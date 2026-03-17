from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import shutil
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from enum import Enum
import json
import csv
import io
import contextlib
import time
from collections import deque, Counter
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
except Exception:  # package is optional in local dev
    LlmChat = None
    UserMessage = None
try:
    from huggingface_hub import InferenceClient
except Exception:
    InferenceClient = None
import resend
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from services.ingestion import IngestionService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'omnimine-secret-2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# LLM Configuration
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
# DeepSeek offers an OpenAI-compatible Chat Completions API in most deployments.
# Allow overriding for self-hosted/proxy setups.
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Hugging Face Inference (API) configuration (no local torch required)
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
HF_MODEL = os.environ.get("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

# Email Configuration
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

app = FastAPI(title="OmniMine API", version="1.0.0")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

ingestion_service = IngestionService(db)

# Evidence uploads (local dev / single-node)
UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    try:
        request.state.request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        return response
    finally:
        dur_ms = int((time.time() - start) * 1000)
        try:
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "method": request.method,
                        "path": request.url.path,
                        "status": getattr(locals().get("response"), "status_code", None),
                        "duration_ms": dur_ms,
                    }
                )
            )
        except Exception:
            pass


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """
    Writes coarse audit events for mutating requests.
    Fine-grained events are also written inside sensitive endpoints.
    """
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        try:
            if request.method in ["POST", "PUT", "PATCH", "DELETE"] and not request.url.path.startswith("/uploads"):
                # best-effort actor extraction from bearer token (do not fail request)
                actor = None
                auth = request.headers.get("authorization") or ""
                if auth.lower().startswith("bearer "):
                    token = auth.split(" ", 1)[1].strip()
                    try:
                        actor = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                    except Exception:
                        actor = None

                org_id = get_org_id(actor)
                await write_audit_event(
                    org_id=org_id,
                    actor=actor,
                    action="http_mutation",
                    resource_type="http",
                    resource_id=None,
                    request=request,
                    status_code=getattr(response, "status_code", None),
                    metadata={"query": dict(request.query_params)},
                )
        except Exception:
            pass


# ============== OBSERVABILITY (D) ==============
@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/readyz")
async def readyz():
    try:
        await db.command("ping")
        return {"ok": True, "mongo": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"mongo not ready: {e}")

SLA_CHECK_INTERVAL_SECONDS = int(os.environ.get("SLA_CHECK_INTERVAL_SECONDS", "300"))
SLA_DUE_SOON_HOURS = int(os.environ.get("SLA_DUE_SOON_HOURS", "2"))
_sla_task: Optional[asyncio.Task] = None
MONITORING_TICK_SECONDS = int(os.environ.get("MONITORING_TICK_SECONDS", "5"))
_monitor_task: Optional[asyncio.Task] = None


class RollingMonitoring:
    """
    In-memory rolling windows per org for live dashboards + spike detection.
    Single-node dev/preview. For production, push events to Kafka / a metrics store.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        # org_id -> deque of (ts_epoch, sentiment, themes[])
        self._events: Dict[str, deque] = {}
        # org_id -> last spike timestamps by key
        self._last_spike: Dict[str, Dict[str, float]] = {}

    async def record(self, org_id: str, sentiment: str, themes: List[str], ts: Optional[datetime] = None):
        if not ts:
            ts = datetime.now(timezone.utc)
        t = ts.timestamp()
        async with self._lock:
            q = self._events.setdefault(org_id, deque(maxlen=200000))
            q.append((t, sentiment, themes or []))

    async def snapshot(self, org_id: str) -> Dict[str, Any]:
        now = time.time()
        async with self._lock:
            q = list(self._events.get(org_id, deque()))

        def window_events(seconds: int):
            cutoff = now - seconds
            return [e for e in q if e[0] >= cutoff]

        ev_60 = window_events(60)
        ev_300 = window_events(300)

        sentiment_60 = Counter([e[1] for e in ev_60])
        sentiment_300 = Counter([e[1] for e in ev_300])

        theme_300 = Counter()
        for _, _, themes in ev_300:
            for th in themes or []:
                theme_300[str(th).strip().lower()] += 1

        top_themes = [{"theme": k, "count": v} for k, v in theme_300.most_common(8)]

        return {
            "now": datetime.now(timezone.utc).isoformat(),
            "window_seconds": {"s60": len(ev_60), "s300": len(ev_300)},
            "sentiment": {
                "s60": dict(sentiment_60),
                "s300": dict(sentiment_300),
            },
            "top_themes_s300": top_themes,
        }

    async def detect_spikes(self) -> List[Dict[str, Any]]:
        """
        Returns spike events to be converted into alerts.
        """
        now = time.time()
        events: List[Dict[str, Any]] = []

        async with self._lock:
            org_ids = list(self._events.keys())

        for org_id in org_ids:
            async with self._lock:
                q = list(self._events.get(org_id, deque()))
                last = self._last_spike.setdefault(org_id, {})

            # windows
            ev_60 = [e for e in q if e[0] >= now - 60]
            ev_600 = [e for e in q if e[0] >= now - 600]
            ev_3600 = [e for e in q if e[0] >= now - 3600]

            total_60 = len(ev_60)
            total_600 = len(ev_600)

            if total_60 >= 20 and total_600 >= 50:
                neg_60 = sum(1 for e in ev_60 if e[1] == "negative")
                neg_600 = sum(1 for e in ev_600 if e[1] == "negative")
                rate_60 = neg_60 / max(1, total_60)
                rate_600 = neg_600 / max(1, total_600)

                # spike when negative rate jumps meaningfully
                if rate_60 >= 0.50 and (rate_60 - rate_600) >= 0.20:
                    key = "sentiment_negative_spike"
                    if now - last.get(key, 0) > 120:
                        last[key] = now
                        events.append({
                            "org_id": org_id,
                            "type": "sentiment_spike",
                            "title": "Negative Sentiment Spike",
                            "message": f"Negative sentiment spiked to {int(rate_60*100)}% in last 60s (baseline {int(rate_600*100)}%).",
                            "severity": "high",
                            "metrics": {"neg_60": neg_60, "total_60": total_60, "rate_60": rate_60, "rate_600": rate_600},
                        })

            # Theme spike (last 5m vs last 1h)
            if len(ev_3600) >= 50:
                ev_300 = [e for e in q if e[0] >= now - 300]
                theme_300 = Counter()
                theme_3600 = Counter()
                for _, _, themes in ev_300:
                    for th in themes or []:
                        theme_300[str(th).strip().lower()] += 1
                for _, _, themes in ev_3600:
                    for th in themes or []:
                        theme_3600[str(th).strip().lower()] += 1

                for theme, c5 in theme_300.most_common(5):
                    if c5 < 10:
                        continue
                    c60 = theme_3600.get(theme, 0)
                    # baseline rate per 5m over 1h ~ c60/12
                    baseline = c60 / 12.0
                    if baseline <= 0:
                        baseline = 1.0
                    if c5 >= baseline * 3:
                        key = f"theme_spike:{theme}"
                        if now - last.get(key, 0) > 300:
                            last[key] = now
                            events.append({
                                "org_id": org_id,
                                "type": "theme_spike",
                                "title": "Theme Spike Detected",
                                "message": f"Theme '{theme}' spiked: {c5} mentions in last 5m (baseline ~{baseline:.1f}/5m).",
                                "severity": "medium",
                                "metrics": {"theme": theme, "count_5m": c5, "baseline_5m": baseline, "count_1h": c60},
                            })

        return events


monitoring = RollingMonitoring()


# ============== REAL-TIME ALERTS (PHASE 3) ==============
class AlertBroadcaster:
    def __init__(self):
        self._subs_by_org: Dict[str, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, org_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subs_by_org.setdefault(org_id, []).append(q)
        return q

    async def unsubscribe(self, org_id: str, q: asyncio.Queue):
        async with self._lock:
            qs = self._subs_by_org.get(org_id) or []
            if q in qs:
                qs.remove(q)
            if not qs and org_id in self._subs_by_org:
                del self._subs_by_org[org_id]

    async def publish(self, org_id: str, event: Dict[str, Any]):
        async with self._lock:
            qs = list(self._subs_by_org.get(org_id) or [])
        logger.info(f"[sse] publish to {len(qs)} subscribers (org={org_id}): {event.get('type')}")
        for q in qs:
            try:
                q.put_nowait(event)
            except Exception:
                # drop if full/closed
                pass


alert_broadcaster = AlertBroadcaster()


async def insert_alert_and_broadcast(alert: "Alert", org_id: str, notify_user_ids: Optional[List[str]] = None):
    alert_dict = alert.model_dump()
    alert_dict["org_id"] = org_id
    alert_dict["created_at"] = alert_dict["created_at"].isoformat()
    # pymongo/motor may add _id (ObjectId) to the dict in-place; keep DB doc separate
    db_doc = dict(alert_dict)
    await db.alerts.insert_one(db_doc)

    event = {
        "type": "alert",
        "org_id": org_id,
        "alert": {k: v for k, v in alert_dict.items() if k != "_id"},
    }
    await alert_broadcaster.publish(org_id, event)


@api_router.get("/stream/alerts")
async def stream_alerts(token: str):
    """
    Server-Sent Events stream of alerts.
    Auth is via token query param because EventSource cannot set Authorization headers.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token")

    org_id = payload.get("org_id")
    if not org_id:
        user_doc = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0, "org_id": 1})
        org_id = (user_doc or {}).get("org_id") or "default"

    q = await alert_broadcaster.subscribe(org_id)

    async def gen():
        try:
            # initial comment to open stream
            yield "event: ping\ndata: {}\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"event: {item.get('type','alert')}\n" + f"data: {json.dumps(item)}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            await alert_broadcaster.unsubscribe(org_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream")

# ============== ENUMS ==============
class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"
    ANALYST = "analyst"


class Permission(str, Enum):
    # User/Org governance
    ORG_LIST = "org:list"
    ORG_CREATE = "org:create"
    ORG_SWITCH = "org:switch"
    USER_ROLE_CHANGE = "user:role_change"
    USER_LIST = "user:list"

    # Core objects
    FEEDBACK_CREATE = "feedback:create"
    FEEDBACK_BULK_CREATE = "feedback:bulk_create"
    FEEDBACK_INGEST = "feedback:ingest"

    CASE_CREATE = "case:create"
    CASE_ASSIGN = "case:assign"
    CASE_START = "case:start"
    CASE_RESOLVE = "case:resolve"
    CASE_VERIFY = "case:verify"
    CASE_ESCALATE = "case:escalate"
    CASE_EVIDENCE_UPLOAD = "case:evidence_upload"

    # Settings / Ops
    SETTINGS_UPDATE = "settings:update"
    SOCIAL_SETTINGS_UPDATE = "social_settings:update"
    REPORTS_MANAGE = "reports:manage"
    SLA_RUN = "sla:run"

    # AI / Orchestration
    AI_RUN = "ai:run"
    HITL_APPROVE = "hitl:approve"

    # Audit/compliance
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"


ROLE_PERMISSIONS: Dict[str, set] = {
    UserRole.ADMIN.value: {p.value for p in Permission},
    UserRole.MANAGER.value: {
        Permission.ORG_LIST.value,
        Permission.ORG_SWITCH.value,
        Permission.USER_LIST.value,
        Permission.FEEDBACK_CREATE.value,
        Permission.FEEDBACK_BULK_CREATE.value,
        Permission.FEEDBACK_INGEST.value,
        Permission.CASE_CREATE.value,
        Permission.CASE_ASSIGN.value,
        Permission.CASE_START.value,
        Permission.CASE_RESOLVE.value,
        Permission.CASE_VERIFY.value,
        Permission.CASE_ESCALATE.value,
        Permission.CASE_EVIDENCE_UPLOAD.value,
        Permission.SETTINGS_UPDATE.value,
        Permission.REPORTS_MANAGE.value,
        Permission.SLA_RUN.value,
        Permission.AI_RUN.value,
        Permission.HITL_APPROVE.value,
        Permission.AUDIT_READ.value,
        Permission.AUDIT_EXPORT.value,
    },
    UserRole.AGENT.value: {
        Permission.USER_LIST.value,
        Permission.FEEDBACK_CREATE.value,
        Permission.CASE_START.value,
        Permission.CASE_RESOLVE.value,
        Permission.CASE_EVIDENCE_UPLOAD.value,
        Permission.AI_RUN.value,
    },
    UserRole.ANALYST.value: {
        Permission.USER_LIST.value,
        Permission.AUDIT_READ.value,
    },
}

# Allow list of org-scoped admin operations (membership management)
ROLE_PERMISSIONS[UserRole.ADMIN.value].add(Permission.ORG_CREATE.value)

class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"

class FeedbackSource(str, Enum):
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    YOUTUBE = "youtube"
    WEBSITE = "website"
    SUPPORT_TICKET = "support_ticket"
    EMAIL = "email"
    SURVEY = "survey"
    MANUAL = "manual"

class CaseStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    VERIFIED = "verified"
    CLOSED = "closed"
    ESCALATED = "escalated"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# ============== MODELS ==============
class Organization(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OrganizationCreate(BaseModel):
    name: str

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole = UserRole.ANALYST
    org_id: str = "default"

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class SwitchOrgRequest(BaseModel):
    org_id: str

class DummyFeedbackRequest(BaseModel):
    interval_seconds: Optional[int] = None  # frontend controls cadence; kept for extensibility

class DummyFeedbackBatchRequest(BaseModel):
    count: int = 10
    negative_min: float = 0.55
    negative_max: float = 0.60

class DummyFeedbackBatchResponse(BaseModel):
    created: int
    negative_target: int
    items: List["Feedback"]

class User(UserBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    team_id: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class FeedbackBase(BaseModel):
    content: str
    source: FeedbackSource = FeedbackSource.MANUAL
    author_name: Optional[str] = None
    author_id: Optional[str] = None
    platform_post_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class FeedbackCreate(FeedbackBase):
    pass

# ============== INGESTION MODELS (Phase A) ==============
class IngestRequest(BaseModel):
    source: str
    payload: Dict[str, Any]

class IngestResponse(BaseModel):
    raw_id: str
    normalized_id: str
    feedback_id: str
    case_id: Optional[str] = None

# ============== MONITORING MODELS (Phase B) ==============
class MonitoringLiveResponse(BaseModel):
    now: str
    window_seconds: Dict[str, int]
    sentiment: Dict[str, Dict[str, int]]
    top_themes_s300: List[Dict[str, Any]] = []

class SentimentAnalysis(BaseModel):
    sentiment: SentimentType
    confidence: float
    emotions: List[str] = []
    themes: List[str] = []
    key_phrases: List[str] = []
    sarcasm_detected: bool = False

class Feedback(FeedbackBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str = "default"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analysis: Optional[SentimentAnalysis] = None
    is_processed: bool = False
    case_id: Optional[str] = None

class CaseBase(BaseModel):
    feedback_id: str
    title: str
    description: Optional[str] = None
    priority: Priority = Priority.MEDIUM

class CaseCreate(CaseBase):
    pass

class CaseEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_filename: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    url: str
    uploaded_by: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: Optional[str] = None

class Case(CaseBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str = "default"
    status: CaseStatus = CaseStatus.OPEN
    assigned_to: Optional[str] = None
    assigned_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    sla_breached: bool = False
    verification_status: Optional[str] = None  # pending|passed|failed
    verified_at: Optional[datetime] = None
    verification_rating: Optional[int] = Field(default=None, ge=1, le=5)
    evidence: List[CaseEvidence] = []

class ResolutionLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str = "default"
    case_id: str
    action: str
    notes: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None

class SurveyBase(BaseModel):
    case_id: str
    feedback_id: str
    rating: int = Field(ge=1, le=5)
    comments: Optional[str] = None
    customer_email: Optional[str] = None

class Survey(SurveyBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str = "default"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    customer_email: Optional[str] = None

class Alert(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str = "default"
    type: str
    title: str
    message: str
    severity: Priority = Priority.MEDIUM
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    related_ids: List[str] = []


# ============== AGENTIC AI (PHASE 2) ==============
class TriageCategory(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    PRODUCT = "product"
    SHIPPING = "shipping"
    SECURITY = "security"
    GENERAL = "general"


class AgenticTriageResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feedback_id: Optional[str] = None
    case_id: Optional[str] = None
    category: TriageCategory = TriageCategory.GENERAL
    suggested_priority: Priority = Priority.MEDIUM
    required_skills: List[str] = []
    summary: str
    recommended_actions: List[str] = []
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str


class AgenticResponseDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str
    customer_reply: str
    internal_note: str
    tone: str = "professional"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str


class ExecutiveDigest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    days: int = 7
    summary: str
    top_themes: List[Dict[str, Any]] = []
    risks: List[str] = []
    recommended_actions: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str


# ============== AGENTIC ORCHESTRATION (PHASE 5 / C) ==============
class OrchestrationRunStatus(str, Enum):
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestrationStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_APPROVAL = "needs_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class OrchestrationGateDecision(BaseModel):
    decision: str  # approve|reject
    note: Optional[str] = None


class OrchestrationStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key: str
    title: str
    status: OrchestrationStepStatus = OrchestrationStepStatus.PENDING
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    requires_approval: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_note: Optional[str] = None
    error: Optional[str] = None


class OrchestrationRun(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str = "default"
    case_id: str
    feedback_id: Optional[str] = None
    status: OrchestrationRunStatus = OrchestrationRunStatus.RUNNING
    current_step_key: Optional[str] = None
    steps: List[OrchestrationStep] = []
    context: Dict[str, Any] = {}
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str

class Team(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str = "default"
    name: str
    description: Optional[str] = None
    members: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BulkFeedbackUpload(BaseModel):
    feedbacks: List[FeedbackCreate]

class AnalyticsQuery(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    source: Optional[FeedbackSource] = None
    sentiment: Optional[SentimentType] = None

# ============== NEW MODELS FOR PHASE 2 ==============
class SocialMediaConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    platform: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    profile_url: Optional[str] = None
    enabled: bool = False
    last_sync: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SystemSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "system_settings"
    organization_name: str = "OmniMine"
    notification_email: Optional[str] = None
    email_alerts_enabled: bool = False
    sla_default_hours: int = 24
    sla_critical_hours: int = 4
    sla_high_hours: int = 8
    sla_medium_hours: int = 24
    sla_low_hours: int = 72
    social_configs: Dict[str, Dict[str, Any]] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EmailNotification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recipient_email: str
    subject: str
    content: str
    alert_id: Optional[str] = None
    sent: bool = False
    sent_at: Optional[datetime] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== AUDIT / COMPLIANCE ==============
AUDIT_RETENTION_DAYS = int(os.environ.get("AUDIT_RETENTION_DAYS", "90"))


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str = "default"
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None

    action: str
    resource_type: str
    resource_id: Optional[str] = None

    request_id: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    status: Optional[int] = None

    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class AuditQuery(BaseModel):
    actor_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    since: Optional[str] = None  # ISO
    until: Optional[str] = None  # ISO
    limit: int = Field(default=200, ge=1, le=1000)


SENSITIVE_KEYS = {"password", "password_hash", "token", "access_token", "api_key", "api_secret", "jwt", "authorization"}


def _redact(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in SENSITIVE_KEYS:
                out[k] = "***redacted***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


async def write_audit_event(
    *,
    org_id: str,
    actor: Optional[Dict[str, Any]],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    request: Optional[Request] = None,
    status_code: Optional[int] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    try:
        ev = AuditEvent(
            org_id=org_id or "default",
            actor_id=(actor or {}).get("sub"),
            actor_email=(actor or {}).get("email"),
            actor_role=(actor or {}).get("role"),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=(request.state.request_id if request and hasattr(request, "state") else None),
            ip=(request.client.host if request and request.client else None),
            user_agent=(request.headers.get("user-agent") if request else None),
            method=(request.method if request else None),
            path=(request.url.path if request else None),
            status=status_code,
            before=_redact(before),
            after=_redact(after),
            metadata=_redact(metadata),
        )
        doc = ev.model_dump()
        await db.audit_events.insert_one(doc)
    except Exception:
        # audit should never break primary flow
        pass

class SocialMediaConfigUpdate(BaseModel):
    platform: str
    profile_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    enabled: bool = False

class SystemSettingsUpdate(BaseModel):
    organization_name: Optional[str] = None
    notification_email: Optional[str] = None
    email_alerts_enabled: Optional[bool] = None
    sla_default_hours: Optional[int] = None
    sla_critical_hours: Optional[int] = None
    sla_high_hours: Optional[int] = None
    sla_medium_hours: Optional[int] = None
    sla_low_hours: Optional[int] = None

class ExportRequest(BaseModel):
    export_type: str = "feedback"  # feedback, cases, analytics
    format: str = "csv"  # csv, pdf
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    filters: Optional[Dict[str, Any]] = None

# ============== PHASE 3 MODELS: SMART ROUTING ==============
class AgentSkill(str, Enum):
    TECHNICAL_SUPPORT = "technical_support"
    BILLING = "billing"
    PRODUCT_ISSUES = "product_issues"
    GENERAL_INQUIRY = "general_inquiry"
    COMPLAINTS = "complaints"
    FEATURE_REQUESTS = "feature_requests"
    SECURITY = "security"
    SHIPPING = "shipping"
    RETURNS = "returns"
    ACCOUNT_MANAGEMENT = "account_management"

class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    skills: List[str] = []
    max_workload: int = 10
    current_workload: int = 0
    avg_resolution_time: float = 0.0
    satisfaction_score: float = 0.0
    cases_resolved: int = 0
    is_available: bool = True
    shift_start: Optional[str] = None  # "09:00"
    shift_end: Optional[str] = None    # "17:00"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentProfileUpdate(BaseModel):
    skills: Optional[List[str]] = None
    max_workload: Optional[int] = None
    is_available: Optional[bool] = None
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None

class SmartRoutingResult(BaseModel):
    recommended_agent_id: str
    recommended_agent_name: str
    confidence_score: float
    reasoning: str
    matched_skills: List[str]
    agent_workload: int
    alternative_agents: List[Dict[str, Any]] = []

class BulkCSVImportResult(BaseModel):
    total_rows: int
    imported: int
    failed: int
    errors: List[str] = []

class ScheduledReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    report_type: str  # "daily_digest", "weekly_summary", "monthly_analytics"
    recipients: List[str] = []
    schedule: str  # "daily", "weekly", "monthly"
    last_sent: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== HELPERS ==============
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, email: str, role: str, org_id: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "org_id": org_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def require_role(roles: List[UserRole]):
    async def role_checker(user: Dict = Depends(get_current_user)):
        if user.get("role") not in [r.value for r in roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker


def has_permission(role: str, perm: str) -> bool:
    return perm in ROLE_PERMISSIONS.get(role or "", set())


async def require_permission(perms: List[Permission]):
    async def perm_checker(user: Dict = Depends(get_current_user)):
        role = user.get("role") or ""
        needed = [p.value for p in perms]
        if not any(has_permission(role, p) for p in needed):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return perm_checker


def get_org_id(user: Optional[Dict[str, Any]]) -> str:
    return (user or {}).get("org_id") or "default"


async def adjust_agent_workload(org_id: str, user_id: str, delta: int, resolved_delta: int = 0):
    if not user_id:
        return
    # Ensure profile exists
    await db.agent_profiles.update_one(
        {"user_id": user_id, "org_id": org_id},
        {"$setOnInsert": {
            "user_id": user_id,
            "org_id": org_id,
            "skills": ["general_inquiry"],
            "max_workload": 10,
            "current_workload": 0,
            "avg_resolution_time": 24.0,
            "satisfaction_score": 3.5,
            "cases_resolved": 0,
            "is_available": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    inc: Dict[str, Any] = {}
    if delta != 0:
        inc["current_workload"] = delta
    if resolved_delta != 0:
        inc["cases_resolved"] = resolved_delta

    if inc:
        await db.agent_profiles.update_one(
            {"user_id": user_id, "org_id": org_id},
            {"$inc": inc, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        )

    # Prevent negative workload
    await db.agent_profiles.update_one(
        {"user_id": user_id, "org_id": org_id, "current_workload": {"$lt": 0}},
        {"$set": {"current_workload": 0, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )


async def get_sla_hours_for_priority(priority: Priority, org_id: str = "default") -> int:
    settings = await db.system_settings.find_one({"id": "system_settings", "org_id": org_id}, {"_id": 0})
    if not settings:
        # defaults
        return {
            Priority.CRITICAL: 4,
            Priority.HIGH: 8,
            Priority.MEDIUM: 24,
            Priority.LOW: 72,
        }.get(priority, 24)

    key_map = {
        Priority.CRITICAL: "sla_critical_hours",
        Priority.HIGH: "sla_high_hours",
        Priority.MEDIUM: "sla_medium_hours",
        Priority.LOW: "sla_low_hours",
    }
    key = key_map.get(priority, "sla_default_hours")
    value = settings.get(key) or settings.get("sla_default_hours") or 24
    try:
        return int(value)
    except Exception:
        return 24


async def log_case_action(case_id: str, action: str, notes: str, created_by: str, metadata: Optional[Dict[str, Any]] = None, org_id: Optional[str] = None):
    if not org_id:
        try:
            case_doc = await db.cases.find_one({"id": case_id}, {"_id": 0, "org_id": 1})
            org_id = (case_doc or {}).get("org_id") or "default"
        except Exception:
            org_id = "default"
    log = ResolutionLog(
        org_id=org_id or "default",
        case_id=case_id,
        action=action,
        notes=notes,
        created_by=created_by,
        metadata=metadata,
    )
    log_dict = log.model_dump()
    log_dict["created_at"] = log_dict["created_at"].isoformat()
    await db.resolution_logs.insert_one(log_dict)


async def create_escalation_alert(case_id: str, title: str, message: str, severity: Priority = Priority.CRITICAL):
    alert = Alert(
        type="case_escalated",
        title=title,
        message=message,
        severity=severity,
        related_ids=[case_id],
    )
    case_doc = await db.cases.find_one({"id": case_id}, {"_id": 0, "org_id": 1})
    org_id = (case_doc or {}).get("org_id") or "default"
    await insert_alert_and_broadcast(alert, org_id=org_id)
    await send_alert_email(alert)


async def auto_assign_case_rules(case_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Rule-based auto-assignment for newly created cases.
    Current rule: for HIGH/CRITICAL cases, assign to the available agent/manager
    with the lowest current_workload (and below max_workload).
    """
    try:
        priority = case_doc.get("priority")
        if priority not in [Priority.HIGH.value, Priority.CRITICAL.value]:
            return None

        # Prefer agents/managers, but fall back to admins if none exist (single-user setups).
        agents = await db.users.find({"role": {"$in": ["agent", "manager", "admin"]}}, {"_id": 0}).to_list(200)
        if not agents:
            return None

        candidates = []
        for agent in agents:
            profile = await db.agent_profiles.find_one({"user_id": agent["id"]}, {"_id": 0})
            if not profile:
                profile = {
                    "user_id": agent["id"],
                    "skills": ["general_inquiry"],
                    "max_workload": 10,
                    "current_workload": 0,
                    "avg_resolution_time": 24.0,
                    "satisfaction_score": 3.5,
                    "cases_resolved": 0,
                    "is_available": True,
                }
                await db.agent_profiles.insert_one(profile)

            if not profile.get("is_available", True):
                continue
            if profile.get("current_workload", 0) >= profile.get("max_workload", 10):
                continue

            candidates.append((profile.get("current_workload", 0), agent, profile))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])
        _, chosen_agent, chosen_profile = candidates[0]
        return {"agent": chosen_agent, "profile": chosen_profile}
    except Exception as e:
        logger.error(f"Auto-assign rules error: {e}")
        return None


async def agentic_triage_text(text: str) -> Dict[str, Any]:
    """
    Lightweight triage: use LLM when available; otherwise heuristic.
    Returns dict matching AgenticTriageResult fields (except ids/timestamps).
    """
    text_l = (text or "").lower()

    # Heuristic category/skills
    category = TriageCategory.GENERAL
    skills: List[str] = ["general_inquiry"]
    if any(k in text_l for k in ["bill", "invoice", "refund", "charge", "payment", "subscription", "pricing"]):
        category = TriageCategory.BILLING
        skills = ["billing"]
    elif any(k in text_l for k in ["crash", "bug", "error", "not working", "broken", "issue", "api"]):
        category = TriageCategory.TECHNICAL
        skills = ["technical_support", "product_issues"]
    elif any(k in text_l for k in ["feature", "request", "missing", "would like"]):
        category = TriageCategory.PRODUCT
        skills = ["feature_requests"]
    elif any(k in text_l for k in ["delivery", "shipping", "late", "package", "courier"]):
        category = TriageCategory.SHIPPING
        skills = ["shipping"]
    elif any(k in text_l for k in ["hack", "breach", "stolen", "security", "phish"]):
        category = TriageCategory.SECURITY
        skills = ["security"]

    # Heuristic priority
    priority = Priority.MEDIUM
    if any(k in text_l for k in ["urgent", "asap", "immediately", "security", "breach", "hacked"]):
        priority = Priority.CRITICAL
    elif any(k in text_l for k in ["worst", "terrible", "angry", "refund", "broken", "unacceptable"]):
        priority = Priority.HIGH

    summary = (text or "").strip()
    if len(summary) > 240:
        summary = summary[:240].rstrip() + "..."

    actions = [
        "Acknowledge the issue and apologize",
        "Collect key details (account/order, timestamps, screenshots/logs)",
        "Propose next steps and expected timeline",
    ]
    if category == TriageCategory.SECURITY:
        actions = [
            "Initiate security incident workflow",
            "Force password reset / revoke sessions",
            "Request incident details and preserve evidence",
        ]

    # Prefer Hugging Face for AI Copilot when configured.
    if HF_TOKEN and InferenceClient:
        try:
            data = await hf_chat_json(
                system=(
                    "You are a customer support triage agent. "
                    "Return ONLY valid JSON with keys: "
                    "category (billing|technical|product|shipping|security|general), "
                    "suggested_priority (low|medium|high|critical), "
                    "required_skills (array), summary (string), recommended_actions (array), confidence (0-1)."
                ),
                user=f"Triage this:\n\n{text}",
            )
            return {
                "category": data.get("category", category.value),
                "suggested_priority": data.get("suggested_priority", priority.value),
                "required_skills": data.get("required_skills", skills),
                "summary": data.get("summary", summary),
                "recommended_actions": data.get("recommended_actions", actions),
                "confidence": float(data.get("confidence", 0.7)),
            }
        except Exception as e:
            logger.warning(f"Hugging Face triage fallback to heuristic: {e}")

    # Optional DeepSeek enhancement (JSON)
    if DEEPSEEK_API_KEY:
        try:
            data = await deepseek_chat_json(
                system=(
                    "You are a customer support triage agent. "
                    "Return ONLY valid JSON with keys: "
                    "category (billing|technical|product|shipping|security|general), "
                    "suggested_priority (low|medium|high|critical), "
                    "required_skills (array), summary (string), recommended_actions (array), confidence (0-1)."
                ),
                user=f"Triage this:\n\n{text}",
            )
            return {
                "category": data.get("category", category.value),
                "suggested_priority": data.get("suggested_priority", priority.value),
                "required_skills": data.get("required_skills", skills),
                "summary": data.get("summary", summary),
                "recommended_actions": data.get("recommended_actions", actions),
                "confidence": float(data.get("confidence", 0.7)),
            }
        except Exception as e:
            logger.warning(f"DeepSeek triage fallback to heuristic: {e}")

    # Optional Emergent LLM enhancement (JSON)
    if EMERGENT_LLM_KEY and LlmChat and UserMessage:
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"triage-{uuid.uuid4()}",
                system_message=(
                    "You are a customer support triage agent. "
                    "Return ONLY valid JSON with keys: "
                    "category (billing|technical|product|shipping|security|general), "
                    "suggested_priority (low|medium|high|critical), "
                    "required_skills (array), summary (string), recommended_actions (array), confidence (0-1)."
                ),
            ).with_model("openai", "gpt-5.2")
            response = await chat.send_message(UserMessage(text=f"Triage this:\n\n{text}"))
            data = json.loads(response)
            return {
                "category": data.get("category", category),
                "suggested_priority": data.get("suggested_priority", priority),
                "required_skills": data.get("required_skills", skills),
                "summary": data.get("summary", summary),
                "recommended_actions": data.get("recommended_actions", actions),
                "confidence": float(data.get("confidence", 0.7)),
            }
        except Exception as e:
            logger.warning(f"LLM triage fallback to heuristic: {e}")

    return {
        "category": category.value,
        "suggested_priority": priority.value,
        "required_skills": skills,
        "summary": summary or "Customer issue reported",
        "recommended_actions": actions,
        "confidence": 0.65,
    }


async def agentic_response_draft(case_title: str, case_description: str, feedback_text: str = "") -> Dict[str, str]:
    """
    Draft a customer reply + internal note. Uses LLM when available, else template.
    """
    base_context = f"Case title: {case_title}\nDescription: {case_description}\nFeedback: {feedback_text}"

    # Prefer Hugging Face for AI Copilot when configured.
    if HF_TOKEN and InferenceClient:
        try:
            data = await hf_chat_json(
                system=(
                    "You are a CX copilot. Produce TWO outputs as JSON: "
                    "{customer_reply: string, internal_note: string}. "
                    "Customer reply should be polite, concise, and action-oriented. "
                    "Internal note should contain triage checklist and next steps."
                ),
                user=f"Draft reply and internal note.\n\n{base_context}",
            )
            return {
                "customer_reply": data.get("customer_reply", ""),
                "internal_note": data.get("internal_note", ""),
            }
        except Exception as e:
            logger.warning(f"Hugging Face response fallback to template: {e}")

    if DEEPSEEK_API_KEY:
        try:
            data = await deepseek_chat_json(
                system=(
                    "You are a CX copilot. Produce TWO outputs as JSON: "
                    "{customer_reply: string, internal_note: string}. "
                    "Customer reply should be polite, concise, and action-oriented. "
                    "Internal note should contain triage checklist and next steps."
                ),
                user=f"Draft reply and internal note.\n\n{base_context}",
            )
            return {
                "customer_reply": data.get("customer_reply", ""),
                "internal_note": data.get("internal_note", ""),
            }
        except Exception as e:
            logger.warning(f"DeepSeek response fallback to template: {e}")

    if EMERGENT_LLM_KEY and LlmChat and UserMessage:
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"reply-{uuid.uuid4()}",
                system_message=(
                    "You are a CX copilot. Produce TWO outputs as JSON: "
                    "{customer_reply: string, internal_note: string}. "
                    "Customer reply should be polite, concise, and action-oriented. "
                    "Internal note should contain triage checklist and next steps."
                ),
            ).with_model("openai", "gpt-5.2")
            response = await chat.send_message(UserMessage(text=f"Draft reply and internal note.\n\n{base_context}"))
            data = json.loads(response)
            return {
                "customer_reply": data.get("customer_reply", ""),
                "internal_note": data.get("internal_note", ""),
            }
        except Exception as e:
            logger.warning(f"LLM response fallback to template: {e}")

    customer_reply = (
        "Thanks for reaching out—sorry for the trouble. "
        "We’re looking into this now. Could you share any relevant details (order/account, time of issue, and screenshots/logs if available)? "
        "We’ll update you with next steps shortly."
    )
    internal_note = (
        "Triage checklist:\n"
        "- Confirm customer identity/account\n"
        "- Reproduce issue / gather logs & screenshots\n"
        "- Determine priority and impact scope\n"
        "- Provide workaround if possible\n"
        "- Track fix and update customer\n"
    )
    return {"customer_reply": customer_reply, "internal_note": internal_note}


# ============== ORCHESTRATION ENGINE (LANGGRAPH-STYLE) ==============
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _orchestration_build_steps() -> List[OrchestrationStep]:
    """
    Minimal “LangGraph-style” workflow: deterministic nodes + HITL gates.
    """
    return [
        OrchestrationStep(key="triage", title="AI triage (category, priority, actions)"),
        OrchestrationStep(key="gate_apply_priority", title="HITL: apply suggested priority", requires_approval=True),
        OrchestrationStep(key="draft_reply", title="Draft customer reply + internal note"),
        OrchestrationStep(key="gate_apply_assign", title="HITL: apply suggested assignee (optional)", requires_approval=True),
        OrchestrationStep(key="complete", title="Workflow complete"),
    ]


async def _orchestration_get_case_and_feedback(org_id: str, case_id: str) -> Dict[str, Any]:
    case = await db.cases.find_one({"id": case_id, "org_id": org_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    fb = None
    if case.get("feedback_id"):
        fb = await db.feedbacks.find_one({"id": case["feedback_id"], "org_id": org_id}, {"_id": 0})
    return {"case": case, "feedback": fb}


async def _orchestration_persist_run(run: OrchestrationRun):
    run.updated_at = _now_iso()
    await db.agentic_runs.update_one(
        {"id": run.id, "org_id": run.org_id},
        {"$set": run.model_dump()},
        upsert=True,
    )


async def _orchestration_load_run(org_id: str, run_id: str) -> OrchestrationRun:
    doc = await db.agentic_runs.find_one({"id": run_id, "org_id": org_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Run not found")
    return OrchestrationRun(**doc)


def _step_by_key(run: OrchestrationRun, key: str) -> Optional[OrchestrationStep]:
    for s in run.steps:
        if s.key == key:
            return s
    return None


async def _orchestration_run_until_wait(run: OrchestrationRun) -> OrchestrationRun:
    """
    Execute steps sequentially until:
    - workflow completes, or
    - a gate needs approval, or
    - failure occurs.
    """
    if run.status in [OrchestrationRunStatus.CANCELLED, OrchestrationRunStatus.COMPLETED, OrchestrationRunStatus.FAILED]:
        return run

    org_id = run.org_id
    data = await _orchestration_get_case_and_feedback(org_id, run.case_id)
    case = data["case"]
    feedback = data["feedback"]
    feedback_text = (feedback.get("content") if feedback else "") or ""

    for step in run.steps:
        if step.status in [OrchestrationStepStatus.COMPLETED, OrchestrationStepStatus.SKIPPED]:
            continue
        if step.status in [OrchestrationStepStatus.NEEDS_APPROVAL, OrchestrationStepStatus.APPROVED]:
            run.status = OrchestrationRunStatus.WAITING_FOR_APPROVAL
            run.current_step_key = step.key
            await _orchestration_persist_run(run)
            return run
        if step.status in [OrchestrationStepStatus.REJECTED]:
            step.status = OrchestrationStepStatus.SKIPPED
            step.finished_at = _now_iso()
            continue
        if step.status in [OrchestrationStepStatus.FAILED]:
            run.status = OrchestrationRunStatus.FAILED
            run.current_step_key = step.key
            await _orchestration_persist_run(run)
            return run

        run.current_step_key = step.key
        step.status = OrchestrationStepStatus.RUNNING
        step.started_at = _now_iso()
        await _orchestration_persist_run(run)

        try:
            if step.key == "triage":
                triage = await agentic_triage_text(feedback_text or case.get("description", "") or case.get("title", ""))
                step.output = {"triage": triage}
                run.context["triage"] = triage
                step.status = OrchestrationStepStatus.COMPLETED
                step.finished_at = _now_iso()

            elif step.key == "gate_apply_priority":
                triage = run.context.get("triage") or {}
                suggested = triage.get("suggested_priority", Priority.MEDIUM.value)
                step.output = {"proposed_priority": suggested, "current_priority": case.get("priority")}
                step.status = OrchestrationStepStatus.NEEDS_APPROVAL
                run.status = OrchestrationRunStatus.WAITING_FOR_APPROVAL
                await _orchestration_persist_run(run)
                return run

            elif step.key == "draft_reply":
                draft = await agentic_response_draft(case.get("title", ""), case.get("description", "") or "", feedback_text)
                step.output = {"draft": draft}
                run.context["draft"] = draft
                step.status = OrchestrationStepStatus.COMPLETED
                step.finished_at = _now_iso()

            elif step.key == "gate_apply_assign":
                proposed_agent_id = None
                proposed_agent_name = None
                try:
                    routing = await analyze_case_for_routing(
                        case_title=case.get("title", ""),
                        case_description=case.get("description", "") or "",
                        feedback_text=feedback_text,
                        org_id=org_id,
                    )
                    proposed_agent_id = routing.get("recommended_agent_id")
                    proposed_agent_name = routing.get("recommended_agent_name")
                except Exception:
                    proposed_agent_id = None
                    proposed_agent_name = None

                if not proposed_agent_id:
                    step.status = OrchestrationStepStatus.SKIPPED
                    step.output = {"skipped": True, "reason": "No suggested assignee"}
                    step.finished_at = _now_iso()
                else:
                    step.output = {
                        "proposed_assignee_id": proposed_agent_id,
                        "proposed_assignee_name": proposed_agent_name,
                        "current_assigned_to": case.get("assigned_to"),
                    }
                    step.status = OrchestrationStepStatus.NEEDS_APPROVAL
                    run.status = OrchestrationRunStatus.WAITING_FOR_APPROVAL
                    await _orchestration_persist_run(run)
                    return run

            elif step.key == "complete":
                step.status = OrchestrationStepStatus.COMPLETED
                step.finished_at = _now_iso()
                run.status = OrchestrationRunStatus.COMPLETED
                run.current_step_key = None
                await _orchestration_persist_run(run)
                return run

            else:
                step.status = OrchestrationStepStatus.SKIPPED
                step.finished_at = _now_iso()

        except Exception as e:
            step.status = OrchestrationStepStatus.FAILED
            step.error = str(e)
            step.finished_at = _now_iso()
            run.status = OrchestrationRunStatus.FAILED
            run.current_step_key = step.key
            await _orchestration_persist_run(run)
            return run

    run.status = OrchestrationRunStatus.COMPLETED
    run.current_step_key = None
    await _orchestration_persist_run(run)
    return run

# ============== AI ANALYSIS ==============
async def analyze_feedback_with_ai(content: str) -> SentimentAnalysis:
    """Use GPT-5.2 to analyze feedback sentiment, emotions, themes"""
    try:
        if HF_TOKEN and InferenceClient:
            result = await hf_chat_json(
                system=(
                    "You are an expert sentiment analysis AI. Analyze the given feedback and return a JSON response with:\n"
                    "- sentiment: \"positive\", \"neutral\", or \"negative\"\n"
                    "- confidence: float between 0 and 1\n"
                    "- emotions: list of detected emotions (joy, anger, sadness, fear, surprise, disgust, trust, anticipation)\n"
                    "- themes: list of main topics/themes mentioned (e.g., \"customer service\", \"product quality\", \"pricing\", \"delivery\")\n"
                    "- key_phrases: important phrases from the text\n"
                    "- sarcasm_detected: boolean if sarcasm is detected\n\n"
                    "Return ONLY valid JSON, no other text."
                ),
                user=f"Analyze this customer feedback:\n\n{content}",
            )
            return SentimentAnalysis(
                sentiment=SentimentType(result.get("sentiment", "neutral")),
                confidence=float(result.get("confidence", 0.5)),
                emotions=result.get("emotions", []) or [],
                themes=result.get("themes", []) or [],
                key_phrases=result.get("key_phrases", []) or [],
                sarcasm_detected=bool(result.get("sarcasm_detected", False)),
            )

        if DEEPSEEK_API_KEY:
            result = await deepseek_chat_json(
                system=(
                    "You are an expert sentiment analysis AI. Analyze the given feedback and return a JSON response with:\n"
                    "- sentiment: \"positive\", \"neutral\", or \"negative\"\n"
                    "- confidence: float between 0 and 1\n"
                    "- emotions: list of detected emotions (joy, anger, sadness, fear, surprise, disgust, trust, anticipation)\n"
                    "- themes: list of main topics/themes mentioned (e.g., \"customer service\", \"product quality\", \"pricing\", \"delivery\")\n"
                    "- key_phrases: important phrases from the text\n"
                    "- sarcasm_detected: boolean if sarcasm is detected\n\n"
                    "Return ONLY valid JSON, no other text."
                ),
                user=f"Analyze this customer feedback:\n\n{content}",
            )
            return SentimentAnalysis(
                sentiment=SentimentType(result.get("sentiment", "neutral")),
                confidence=float(result.get("confidence", 0.5)),
                emotions=result.get("emotions", []) or [],
                themes=result.get("themes", []) or [],
                key_phrases=result.get("key_phrases", []) or [],
                sarcasm_detected=bool(result.get("sarcasm_detected", False)),
            )

        if not EMERGENT_LLM_KEY or LlmChat is None or UserMessage is None:
            raise RuntimeError("LLM integration not configured")
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"analysis-{uuid.uuid4()}",
            system_message="""You are an expert sentiment analysis AI. Analyze the given feedback and return a JSON response with:
- sentiment: "positive", "neutral", or "negative"
- confidence: float between 0 and 1
- emotions: list of detected emotions (joy, anger, sadness, fear, surprise, disgust, trust, anticipation)
- themes: list of main topics/themes mentioned (e.g., "customer service", "product quality", "pricing", "delivery")
- key_phrases: important phrases from the text
- sarcasm_detected: boolean if sarcasm is detected

Return ONLY valid JSON, no other text."""
        ).with_model("openai", "gpt-5.2")
        
        message = UserMessage(text=f"Analyze this customer feedback:\n\n{content}")
        response = await chat.send_message(message)
        
        # Parse JSON response
        try:
            result = json.loads(response)
            return SentimentAnalysis(
                sentiment=SentimentType(result.get("sentiment", "neutral")),
                confidence=float(result.get("confidence", 0.5)),
                emotions=result.get("emotions", []),
                themes=result.get("themes", []),
                key_phrases=result.get("key_phrases", []),
                sarcasm_detected=result.get("sarcasm_detected", False)
            )
        except json.JSONDecodeError:
            # Fallback parsing
            sentiment = SentimentType.NEUTRAL
            if "positive" in response.lower():
                sentiment = SentimentType.POSITIVE
            elif "negative" in response.lower():
                sentiment = SentimentType.NEGATIVE
            return SentimentAnalysis(sentiment=sentiment, confidence=0.7, emotions=[], themes=[], key_phrases=[])
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        # Fallback to simple keyword-based analysis
        content_lower = content.lower()
        positive_words = ["great", "excellent", "amazing", "love", "good", "fantastic", "wonderful", "happy", "satisfied"]
        negative_words = ["bad", "terrible", "awful", "hate", "poor", "disappointed", "angry", "frustrated", "worst"]
        
        pos_count = sum(1 for w in positive_words if w in content_lower)
        neg_count = sum(1 for w in negative_words if w in content_lower)
        
        if pos_count > neg_count:
            sentiment = SentimentType.POSITIVE
        elif neg_count > pos_count:
            sentiment = SentimentType.NEGATIVE
        else:
            sentiment = SentimentType.NEUTRAL
            
        confidence = 0.6
        if pos_count != neg_count:
            confidence = min(0.95, 0.6 + 0.1 * abs(pos_count - neg_count))

        return SentimentAnalysis(sentiment=sentiment, confidence=confidence, emotions=[], themes=[], key_phrases=[])


async def deepseek_chat_json(system: str, user: str) -> Dict[str, Any]:
    """
    DeepSeek OpenAI-compatible chat call that must return JSON.
    Uses aiohttp (already in requirements).
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    url = f"{DEEPSEEK_BASE_URL.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=45)) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"DeepSeek API error {resp.status}: {text[:400]}")
            data = json.loads(text)
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or "{}"
            return json.loads(content)


async def hf_chat_json(system: str, user: str) -> Dict[str, Any]:
    """
    Hugging Face Inference API JSON chat.
    Uses huggingface_hub.InferenceClient (sync), wrapped in a thread.
    """
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN not set")
    if not InferenceClient:
        raise RuntimeError("huggingface_hub not available")

    def _call() -> Dict[str, Any]:
        client = InferenceClient(model=HF_MODEL, token=HF_TOKEN)
        # Many HF chat models support the OpenAI-style chat.completions endpoint.
        # We request a JSON object explicitly in the system prompt.
        resp = client.chat.completions.create(
            model=HF_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("HF returned empty content")

        # Be tolerant to models that wrap JSON in prose/codefences.
        try:
            return json.loads(content)
        except Exception:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = content[start : end + 1]
                return json.loads(snippet)
            raise

    return await asyncio.to_thread(_call)

# ============== AUTH ROUTES ==============
@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=user_data.email,
        name=user_data.name,
        role=user_data.role,
        org_id=getattr(user_data, "org_id", None) or "default",
    )
    user_dict = user.model_dump()
    user_dict["password_hash"] = hash_password(user_data.password)
    user_dict["created_at"] = user_dict["created_at"].isoformat()
    
    await db.users.insert_one(user_dict)
    token = create_token(user.id, user.email, user.role.value, user.org_id)

    await write_audit_event(
        org_id=user.org_id,
        actor={"sub": user.id, "email": user.email, "role": user.role.value, "org_id": user.org_id},
        action="auth_register",
        resource_type="user",
        resource_id=user.id,
        metadata={"email": user.email},
    )
    
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "name": user.name, "role": user.role.value, "org_id": user.org_id}
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    org_id = user.get("org_id") or "default"
    token = create_token(user["id"], user["email"], user["role"], org_id)

    await write_audit_event(
        org_id=org_id,
        actor={"sub": user["id"], "email": user["email"], "role": user.get("role"), "org_id": org_id},
        action="auth_login",
        resource_type="user",
        resource_id=user["id"],
        metadata={"email": user["email"]},
    )
    return TokenResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"], "org_id": org_id}
    )

@api_router.get("/auth/me")
async def get_me(user: Dict = Depends(get_current_user)):
    user_data = await db.users.find_one({"id": user["sub"]}, {"_id": 0, "password_hash": 0})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return user_data


@api_router.post("/auth/switch-org", response_model=TokenResponse)
async def switch_org(payload: SwitchOrgRequest, user: Dict = Depends(get_current_user)):
    """
    Re-issue a JWT scoped to the requested org.
    Admin-only (for now): allows viewing another org's data without re-login.
    """
    if not has_permission(user.get("role"), Permission.ORG_SWITCH.value):
        raise HTTPException(status_code=403, detail="Only admins can switch organizations")

    org_id = payload.org_id or "default"
    org = await db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    user_doc = await db.users.find_one({"id": user["sub"]}, {"_id": 0, "password_hash": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_token(user_doc["id"], user_doc["email"], user_doc.get("role", "analyst"), org_id)
    user_doc["org_id"] = org_id

    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="org_switch",
        resource_type="organization",
        resource_id=org_id,
        metadata={"user_id": user.get("sub")},
    )
    return TokenResponse(access_token=token, user=user_doc)

# ============== FEEDBACK ROUTES ==============
@api_router.post("/feedback", response_model=Feedback)
async def create_feedback(feedback_data: FeedbackCreate, user: Dict = Depends(get_current_user)):
    feedback = Feedback(**feedback_data.model_dump())
    feedback.org_id = user.get("org_id") or "default"
    
    # Analyze with AI
    analysis = await analyze_feedback_with_ai(feedback.content)
    feedback.analysis = analysis
    feedback.is_processed = True
    
    feedback_dict = feedback.model_dump()
    feedback_dict["created_at"] = feedback_dict["created_at"].isoformat()
    if feedback_dict["analysis"]:
        feedback_dict["analysis"] = feedback_dict["analysis"]
    
    await db.feedbacks.insert_one(feedback_dict)

    # Real-time monitoring (rolling windows)
    try:
        await monitoring.record(
            feedback.org_id,
            analysis.sentiment.value if hasattr(analysis.sentiment, "value") else str(analysis.sentiment),
            analysis.themes or [],
        )
    except Exception:
        pass
    
    # Create alert for negative feedback + auto-create case (CFL v2.1)
    if analysis.sentiment == SentimentType.NEGATIVE and analysis.confidence > 0.7:
        alert = Alert(
            type="negative_feedback",
            title="Negative Feedback Detected",
            message=f"New negative feedback from {feedback.source.value}: {feedback.content[:100]}...",
            severity=Priority.HIGH,
            related_ids=[feedback.id]
        )
        await insert_alert_and_broadcast(alert, org_id=feedback.org_id)

        # Auto-create a case if not already linked
        priority = Priority.MEDIUM
        if analysis.confidence >= 0.9:
            priority = Priority.CRITICAL
        elif analysis.confidence >= 0.8:
            priority = Priority.HIGH

        case = Case(
            feedback_id=feedback.id,
            title=f"Issue: {feedback.content[:50]}...",
            description=feedback.content,
            priority=priority,
        )
        case.org_id = feedback.org_id
        sla_hours = await get_sla_hours_for_priority(case.priority, org_id=feedback.org_id)
        case.due_date = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

        case_dict = case.model_dump()
        case_dict["created_at"] = case_dict["created_at"].isoformat()
        case_dict["updated_at"] = case_dict["updated_at"].isoformat()
        if case_dict.get("due_date"):
            case_dict["due_date"] = case_dict["due_date"].isoformat()

        await db.cases.insert_one(case_dict)
        await db.feedbacks.update_one({"id": feedback.id}, {"$set": {"case_id": case.id}})
        feedback.case_id = case.id

        await log_case_action(
            case.id,
            "created",
            f"Auto-created case from negative feedback {feedback.id}",
            created_by=user["sub"],
            metadata={"auto": True, "priority": case.priority.value, "sla_hours": sla_hours},
        )

        # Alert for new case created
        case_alert = Alert(
            type="case_created",
            title="Case Auto-Created",
            message=f"A case was auto-created from negative feedback ({case.priority.value}): {case.title}",
            severity=Priority.HIGH if case.priority in [Priority.HIGH, Priority.CRITICAL] else Priority.MEDIUM,
            related_ids=[case.id, feedback.id],
        )
        await insert_alert_and_broadcast(case_alert, org_id=case.org_id)

        # Auto-assignment (rules) for high/critical cases
        assigned = await auto_assign_case_rules(case_dict)
        if assigned:
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.cases.update_one(
                {"id": case.id},
                {"$set": {
                    "assigned_to": assigned["agent"]["id"],
                    "assigned_by": "auto_rules",
                    "status": CaseStatus.ASSIGNED.value,
                    "updated_at": now_iso,
                }},
            )
            await db.agent_profiles.update_one(
                {"user_id": assigned["agent"]["id"]},
                {"$inc": {"current_workload": 1}},
            )
            await log_case_action(
                case.id,
                "auto_assigned",
                f"Auto-assigned to {assigned['agent'].get('name','')}",
                created_by="system",
                metadata={"assigned_to": assigned["agent"]["id"]},
            )
            auto_assign_alert = Alert(
                type="case_auto_assigned",
                title="Case Auto-Assigned",
                message=f"Case '{case.title[:80]}' auto-assigned to {assigned['agent'].get('name','agent')}.",
                severity=Priority.MEDIUM,
                related_ids=[case.id],
            )
            await insert_alert_and_broadcast(auto_assign_alert, org_id=case.org_id)
    
    return feedback


# ============== DEV / TESTING ROUTES ==============
@api_router.post("/dev/dummy-feedback", response_model=Feedback)
async def generate_dummy_feedback(_: DummyFeedbackRequest = None, user: Dict = Depends(get_current_user)):
    """
    Generate a realistic dummy feedback item using Hugging Face LLM.
    Purpose: exercise the full pipeline (analysis -> alerts -> auto-case creation -> routing).
    """
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins/managers can generate dummy feedback")

    if not (HF_TOKEN and InferenceClient):
        raise HTTPException(status_code=400, detail="Hugging Face is not configured (HF_TOKEN missing)")

    org_id = get_org_id(user)

    # 1) Generate feedback content (HF)
    seed = str(uuid.uuid4())
    gen = await hf_chat_json(
        system=(
            "Generate ONE realistic customer feedback item for a SaaS product. "
            "Return ONLY valid JSON with keys: "
            "content (string, 1-3 sentences), "
            "source (one of: twitter, facebook, youtube, website, support_ticket, email, survey, manual), "
            "author_name (string), "
            "sentiment_hint (positive|neutral|negative)."
        ),
        user=(
            f"Create a diverse feedback example. seed={seed}. "
            "Vary the sentiment, topic (billing, bugs, UX, performance, support), and tone."
        ),
    )
    content = (gen.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=500, detail="LLM did not generate content")

    source_raw = (gen.get("source") or "manual").strip().lower()
    if source_raw not in {s.value for s in FeedbackSource}:
        source_raw = "manual"

    author_name = (gen.get("author_name") or "Customer").strip()[:80]

    # 2) Analyze with HF (force HF path regardless of other providers)
    analysis_json = await hf_chat_json(
        system=(
            "You are an expert sentiment analysis AI. Analyze the given feedback and return a JSON response with:\n"
            "- sentiment: \"positive\", \"neutral\", or \"negative\"\n"
            "- confidence: float between 0 and 1\n"
            "- emotions: list of detected emotions\n"
            "- themes: list of main topics/themes mentioned\n"
            "- key_phrases: important phrases from the text\n"
            "- sarcasm_detected: boolean\n\n"
            "Return ONLY valid JSON, no other text."
        ),
        user=f"Analyze this customer feedback:\n\n{content}",
    )
    analysis = SentimentAnalysis(
        sentiment=SentimentType(analysis_json.get("sentiment", "neutral")),
        confidence=float(analysis_json.get("confidence", 0.6)),
        emotions=analysis_json.get("emotions", []) or [],
        themes=analysis_json.get("themes", []) or [],
        key_phrases=analysis_json.get("key_phrases", []) or [],
        sarcasm_detected=bool(analysis_json.get("sarcasm_detected", False)),
    )

    # 3) Insert feedback and run the same business logic as /feedback
    feedback = Feedback(
        content=content,
        source=FeedbackSource(source_raw),
        author_name=author_name,
    )
    feedback.org_id = org_id
    feedback.analysis = analysis
    feedback.is_processed = True

    feedback_dict = feedback.model_dump()
    feedback_dict["created_at"] = feedback_dict["created_at"].isoformat()
    await db.feedbacks.insert_one(feedback_dict)

    # Negative feedback alert + auto-case creation (same logic as create_feedback)
    if analysis.sentiment == SentimentType.NEGATIVE and analysis.confidence > 0.7:
        alert = Alert(
            type="negative_feedback",
            title="Negative Feedback Detected",
            message=f"New negative feedback from {feedback.source.value}: {feedback.content[:100]}...",
            severity=Priority.HIGH,
            related_ids=[feedback.id],
        )
        await insert_alert_and_broadcast(alert, org_id=feedback.org_id)

        priority = Priority.MEDIUM
        if analysis.confidence >= 0.9:
            priority = Priority.CRITICAL
        elif analysis.confidence >= 0.8:
            priority = Priority.HIGH

        case = Case(
            feedback_id=feedback.id,
            title=f"Issue: {feedback.content[:50]}...",
            description=feedback.content,
            priority=priority,
        )
        case.org_id = feedback.org_id
        sla_hours = await get_sla_hours_for_priority(case.priority, org_id=feedback.org_id)
        case.due_date = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

        case_dict = case.model_dump()
        case_dict["created_at"] = case_dict["created_at"].isoformat()
        case_dict["updated_at"] = case_dict["updated_at"].isoformat()
        if case_dict.get("due_date"):
            case_dict["due_date"] = case_dict["due_date"].isoformat()

        await db.cases.insert_one(case_dict)
        await db.feedbacks.update_one({"id": feedback.id, "org_id": org_id}, {"$set": {"case_id": case.id}})
        feedback.case_id = case.id

        await log_case_action(
            case.id,
            "created",
            f"Auto-created case from negative feedback {feedback.id}",
            created_by=user["sub"],
            metadata={"auto": True, "priority": case.priority.value, "sla_hours": sla_hours},
            org_id=org_id,
        )

        case_alert = Alert(
            type="case_created",
            title="Case Auto-Created",
            message=f"A case was auto-created from negative feedback ({case.priority.value}): {case.title}",
            severity=Priority.HIGH if case.priority in [Priority.HIGH, Priority.CRITICAL] else Priority.MEDIUM,
            related_ids=[case.id, feedback.id],
        )
        await insert_alert_and_broadcast(case_alert, org_id=case.org_id)

        assigned = await auto_assign_case_rules(case_dict)
        if assigned:
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.cases.update_one(
                {"id": case.id, "org_id": org_id},
                {"$set": {
                    "assigned_to": assigned["agent"]["id"],
                    "assigned_by": "auto_rules",
                    "status": CaseStatus.ASSIGNED.value,
                    "updated_at": now_iso,
                }},
            )
            await adjust_agent_workload(org_id, assigned["agent"]["id"], delta=+1)
            await log_case_action(
                case.id,
                "auto_assigned",
                f"Auto-assigned to {assigned['agent'].get('name','')}",
                created_by="system",
                metadata={"assigned_to": assigned["agent"]["id"]},
                org_id=org_id,
            )
            auto_assign_alert = Alert(
                type="case_auto_assigned",
                title="Case Auto-Assigned",
                message=f"Case '{case.title[:80]}' auto-assigned to {assigned['agent'].get('name','agent')}.",
                severity=Priority.MEDIUM,
                related_ids=[case.id],
            )
            await insert_alert_and_broadcast(auto_assign_alert, org_id=case.org_id)

    return feedback


@api_router.post("/dev/dummy-feedback/batch", response_model=DummyFeedbackBatchResponse)
async def generate_dummy_feedback_batch(payload: DummyFeedbackBatchRequest, request: Request, user: Dict = Depends(get_current_user)):
    """
    Generate a batch of dummy feedback items.
    Target: 10 per second usage from UI. Enforces 55–60% negative/constructive by choosing
    5 or 6 negatives for batches of 10 (alternating via time parity => averages ~55%).
    """
    if not has_permission(user.get("role"), Permission.FEEDBACK_BULK_CREATE.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    use_hf = bool(HF_TOKEN and InferenceClient)

    count = int(payload.count or 10)
    if count < 1 or count > 50:
        raise HTTPException(status_code=400, detail="count must be between 1 and 50")

    neg_min = float(payload.negative_min or 0.55)
    neg_max = float(payload.negative_max or 0.60)
    if not (0.0 <= neg_min <= 1.0 and 0.0 <= neg_max <= 1.0 and neg_min <= neg_max):
        raise HTTPException(status_code=400, detail="invalid negative_min/negative_max")

    org_id = get_org_id(user)

    # For count=10, enforce 55–60%: alternate 6 (60%) and 5 (50%) => avg ~55%.
    if count == 10:
        negative_target = 6 if int(time.time()) % 2 == 0 else 5
    else:
        target_ratio = (neg_min + neg_max) / 2.0
        negative_target = max(0, min(count, int(round(count * target_ratio))))

    created: List[Feedback] = []
    now = datetime.now(timezone.utc)

    async def make_one(force_sentiment: str) -> Feedback:
        # If HF is configured, use LLM generation; otherwise fallback to templates
        if use_hf:
            seed = str(uuid.uuid4())
            data = await hf_chat_json(
                system=(
                    "Generate ONE realistic customer feedback item for a SaaS product and its sentiment analysis. "
                    "Return ONLY valid JSON with keys:\n"
                    "- content: string (1-3 sentences)\n"
                    "- source: one of (twitter, facebook, youtube, website, support_ticket, email, survey, manual)\n"
                    "- author_name: string\n"
                    "- sentiment: one of (positive, neutral, negative)\n"
                    "- confidence: float 0..1\n"
                    "- emotions: array of strings\n"
                    "- themes: array of strings\n"
                    "- key_phrases: array of strings\n"
                    "- sarcasm_detected: boolean\n\n"
                    f"Rules:\n- sentiment must be '{force_sentiment}'\n"
                    "- If sentiment is negative, make it constructive/actionable.\n"
                ),
                user=f"seed={seed}. Topic variety: billing, bugs, UX, performance, support, security, features.",
            )
        else:
            # Template fallback for Docker runs without HF_TOKEN
            neg_templates = [
                "The app feels slow during peak hours and the dashboard often times out. Please optimize performance or provide a lighter view.",
                "I was billed twice this month and support hasn’t resolved it yet. Please refund the duplicate charge and confirm billing logic.",
                "Search is unreliable—it misses obvious matches. Can you improve indexing and add filters?",
                "The latest update broke notifications. Please fix and share a workaround until patched.",
                "Export to CSV fails for large datasets. Please add chunked exports or background jobs.",
            ]
            neu_templates = [
                "Overall the product is fine, but onboarding could be clearer. A short guided tour would help.",
                "I’m neutral on the new UI—looks cleaner but takes extra clicks. Maybe add compact mode.",
                "Support responded quickly, but the solution was incomplete. Please follow up with next steps.",
            ]
            pos_templates = [
                "Great experience so far—setup was quick and the insights are genuinely useful. Keep it up!",
                "Love the new dashboard design. It’s fast and the charts are easy to understand.",
                "Excellent support—my issue was resolved in one message. Thank you!",
            ]
            srcs = ["twitter", "facebook", "youtube", "website", "support_ticket", "email", "survey", "manual"]
            authors = ["Alex", "Priya", "Jordan", "Sam", "Taylor", "Aman", "Riya", "Dev Team"]
            pool = neg_templates if force_sentiment == "negative" else (pos_templates if force_sentiment == "positive" else neu_templates)
            content = pool[int(time.time() * 1000) % len(pool)]
            data = {
                "content": content,
                "source": srcs[int(time.time() * 1000) % len(srcs)],
                "author_name": authors[int(time.time() * 1000) % len(authors)],
                "sentiment": force_sentiment,
                "confidence": 0.85 if force_sentiment == "negative" else 0.7,
                "emotions": (["frustration"] if force_sentiment == "negative" else (["joy"] if force_sentiment == "positive" else ["neutral"])),
                "themes": (["performance", "billing"] if force_sentiment == "negative" else (["product", "ux"] if force_sentiment == "positive" else ["ux"])),
                "key_phrases": [],
                "sarcasm_detected": False,
            }

        content = (data.get("content") or "").strip()
        if not content:
            raise RuntimeError("LLM did not generate content")

        source_raw = (data.get("source") or "manual").strip().lower()
        if source_raw not in {s.value for s in FeedbackSource}:
            source_raw = "manual"

        author_name = (data.get("author_name") or "Customer").strip()[:80]

        sentiment_raw = (data.get("sentiment") or force_sentiment).strip().lower()
        if sentiment_raw not in {SentimentType.POSITIVE.value, SentimentType.NEUTRAL.value, SentimentType.NEGATIVE.value}:
            sentiment_raw = force_sentiment

        try:
            confidence = float(data.get("confidence", 0.75 if sentiment_raw == "negative" else 0.6))
        except Exception:
            confidence = 0.6

        analysis = SentimentAnalysis(
            sentiment=SentimentType(sentiment_raw),
            confidence=max(0.0, min(1.0, confidence)),
            emotions=data.get("emotions", []) or [],
            themes=data.get("themes", []) or [],
            key_phrases=data.get("key_phrases", []) or [],
            sarcasm_detected=bool(data.get("sarcasm_detected", False)),
        )

        fb = Feedback(content=content, source=FeedbackSource(source_raw), author_name=author_name)
        fb.org_id = org_id
        fb.analysis = analysis
        fb.is_processed = True
        fb.created_at = now
        return fb

    async def persist_and_apply_rules(fb: Feedback):
        fb_dict = fb.model_dump()
        fb_dict["created_at"] = now.isoformat()
        await db.feedbacks.insert_one(fb_dict)

        try:
            a = fb.analysis
            await monitoring.record(org_id, a.sentiment.value if a and hasattr(a.sentiment, "value") else str(a.sentiment), (a.themes if a else []) or [])
        except Exception:
            pass

        # Run the same downstream logic as create_feedback for negative items
        analysis = fb.analysis
        if analysis and analysis.sentiment == SentimentType.NEGATIVE and analysis.confidence > 0.7:
            alert = Alert(
                type="negative_feedback",
                title="Negative Feedback Detected",
                message=f"New negative feedback from {fb.source.value}: {fb.content[:100]}...",
                severity=Priority.HIGH,
                related_ids=[fb.id],
            )
            await insert_alert_and_broadcast(alert, org_id=org_id)

            priority = Priority.MEDIUM
            if analysis.confidence >= 0.9:
                priority = Priority.CRITICAL
            elif analysis.confidence >= 0.8:
                priority = Priority.HIGH

            case = Case(
                feedback_id=fb.id,
                title=f"Issue: {fb.content[:50]}...",
                description=fb.content,
                priority=priority,
            )
            case.org_id = org_id
            sla_hours = await get_sla_hours_for_priority(case.priority, org_id=org_id)
            case.due_date = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

            case_dict = case.model_dump()
            case_dict["created_at"] = case_dict["created_at"].isoformat()
            case_dict["updated_at"] = case_dict["updated_at"].isoformat()
            if case_dict.get("due_date"):
                case_dict["due_date"] = case_dict["due_date"].isoformat()

            await db.cases.insert_one(case_dict)
            await db.feedbacks.update_one({"id": fb.id, "org_id": org_id}, {"$set": {"case_id": case.id}})
            fb.case_id = case.id

            await log_case_action(
                case.id,
                "created",
                f"Auto-created case from negative feedback {fb.id}",
                created_by=user["sub"],
                metadata={"auto": True, "priority": case.priority.value, "sla_hours": sla_hours},
                org_id=org_id,
            )

            case_alert = Alert(
                type="case_created",
                title="Case Auto-Created",
                message=f"A case was auto-created from negative feedback ({case.priority.value}): {case.title}",
                severity=Priority.HIGH if case.priority in [Priority.HIGH, Priority.CRITICAL] else Priority.MEDIUM,
                related_ids=[case.id, fb.id],
            )
            await insert_alert_and_broadcast(case_alert, org_id=org_id)

            assigned = await auto_assign_case_rules(case_dict)
            if assigned:
                now_iso = datetime.now(timezone.utc).isoformat()
                await db.cases.update_one(
                    {"id": case.id, "org_id": org_id},
                    {"$set": {
                        "assigned_to": assigned["agent"]["id"],
                        "assigned_by": "auto_rules",
                        "status": CaseStatus.ASSIGNED.value,
                        "updated_at": now_iso,
                    }},
                )
                await adjust_agent_workload(org_id, assigned["agent"]["id"], delta=+1)
                await log_case_action(
                    case.id,
                    "auto_assigned",
                    f"Auto-assigned to {assigned['agent'].get('name','')}",
                    created_by="system",
                    metadata={"assigned_to": assigned["agent"]["id"]},
                    org_id=org_id,
                )
                auto_assign_alert = Alert(
                    type="case_auto_assigned",
                    title="Case Auto-Assigned",
                    message=f"Case '{case.title[:80]}' auto-assigned to {assigned['agent'].get('name','agent')}.",
                    severity=Priority.MEDIUM,
                    related_ids=[case.id],
                )
                await insert_alert_and_broadcast(auto_assign_alert, org_id=org_id)

    # Generate negatives + non-negatives
    sentiments: List[str] = (["negative"] * negative_target) + (["neutral"] * (count - negative_target))
    # If there is room, swap a couple neutrals to positives for variety
    for i in range(len(sentiments)):
        if sentiments[i] == "neutral" and i % 3 == 0:
            sentiments[i] = "positive"

    # Best-effort concurrency without overloading HF
    sem = asyncio.Semaphore(3)
    async def guarded_make(s: str):
        async with sem:
            return await make_one(s)

    made = await asyncio.gather(*[guarded_make(s) for s in sentiments], return_exceptions=True)
    for m in made:
        if isinstance(m, Exception):
            continue
        fb = m
        await persist_and_apply_rules(fb)
        created.append(fb)

    resp = DummyFeedbackBatchResponse(created=len(created), negative_target=negative_target, items=created)
    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="dev_dummy_feedback_batch",
        resource_type="feedback",
        request=request,
        status_code=200,
        metadata={"count": count, "negative_target": negative_target, "created": resp.created},
    )
    return resp


# ============== INGESTION ROUTES (FOUNDATIONAL) ==============
@api_router.post("/ingest", response_model=IngestResponse)
async def ingest_feedback(req: IngestRequest, request: Request, user: Dict = Depends(get_current_user)):
    """
    Foundational ingestion endpoint:
    - stores RAW payload (db.raw_feedback)
    - stores NORMALIZED payload (db.normalized_feedback)
    - creates a standard Feedback record (db.feedbacks) by reusing existing business logic
    This keeps existing features intact while adding enterprise ingestion primitives.
    """
    # For now, protect ingestion with JWT roles; can be extended to API keys/webhooks later.
    if not has_permission(user.get("role"), Permission.FEEDBACK_INGEST.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    org_id = get_org_id(user)
    normalized = await ingestion_service.ingest(org_id=org_id, source=req.source, payload=req.payload)

    # Create standard Feedback using the existing pipeline
    fb_create = FeedbackCreate(
        content=normalized.content,
        source=FeedbackSource(normalized.source) if normalized.source in {s.value for s in FeedbackSource} else FeedbackSource.MANUAL,
        author_name=normalized.author_name,
        author_id=normalized.author_id,
        metadata={**(normalized.metadata or {}), "external_id": normalized.external_id, "normalized_id": normalized.id, "raw_ref_id": normalized.raw_ref_id},
    )
    fb = await create_feedback(fb_create, user=user)

    # Also store an analyzed copy for historical pipeline layering
    try:
        await db.analyzed_feedback.insert_one({
            "id": fb.id,
            "org_id": org_id,
            "feedback_id": fb.id,
            "normalized_id": normalized.id,
            "raw_ref_id": normalized.raw_ref_id,
            "created_at": fb.created_at.isoformat() if isinstance(fb.created_at, datetime) else fb.created_at,
            "analysis": (fb.analysis.model_dump() if fb.analysis else None),
            "content": fb.content,
            "source": fb.source.value if hasattr(fb.source, "value") else fb.source,
        })
    except Exception:
        pass

    resp = IngestResponse(
        raw_id=normalized.raw_ref_id,
        normalized_id=normalized.id,
        feedback_id=fb.id,
        case_id=fb.case_id,
    )
    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="feedback_ingest",
        resource_type="ingestion",
        resource_id=normalized.id,
        request=request,
        status_code=200,
        metadata={"source": req.source, "feedback_id": fb.id, "case_id": fb.case_id},
    )
    return resp


@api_router.post("/ingest/website", response_model=IngestResponse)
async def ingest_website(payload: Dict[str, Any], user: Dict = Depends(get_current_user)):
    return await ingest_feedback(IngestRequest(source="website", payload=payload), user=user)


@api_router.post("/ingest/support-ticket", response_model=IngestResponse)
async def ingest_support_ticket(payload: Dict[str, Any], user: Dict = Depends(get_current_user)):
    # Example payloads: zendesk/freshdesk/service-now; normalized extractor handles common fields.
    return await ingest_feedback(IngestRequest(source="support_ticket", payload=payload), user=user)


# ============== MONITORING ROUTES (REAL-TIME) ==============
@api_router.get("/monitoring/live", response_model=MonitoringLiveResponse)
async def monitoring_live(user: Dict = Depends(get_current_user)):
    """
    Live dashboard snapshot from in-memory rolling windows.
    If the server was restarted recently, counters will rebuild as new events arrive.
    """
    org_id = get_org_id(user)
    snap = await monitoring.snapshot(org_id)
    return snap

@api_router.post("/feedback/bulk", response_model=List[Feedback])
async def bulk_create_feedback(data: BulkFeedbackUpload, user: Dict = Depends(get_current_user)):
    feedbacks = []
    for fb_data in data.feedbacks:
        feedback = Feedback(**fb_data.model_dump())
        feedback.org_id = get_org_id(user)
        analysis = await analyze_feedback_with_ai(feedback.content)
        feedback.analysis = analysis
        feedback.is_processed = True
        
        feedback_dict = feedback.model_dump()
        feedback_dict["created_at"] = feedback_dict["created_at"].isoformat()
        await db.feedbacks.insert_one(feedback_dict)
        feedbacks.append(feedback)

        try:
            await monitoring.record(
                feedback.org_id,
                (analysis.sentiment.value if hasattr(analysis.sentiment, "value") else str(analysis.sentiment)),
                analysis.themes or [],
            )
        except Exception:
            pass
    
    return feedbacks

@api_router.get("/feedback", response_model=List[Feedback])
async def get_feedbacks(
    skip: int = 0,
    limit: int = 50,
    source: Optional[FeedbackSource] = None,
    sentiment: Optional[SentimentType] = None,
    user: Dict = Depends(get_current_user)
):
    query = {"org_id": get_org_id(user)}
    if source:
        query["source"] = source.value
    if sentiment:
        query["analysis.sentiment"] = sentiment.value
    
    feedbacks = await db.feedbacks.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    for fb in feedbacks:
        if isinstance(fb.get("created_at"), str):
            fb["created_at"] = datetime.fromisoformat(fb["created_at"])
    
    return feedbacks

@api_router.get("/feedback/{feedback_id}", response_model=Feedback)
async def get_feedback(feedback_id: str, user: Dict = Depends(get_current_user)):
    feedback = await db.feedbacks.find_one({"id": feedback_id, "org_id": get_org_id(user)}, {"_id": 0})
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    if isinstance(feedback.get("created_at"), str):
        feedback["created_at"] = datetime.fromisoformat(feedback["created_at"])
    return feedback

@api_router.post("/feedback/{feedback_id}/analyze", response_model=Feedback)
async def reanalyze_feedback(feedback_id: str, user: Dict = Depends(get_current_user)):
    feedback = await db.feedbacks.find_one({"id": feedback_id, "org_id": get_org_id(user)}, {"_id": 0})
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    analysis = await analyze_feedback_with_ai(feedback["content"])
    await db.feedbacks.update_one(
        {"id": feedback_id, "org_id": get_org_id(user)},
        {"$set": {"analysis": analysis.model_dump(), "is_processed": True}}
    )
    
    feedback["analysis"] = analysis.model_dump()
    feedback["is_processed"] = True
    if isinstance(feedback.get("created_at"), str):
        feedback["created_at"] = datetime.fromisoformat(feedback["created_at"])
    return feedback

# ============== CASES (CFL) ROUTES ==============
@api_router.post("/cases", response_model=Case)
async def create_case(case_data: CaseCreate, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    feedback = await db.feedbacks.find_one({"id": case_data.feedback_id, "org_id": org_id}, {"_id": 0})
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    case = Case(**case_data.model_dump())
    case.org_id = org_id
    sla_hours = await get_sla_hours_for_priority(case.priority, org_id=org_id)
    case.due_date = datetime.now(timezone.utc) + timedelta(hours=sla_hours)
    case.verification_status = None
    
    case_dict = case.model_dump()
    case_dict["created_at"] = case_dict["created_at"].isoformat()
    case_dict["updated_at"] = case_dict["updated_at"].isoformat()
    if case_dict["due_date"]:
        case_dict["due_date"] = case_dict["due_date"].isoformat()
    
    await db.cases.insert_one(case_dict)
    await db.feedbacks.update_one({"id": case_data.feedback_id, "org_id": org_id}, {"$set": {"case_id": case.id}})

    await log_case_action(
        case.id,
        "created",
        f"Case created from feedback {case_data.feedback_id}",
        created_by=user["sub"],
        metadata={"priority": case.priority.value, "sla_hours": sla_hours},
    )
    
    return case

@api_router.get("/cases", response_model=List[Case])
async def get_cases(
    skip: int = 0,
    limit: int = 50,
    status: Optional[CaseStatus] = None,
    priority: Optional[Priority] = None,
    assigned_to: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    query = {"org_id": get_org_id(user)}
    if status:
        query["status"] = status.value
    if priority:
        query["priority"] = priority.value
    if assigned_to:
        query["assigned_to"] = assigned_to
    
    cases = await db.cases.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    for c in cases:
        for field in ["created_at", "updated_at", "due_date"]:
            if c.get(field) and isinstance(c[field], str):
                c[field] = datetime.fromisoformat(c[field])
    
    return cases

@api_router.get("/cases/{case_id}", response_model=Case)
async def get_case(case_id: str, user: Dict = Depends(get_current_user)):
    case = await db.cases.find_one({"id": case_id, "org_id": get_org_id(user)}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    for field in ["created_at", "updated_at", "due_date"]:
        if case.get(field) and isinstance(case[field], str):
            case[field] = datetime.fromisoformat(case[field])
    return case

@api_router.put("/cases/{case_id}/assign")
async def assign_case(case_id: str, assignee_id: str, request: Request, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    if not has_permission(user.get("role"), Permission.CASE_ASSIGN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    case = await db.cases.find_one({"id": case_id, "org_id": org_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    prev_assignee = case.get("assigned_to")
    await db.cases.update_one(
        {"id": case_id, "org_id": org_id},
        {"$set": {
            "assigned_to": assignee_id,
            "assigned_by": user["sub"],
            "status": CaseStatus.ASSIGNED.value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    if prev_assignee and prev_assignee != assignee_id:
        await adjust_agent_workload(org_id, prev_assignee, delta=-1)
    if assignee_id:
        await adjust_agent_workload(org_id, assignee_id, delta=+1)
    
    await log_case_action(
        case_id,
        "assigned",
        f"Case assigned to {assignee_id}",
        created_by=user["sub"],
        metadata={"assigned_to": assignee_id, "from_status": case.get("status"), "to_status": CaseStatus.ASSIGNED.value},
    )

    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="case_assign",
        resource_type="case",
        resource_id=case_id,
        request=request,
        status_code=200,
        before={"assigned_to": prev_assignee, "status": case.get("status")},
        after={"assigned_to": assignee_id, "status": CaseStatus.ASSIGNED.value},
        metadata={"assignee_id": assignee_id},
    )
    
    return {"message": "Case assigned successfully"}


@api_router.put("/cases/{case_id}/start")
async def start_case_work(case_id: str, request: Request, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    case = await db.cases.find_one({"id": case_id, "org_id": org_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Only assignee (or admin/manager) can start work
    if user.get("role") not in ["admin", "manager"] and case.get("assigned_to") != user.get("sub"):
        raise HTTPException(status_code=403, detail="Only the assignee can start work on this case")

    await db.cases.update_one(
        {"id": case_id, "org_id": org_id},
        {"$set": {"status": CaseStatus.IN_PROGRESS.value, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    await log_case_action(
        case_id,
        "started",
        "Work started on case",
        created_by=user["sub"],
        metadata={"from_status": case.get("status"), "to_status": CaseStatus.IN_PROGRESS.value},
    )

    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="case_start",
        resource_type="case",
        resource_id=case_id,
        request=request,
        status_code=200,
        before={"status": case.get("status")},
        after={"status": CaseStatus.IN_PROGRESS.value},
    )

    return {"message": "Case marked as in progress"}

@api_router.put("/cases/{case_id}/resolve")
async def resolve_case(case_id: str, resolution_notes: str, request: Request, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    case = await db.cases.find_one({"id": case_id, "org_id": org_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if user.get("role") not in ["admin", "manager"] and case.get("assigned_to") not in [None, user.get("sub")]:
        raise HTTPException(status_code=403, detail="Only the assignee can resolve this case")
    
    await db.cases.update_one(
        {"id": case_id, "org_id": org_id},
        {"$set": {
            "status": CaseStatus.RESOLVED.value,
            "resolution_notes": resolution_notes,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "verification_status": "pending",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    await log_case_action(
        case_id,
        "resolved",
        resolution_notes,
        created_by=user["sub"],
        metadata={"from_status": case.get("status"), "to_status": CaseStatus.RESOLVED.value},
    )

    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="case_resolve",
        resource_type="case",
        resource_id=case_id,
        request=request,
        status_code=200,
        metadata={"resolution_notes_preview": (resolution_notes or "")[:200]},
    )
    
    return {"message": "Case resolved successfully"}


@api_router.post("/cases/{case_id}/verify", response_model=Survey)
async def verify_case(case_id: str, survey_data: SurveyBase, request: Request, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    case = await db.cases.find_one({"id": case_id, "org_id": org_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if survey_data.case_id != case_id:
        raise HTTPException(status_code=400, detail="case_id mismatch")

    survey = Survey(**survey_data.model_dump())
    survey.org_id = org_id
    survey_dict = survey.model_dump()
    survey_dict["created_at"] = survey_dict["created_at"].isoformat()
    await db.surveys.insert_one(survey_dict)

    now_iso = datetime.now(timezone.utc).isoformat()
    passed = survey.rating >= 4
    new_status = CaseStatus.CLOSED.value if passed else CaseStatus.IN_PROGRESS.value
    verification_status = "passed" if passed else "failed"

    await db.cases.update_one(
        {"id": case_id, "org_id": org_id},
        {"$set": {
            "verification_status": verification_status,
            "verification_rating": survey.rating,
            "verified_at": now_iso,
            "status": new_status,
            "updated_at": now_iso,
        }},
    )

    await log_case_action(
        case_id,
        "verified",
        f"Customer verification recorded (rating {survey.rating}/5)",
        created_by=user["sub"],
        metadata={
            "rating": survey.rating,
            "verification_status": verification_status,
            "from_status": case.get("status"),
            "to_status": new_status,
        },
    )

    # Workload accounting: when a case is closed, decrement assignee workload and increment resolved count.
    if passed and case.get("assigned_to"):
        await adjust_agent_workload(org_id, case["assigned_to"], delta=-1, resolved_delta=+1)

    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="case_verify",
        resource_type="case",
        resource_id=case_id,
        request=request,
        status_code=200,
        metadata={"rating": survey.rating, "passed": passed, "new_status": new_status},
    )

    return survey


@api_router.post("/cases/{case_id}/evidence", response_model=CaseEvidence)
async def upload_case_evidence(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    note: Optional[str] = Form(default=None),
    user: Dict = Depends(get_current_user),
):
    org_id = get_org_id(user)
    case = await db.cases.find_one({"id": case_id, "org_id": org_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Only assigned agent/manager/admin can upload evidence
    if user.get("role") not in ["admin", "manager"] and case.get("assigned_to") not in [None, user.get("sub")]:
        raise HTTPException(status_code=403, detail="Only the assignee can upload evidence")

    original = file.filename or "evidence"
    ext = ""
    if "." in original:
        ext = "." + original.split(".")[-1]
    safe_name = f"{case_id}-{uuid.uuid4()}{ext}"
    dest = UPLOADS_DIR / safe_name

    size_bytes: Optional[int] = None
    with dest.open("wb") as buffer:
        copied = shutil.copyfileobj(file.file, buffer)
        # shutil.copyfileobj returns None; determine size from filesystem
    try:
        size_bytes = dest.stat().st_size
    except Exception:
        size_bytes = None

    evidence = CaseEvidence(
        filename=safe_name,
        original_filename=original,
        content_type=file.content_type,
        size_bytes=size_bytes,
        url=f"/uploads/{safe_name}",
        uploaded_by=user["sub"],
        note=note,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.cases.update_one(
        {"id": case_id, "org_id": org_id},
        {"$push": {"evidence": {**evidence.model_dump(), "uploaded_at": evidence.uploaded_at.isoformat()}}, "$set": {"updated_at": now_iso}},
    )

    await log_case_action(
        case_id,
        "evidence_uploaded",
        f"Evidence uploaded: {original}",
        created_by=user["sub"],
        metadata={"evidence_id": evidence.id, "url": evidence.url, "note": note},
    )

    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="case_evidence_upload",
        resource_type="case",
        resource_id=case_id,
        request=request,
        status_code=200,
        metadata={"evidence_id": evidence.id, "filename": original, "note": note},
    )

    return evidence

@api_router.get("/cases/{case_id}/logs", response_model=List[ResolutionLog])
async def get_case_logs(case_id: str, user: Dict = Depends(get_current_user)):
    logs = await db.resolution_logs.find({"case_id": case_id, "org_id": get_org_id(user)}, {"_id": 0}).sort("created_at", -1).to_list(100)
    for log in logs:
        if isinstance(log.get("created_at"), str):
            log["created_at"] = datetime.fromisoformat(log["created_at"])
    return logs

# ============== SURVEYS ROUTES ==============
@api_router.post("/surveys", response_model=Survey)
async def create_survey(survey_data: SurveyBase, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    case = await db.cases.find_one({"id": survey_data.case_id, "org_id": org_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    survey = Survey(**survey_data.model_dump())
    survey.org_id = org_id
    survey_dict = survey.model_dump()
    survey_dict["created_at"] = survey_dict["created_at"].isoformat()
    
    await db.surveys.insert_one(survey_dict)
    
    # Verification behavior (CFL v2):
    # rating >= 4: close case, else re-open to in_progress
    now_iso = datetime.now(timezone.utc).isoformat()
    passed = survey_data.rating >= 4
    new_status = CaseStatus.CLOSED.value if passed else CaseStatus.IN_PROGRESS.value
    verification_status = "passed" if passed else "failed"
    await db.cases.update_one(
        {"id": survey_data.case_id, "org_id": org_id},
        {"$set": {
            "status": new_status,
            "verification_status": verification_status,
            "verification_rating": survey_data.rating,
            "verified_at": now_iso,
            "updated_at": now_iso,
        }}
    )
    await log_case_action(
        survey_data.case_id,
        "verified",
        f"Survey recorded (rating {survey_data.rating}/5)",
        created_by=user["sub"],
        metadata={"rating": survey_data.rating, "verification_status": verification_status, "to_status": new_status},
    )

    if passed and case.get("assigned_to"):
        await adjust_agent_workload(org_id, case["assigned_to"], delta=-1, resolved_delta=+1)
    
    return survey

@api_router.get("/surveys", response_model=List[Survey])
async def get_surveys(skip: int = 0, limit: int = 50, user: Dict = Depends(get_current_user)):
    surveys = await db.surveys.find({"org_id": get_org_id(user)}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    for s in surveys:
        if isinstance(s.get("created_at"), str):
            s["created_at"] = datetime.fromisoformat(s["created_at"])
    return surveys

# ============== ALERTS ROUTES ==============
@api_router.get("/alerts", response_model=List[Alert])
async def get_alerts(unread_only: bool = False, user: Dict = Depends(get_current_user)):
    query = {"org_id": get_org_id(user), "is_read": False} if unread_only else {"org_id": get_org_id(user)}
    alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    for a in alerts:
        if isinstance(a.get("created_at"), str):
            a["created_at"] = datetime.fromisoformat(a["created_at"])
    return alerts


# ============== AUDIT ROUTES ==============
@api_router.post("/audit", response_model=List[AuditEvent])
async def query_audit_events(q: AuditQuery, user: Dict = Depends(get_current_user)):
    if not has_permission(user.get("role"), Permission.AUDIT_READ.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    org_id = get_org_id(user)

    query: Dict[str, Any] = {"org_id": org_id}
    if q.actor_id:
        query["actor_id"] = q.actor_id
    if q.action:
        query["action"] = q.action
    if q.resource_type:
        query["resource_type"] = q.resource_type
    if q.resource_id:
        query["resource_id"] = q.resource_id
    if q.since or q.until:
        ts_q: Dict[str, Any] = {}
        if q.since:
            ts_q["$gte"] = q.since
        if q.until:
            ts_q["$lte"] = q.until
        query["ts"] = ts_q

    docs = await db.audit_events.find(query, {"_id": 0}).sort("ts", -1).limit(int(q.limit)).to_list(int(q.limit))
    return [AuditEvent(**d) for d in docs]


# ============== AGENTIC AI ROUTES ==============
@api_router.post("/agentic/triage/feedback/{feedback_id}", response_model=AgenticTriageResult)
async def agentic_triage_feedback(feedback_id: str, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    fb = await db.feedbacks.find_one({"id": feedback_id, "org_id": org_id}, {"_id": 0})
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")

    content = fb.get("content", "")
    triage = await agentic_triage_text(content)

    result = AgenticTriageResult(
        feedback_id=feedback_id,
        case_id=fb.get("case_id"),
        category=TriageCategory(triage["category"]),
        suggested_priority=Priority(triage["suggested_priority"]),
        required_skills=triage.get("required_skills", []),
        summary=triage.get("summary", "Customer issue reported"),
        recommended_actions=triage.get("recommended_actions", []),
        confidence=float(triage.get("confidence", 0.65)),
        created_by=user["sub"],
    )

    doc = result.model_dump()
    doc["org_id"] = org_id
    doc["created_at"] = result.created_at.isoformat()
    await db.agentic_triage.insert_one(doc)

    # If a case exists, optionally raise its priority (never lower)
    if fb.get("case_id"):
        case = await db.cases.find_one({"id": fb["case_id"], "org_id": org_id}, {"_id": 0})
        if case:
            current = case.get("priority", Priority.MEDIUM.value)
            order = {Priority.LOW.value: 0, Priority.MEDIUM.value: 1, Priority.HIGH.value: 2, Priority.CRITICAL.value: 3}
            if order.get(result.suggested_priority.value, 1) > order.get(current, 1):
                await db.cases.update_one({"id": fb["case_id"], "org_id": org_id}, {"$set": {"priority": result.suggested_priority.value, "updated_at": datetime.now(timezone.utc).isoformat()}})
                await log_case_action(fb["case_id"], "triaged", f"AI triage suggested priority {result.suggested_priority.value}", created_by=user["sub"])

    return result


@api_router.post("/agentic/response/case/{case_id}", response_model=AgenticResponseDraft)
async def agentic_response_case(case_id: str, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    case = await db.cases.find_one({"id": case_id, "org_id": org_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    fb = await db.feedbacks.find_one({"id": case.get("feedback_id"), "org_id": org_id}, {"_id": 0})
    feedback_text = fb.get("content", "") if fb else ""
    draft = await agentic_response_draft(case.get("title", ""), case.get("description", "") or "", feedback_text)

    result = AgenticResponseDraft(
        case_id=case_id,
        customer_reply=draft["customer_reply"],
        internal_note=draft["internal_note"],
        created_by=user["sub"],
    )
    doc = result.model_dump()
    doc["org_id"] = org_id
    doc["created_at"] = result.created_at.isoformat()
    await db.agentic_responses.insert_one(doc)

    await log_case_action(case_id, "ai_draft_created", "AI response draft generated", created_by=user["sub"])
    return result


# ============== ORCHESTRATION ROUTES (PHASE C) ==============
@api_router.post("/agentic/orchestrations/case/{case_id}", response_model=OrchestrationRun)
async def start_case_orchestration(case_id: str, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    case = await db.cases.find_one({"id": case_id, "org_id": org_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    existing = await db.agentic_runs.find_one(
        {
            "org_id": org_id,
            "case_id": case_id,
            "status": {"$in": [OrchestrationRunStatus.RUNNING.value, OrchestrationRunStatus.WAITING_FOR_APPROVAL.value]},
        },
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if existing:
        return OrchestrationRun(**existing)

    steps = await _orchestration_build_steps()
    run = OrchestrationRun(
        org_id=org_id,
        case_id=case_id,
        feedback_id=case.get("feedback_id"),
        steps=steps,
        created_by=user["sub"],
        context={},
    )
    await _orchestration_persist_run(run)
    return await _orchestration_run_until_wait(run)


@api_router.get("/agentic/orchestrations/{run_id}", response_model=OrchestrationRun)
async def get_orchestration_run(run_id: str, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    return await _orchestration_load_run(org_id, run_id)


@api_router.post("/agentic/orchestrations/{run_id}/resume", response_model=OrchestrationRun)
async def resume_orchestration(run_id: str, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    run = await _orchestration_load_run(org_id, run_id)
    if run.status == OrchestrationRunStatus.WAITING_FOR_APPROVAL:
        return run
    run.status = OrchestrationRunStatus.RUNNING
    await _orchestration_persist_run(run)
    return await _orchestration_run_until_wait(run)


@api_router.post("/agentic/orchestrations/{run_id}/cancel", response_model=OrchestrationRun)
async def cancel_orchestration(run_id: str, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    run = await _orchestration_load_run(org_id, run_id)
    run.status = OrchestrationRunStatus.CANCELLED
    await _orchestration_persist_run(run)
    return run


@api_router.post("/agentic/orchestrations/{run_id}/gates/{step_key}", response_model=OrchestrationRun)
async def decide_orchestration_gate(run_id: str, step_key: str, decision: OrchestrationGateDecision, request: Request, user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    if not has_permission(user.get("role"), Permission.HITL_APPROVE.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    run = await _orchestration_load_run(org_id, run_id)
    step = _step_by_key(run, step_key)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    if not step.requires_approval:
        raise HTTPException(status_code=400, detail="Step is not a gate")
    if step.status != OrchestrationStepStatus.NEEDS_APPROVAL:
        raise HTTPException(status_code=400, detail="Gate is not waiting for approval")

    dec = (decision.decision or "").strip().lower()
    if dec not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="decision must be approve or reject")

    step.approved_by = user.get("sub")
    step.approved_at = _now_iso()
    step.approval_note = decision.note

    if dec == "approve":
        step.status = OrchestrationStepStatus.APPROVED
        if step.key == "gate_apply_priority":
            proposed = (step.output or {}).get("proposed_priority")
            if proposed in [p.value for p in Priority]:
                await db.cases.update_one(
                    {"id": run.case_id, "org_id": org_id},
                    {"$set": {"priority": proposed, "updated_at": _now_iso()}},
                )
                await log_case_action(
                    run.case_id,
                    "priority_updated",
                    f"Priority updated via HITL approval to {proposed}",
                    created_by=user["sub"],
                    metadata={"run_id": run.id, "step": step.key},
                    org_id=org_id,
                )
        elif step.key == "gate_apply_assign":
            proposed_agent_id = (step.output or {}).get("proposed_assignee_id")
            if proposed_agent_id:
                now_iso = _now_iso()
                await db.cases.update_one(
                    {"id": run.case_id, "org_id": org_id},
                    {"$set": {
                        "assigned_to": proposed_agent_id,
                        "assigned_by": "hitl_orchestration",
                        "status": CaseStatus.ASSIGNED.value,
                        "updated_at": now_iso,
                    }},
                )
                await adjust_agent_workload(org_id, proposed_agent_id, delta=+1)
                await log_case_action(
                    run.case_id,
                    "assigned",
                    f"Assigned via HITL orchestration to {proposed_agent_id}",
                    created_by=user["sub"],
                    metadata={"run_id": run.id, "step": step.key},
                    org_id=org_id,
                )
    else:
        step.status = OrchestrationStepStatus.REJECTED

    step.finished_at = _now_iso()

    run.status = OrchestrationRunStatus.RUNNING
    await _orchestration_persist_run(run)
    run = await _orchestration_run_until_wait(run)
    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="hitl_gate_decision",
        resource_type="agentic_run",
        resource_id=run_id,
        request=request,
        status_code=200,
        metadata={"step_key": step_key, "decision": dec, "note": decision.note, "case_id": run.case_id},
    )
    return run


@api_router.get("/agentic/executive/digest", response_model=ExecutiveDigest)
async def agentic_executive_digest(days: int = 7, user: Dict = Depends(get_current_user)):
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    org_id = get_org_id(user)
    feedbacks = await db.feedbacks.find({"org_id": org_id, "created_at": {"$gte": since.isoformat()}}, {"_id": 0, "analysis.sentiment": 1, "analysis.themes": 1}).to_list(5000)
    cases = await db.cases.find({"org_id": org_id, "created_at": {"$gte": since.isoformat()}}, {"_id": 0, "status": 1, "priority": 1}).to_list(5000)

    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    theme_counts: Dict[str, int] = {}
    for fb in feedbacks:
        s = (fb.get("analysis", {}) or {}).get("sentiment")
        if s in sentiment_counts:
            sentiment_counts[s] += 1
        for t in (fb.get("analysis", {}) or {}).get("themes", []) or []:
            theme_counts[t] = theme_counts.get(t, 0) + 1

    top_themes = [{"theme": k, "count": v} for k, v in sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:8]]

    open_like = sum(1 for c in cases if c.get("status") in ["open", "assigned", "in_progress", "escalated"])
    critical = sum(1 for c in cases if c.get("priority") == "critical")
    escalated = sum(1 for c in cases if c.get("status") == "escalated")

    risks = []
    if escalated > 0:
        risks.append(f"{escalated} escalated cases in last {days} days")
    if critical > 0:
        risks.append(f"{critical} critical cases created in last {days} days")
    if sentiment_counts["negative"] > 0:
        risks.append(f"{sentiment_counts['negative']} negative feedback items in last {days} days")

    recommended = [
        "Review escalated/critical cases and ensure owners + deadlines are set",
        "Identify top 1–2 themes driving negative sentiment and prioritize fixes",
        "Confirm SLA settings match operational capacity",
    ]

    summary = (
        f"Last {days} days: {sentiment_counts['negative']} negative feedback, "
        f"{open_like} open/active cases, {escalated} escalations."
    )

    digest = ExecutiveDigest(
        days=days,
        summary=summary,
        top_themes=top_themes,
        risks=risks,
        recommended_actions=recommended,
        created_by=user["sub"],
    )
    doc = digest.model_dump()
    doc["org_id"] = org_id
    doc["created_at"] = digest.created_at.isoformat()
    await db.agentic_exec_digests.insert_one(doc)
    return digest

@api_router.put("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, user: Dict = Depends(get_current_user)):
    await db.alerts.update_one({"id": alert_id, "org_id": get_org_id(user)}, {"$set": {"is_read": True}})
    return {"message": "Alert marked as read"}

@api_router.put("/alerts/read-all")
async def mark_all_alerts_read(user: Dict = Depends(get_current_user)):
    await db.alerts.update_many({"org_id": get_org_id(user)}, {"$set": {"is_read": True}})
    return {"message": "All alerts marked as read"}

# ============== USERS ROUTES ==============
@api_router.get("/users", response_model=List[User])
async def get_users(role: Optional[UserRole] = None, user: Dict = Depends(get_current_user)):
    query = {"org_id": get_org_id(user)}
    if role:
        query["role"] = role.value
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).to_list(1000)

    sanitized: List[Dict[str, Any]] = []
    for u in users:
        # Coerce legacy fields → current schema
        if "name" not in u and "full_name" in u:
            u["name"] = u.get("full_name")
        if "password" in u and "password_hash" not in u:
            # never expose raw password field; also avoids leaking on accidental schema drift
            u.pop("password", None)

        # Filter to supported roles only; skip incompatible legacy users
        role_value = u.get("role")
        if role_value not in {r.value for r in UserRole}:
            continue

        if isinstance(u.get("created_at"), str):
            try:
                u["created_at"] = datetime.fromisoformat(u["created_at"])
            except Exception:
                u["created_at"] = datetime.now(timezone.utc)

        # Ensure required fields exist for response_model
        if not u.get("id") or not u.get("email") or not u.get("name"):
            continue

        sanitized.append(u)

    return sanitized


# ============== ORG ROUTES (PHASE 4) ==============
@api_router.get("/orgs", response_model=List[Organization])
async def list_orgs(user: Dict = Depends(get_current_user)):
    if user.get("role") not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admins can list organizations")
    orgs = await db.organizations.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for o in orgs:
        if isinstance(o.get("created_at"), str):
            o["created_at"] = datetime.fromisoformat(o["created_at"])
    return orgs


@api_router.post("/orgs", response_model=Organization)
async def create_org(payload: OrganizationCreate, user: Dict = Depends(get_current_user)):
    if user.get("role") not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admins can create organizations")
    org = Organization(name=payload.name)
    doc = org.model_dump()
    doc["created_at"] = org.created_at.isoformat()
    await db.organizations.insert_one(doc)
    return org


@api_router.put("/orgs/{org_id}/users/{user_id}")
async def move_user_to_org(org_id: str, user_id: str, request: Request, user: Dict = Depends(get_current_user)):
    if not has_permission(user.get("role"), Permission.ORG_CREATE.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    org = await db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    before = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    result = await db.users.update_one({"id": user_id}, {"$set": {"org_id": org_id}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    after = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="user_org_change",
        resource_type="user",
        resource_id=user_id,
        request=request,
        status_code=200,
        before=before,
        after=after,
        metadata={"new_org_id": org_id},
    )
    return {"message": "User org updated"}

@api_router.put("/users/{user_id}/role")
async def update_user_role(user_id: str, new_role: UserRole, request: Request, current_user: Dict = Depends(get_current_user)):
    if not has_permission(current_user.get("role"), Permission.USER_ROLE_CHANGE.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    before = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    result = await db.users.update_one({"id": user_id}, {"$set": {"role": new_role.value}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    after = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    await write_audit_event(
        org_id=get_org_id(current_user),
        actor=current_user,
        action="user_role_change",
        resource_type="user",
        resource_id=user_id,
        request=request,
        status_code=200,
        before=before,
        after=after,
        metadata={"new_role": new_role.value},
    )
    return {"message": "Role updated successfully"}

# ============== TEAMS ROUTES ==============
@api_router.post("/teams", response_model=Team)
async def create_team(name: str, description: Optional[str] = None, user: Dict = Depends(get_current_user)):
    team = Team(name=name, description=description)
    team_dict = team.model_dump()
    team_dict["created_at"] = team_dict["created_at"].isoformat()
    await db.teams.insert_one(team_dict)
    return team

@api_router.get("/teams", response_model=List[Team])
async def get_teams(user: Dict = Depends(get_current_user)):
    teams = await db.teams.find({}, {"_id": 0}).to_list(100)
    for t in teams:
        if isinstance(t.get("created_at"), str):
            t["created_at"] = datetime.fromisoformat(t["created_at"])
    return teams

@api_router.put("/teams/{team_id}/members")
async def add_team_member(team_id: str, member_id: str, user: Dict = Depends(get_current_user)):
    await db.teams.update_one({"id": team_id}, {"$addToSet": {"members": member_id}})
    await db.users.update_one({"id": member_id}, {"$set": {"team_id": team_id}})
    return {"message": "Member added to team"}

# ============== ANALYTICS ROUTES ==============
@api_router.get("/analytics/overview")
async def get_analytics_overview(user: Dict = Depends(get_current_user)):
    total_feedback = await db.feedbacks.count_documents({})
    positive = await db.feedbacks.count_documents({"analysis.sentiment": "positive"})
    neutral = await db.feedbacks.count_documents({"analysis.sentiment": "neutral"})
    negative = await db.feedbacks.count_documents({"analysis.sentiment": "negative"})
    
    total_cases = await db.cases.count_documents({})
    open_cases = await db.cases.count_documents({"status": {"$in": ["open", "in_progress"]}})
    resolved_cases = await db.cases.count_documents({"status": {"$in": ["resolved", "closed"]}})
    
    # Calculate average survey rating
    surveys = await db.surveys.find({}, {"_id": 0, "rating": 1}).to_list(1000)
    avg_rating = sum(s["rating"] for s in surveys) / len(surveys) if surveys else 0
    
    # SLA compliance (simplified - percentage of cases not breached)
    breached_cases = await db.cases.count_documents({"sla_breached": True})
    sla_compliance = ((total_cases - breached_cases) / total_cases * 100) if total_cases > 0 else 100
    
    # Closure rate
    closure_rate = (resolved_cases / total_cases * 100) if total_cases > 0 else 0
    
    return {
        "feedback": {
            "total": total_feedback,
            "positive": positive,
            "neutral": neutral,
            "negative": negative,
            "positive_rate": (positive / total_feedback * 100) if total_feedback > 0 else 0
        },
        "cases": {
            "total": total_cases,
            "open": open_cases,
            "resolved": resolved_cases,
            "closure_rate": closure_rate
        },
        "kpis": {
            "csat": avg_rating,
            "sla_compliance": sla_compliance,
            "closure_rate": closure_rate
        }
    }

@api_router.get("/analytics/sentiment-trends")
async def get_sentiment_trends(days: int = 30, user: Dict = Depends(get_current_user)):
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    feedbacks = await db.feedbacks.find(
        {"created_at": {"$gte": start_date.isoformat()}},
        {"_id": 0, "created_at": 1, "analysis.sentiment": 1}
    ).to_list(10000)
    
    # Group by date
    trends = {}
    for fb in feedbacks:
        date_str = fb["created_at"][:10] if isinstance(fb["created_at"], str) else fb["created_at"].strftime("%Y-%m-%d")
        if date_str not in trends:
            trends[date_str] = {"positive": 0, "neutral": 0, "negative": 0}
        sentiment = fb.get("analysis", {}).get("sentiment", "neutral")
        trends[date_str][sentiment] += 1
    
    return [{"date": k, **v} for k, v in sorted(trends.items())]

@api_router.get("/analytics/source-distribution")
async def get_source_distribution(user: Dict = Depends(get_current_user)):
    pipeline = [
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    results = await db.feedbacks.aggregate(pipeline).to_list(100)
    return [{"source": r["_id"], "count": r["count"]} for r in results]

@api_router.get("/analytics/themes")
async def get_theme_distribution(user: Dict = Depends(get_current_user)):
    feedbacks = await db.feedbacks.find({"analysis.themes": {"$exists": True}}, {"_id": 0, "analysis.themes": 1}).to_list(1000)
    theme_counts = {}
    for fb in feedbacks:
        for theme in fb.get("analysis", {}).get("themes", []):
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
    
    sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    return [{"theme": t, "count": c} for t, c in sorted_themes]

@api_router.get("/analytics/emotions")
async def get_emotion_distribution(user: Dict = Depends(get_current_user)):
    feedbacks = await db.feedbacks.find({"analysis.emotions": {"$exists": True}}, {"_id": 0, "analysis.emotions": 1}).to_list(1000)
    emotion_counts = {}
    for fb in feedbacks:
        for emotion in fb.get("analysis", {}).get("emotions", []):
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    
    return [{"emotion": e, "count": c} for e, c in sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)]

# ============== DEMO DATA ==============
@api_router.post("/demo/seed")
async def seed_demo_data(user: Dict = Depends(get_current_user)):
    """Seed database with demo data"""
    demo_feedbacks = [
        {"content": "Absolutely love your product! The customer service team was incredibly helpful and resolved my issue within minutes. Will definitely recommend to friends!", "source": "twitter", "author_name": "Sarah Johnson"},
        {"content": "The new update completely broke my workflow. I've been a loyal customer for 3 years and this is unacceptable. Please fix this ASAP!", "source": "support_ticket", "author_name": "Mike Chen"},
        {"content": "Product quality is decent. Delivery was on time. Nothing special but gets the job done.", "source": "website", "author_name": "Anonymous"},
        {"content": "Your mobile app keeps crashing every time I try to complete checkout. This is the third time this week. Extremely frustrated!", "source": "facebook", "author_name": "Jennifer Williams"},
        {"content": "Best purchase I've made this year! The features are exactly what I needed and the price point is perfect.", "source": "youtube", "author_name": "Tech Reviewer Pro"},
        {"content": "Waited 2 weeks for my order only to receive the wrong item. Support was helpful in processing the return at least.", "source": "email", "author_name": "Robert Davis"},
        {"content": "The onboarding process was smooth and intuitive. Your team clearly put a lot of thought into user experience.", "source": "survey", "author_name": "Amanda Lee"},
        {"content": "Oh great, another price increase. Sure, I'll just keep paying more for the same features. Thanks for nothing.", "source": "twitter", "author_name": "Sarcastic_User42"},
        {"content": "Your API documentation is confusing and outdated. Spent hours debugging only to find the endpoint changed.", "source": "support_ticket", "author_name": "DevTeam Lead"},
        {"content": "Just switched from your competitor and wow, what a difference! Everything works seamlessly.", "source": "website", "author_name": "Happy Customer"},
        {"content": "The subscription model doesn't work for small businesses like mine. Please consider a pay-per-use option.", "source": "email", "author_name": "Small Biz Owner"},
        {"content": "Outstanding webinar yesterday! Learned so much about the new features. Keep up the great work!", "source": "youtube", "author_name": "Eager Learner"},
        {"content": "My account was hacked and I lost all my data. This is a serious security issue that needs immediate attention!", "source": "support_ticket", "author_name": "Concerned User"},
        {"content": "The redesign looks clean but takes some getting used to. Overall positive experience.", "source": "facebook", "author_name": "UI Enthusiast"},
        {"content": "Terrible experience. Product broke within a week. Refund process was a nightmare. Never again.", "source": "twitter", "author_name": "Disappointed_Dan"}
    ]
    
    created_feedbacks = []
    for fb_data in demo_feedbacks:
        feedback = Feedback(
            content=fb_data["content"],
            source=FeedbackSource(fb_data["source"]),
            author_name=fb_data["author_name"]
        )
        
        # Analyze with AI
        analysis = await analyze_feedback_with_ai(feedback.content)
        feedback.analysis = analysis
        feedback.is_processed = True
        
        feedback_dict = feedback.model_dump()
        feedback_dict["created_at"] = feedback_dict["created_at"].isoformat()
        await db.feedbacks.insert_one(feedback_dict)
        created_feedbacks.append(feedback)
    
    # Create some demo cases for negative feedbacks
    negative_feedbacks = [f for f in created_feedbacks if f.analysis and f.analysis.sentiment == SentimentType.NEGATIVE]
    for fb in negative_feedbacks[:5]:
        case = Case(
            feedback_id=fb.id,
            title=f"Issue: {fb.content[:50]}...",
            priority=Priority.HIGH if fb.analysis.confidence > 0.8 else Priority.MEDIUM
        )
        case.due_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        case_dict = case.model_dump()
        case_dict["created_at"] = case_dict["created_at"].isoformat()
        case_dict["updated_at"] = case_dict["updated_at"].isoformat()
        if case_dict["due_date"]:
            case_dict["due_date"] = case_dict["due_date"].isoformat()
        
        await db.cases.insert_one(case_dict)
        await db.feedbacks.update_one({"id": fb.id}, {"$set": {"case_id": case.id}})
    
    return {"message": f"Seeded {len(created_feedbacks)} feedbacks and {len(negative_feedbacks[:5])} cases"}

# ============== EMAIL NOTIFICATIONS ==============
async def send_email_notification(recipient: str, subject: str, content: str, alert_id: str = None):
    """Send email notification using Resend"""
    if not RESEND_API_KEY:
        logger.warning("Email notifications disabled: RESEND_API_KEY not configured")
        return None
    
    notification = EmailNotification(
        recipient_email=recipient,
        subject=subject,
        content=content,
        alert_id=alert_id
    )
    
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [recipient],
            "subject": subject,
            "html": content
        }
        
        result = await asyncio.to_thread(resend.Emails.send, params)
        notification.sent = True
        notification.sent_at = datetime.now(timezone.utc)
        
        # Save notification record
        notif_dict = notification.model_dump()
        notif_dict["created_at"] = notif_dict["created_at"].isoformat()
        if notif_dict["sent_at"]:
            notif_dict["sent_at"] = notif_dict["sent_at"].isoformat()
        await db.email_notifications.insert_one(notif_dict)
        
        logger.info(f"Email sent to {recipient}: {subject}")
        return result
    except Exception as e:
        notification.error = str(e)
        notif_dict = notification.model_dump()
        notif_dict["created_at"] = notif_dict["created_at"].isoformat()
        await db.email_notifications.insert_one(notif_dict)
        logger.error(f"Failed to send email: {e}")
        return None

async def send_alert_email(alert: Alert, settings: Dict = None):
    """Send email for an alert if notifications are enabled"""
    if not settings:
        settings = await db.system_settings.find_one({"id": "system_settings"}, {"_id": 0})
    
    if not settings or not settings.get("email_alerts_enabled") or not settings.get("notification_email"):
        return
    
    severity_colors = {
        "critical": "#DC2626",
        "high": "#F97316", 
        "medium": "#F59E0B",
        "low": "#3B82F6"
    }
    
    html_content = f"""
    <div style="font-family: 'IBM Plex Sans', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #4F46E5, #7C3AED); padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">OmniMine Alert</h1>
        </div>
        <div style="background: #fff; padding: 24px; border: 1px solid #E2E8F0; border-top: none; border-radius: 0 0 12px 12px;">
            <div style="background: {severity_colors.get(alert.severity.value, '#64748B')}15; border-left: 4px solid {severity_colors.get(alert.severity.value, '#64748B')}; padding: 16px; margin-bottom: 16px; border-radius: 4px;">
                <h2 style="margin: 0 0 8px 0; color: #1E293B; font-size: 18px;">{alert.title}</h2>
                <span style="background: {severity_colors.get(alert.severity.value, '#64748B')}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; text-transform: uppercase;">{alert.severity.value}</span>
            </div>
            <p style="color: #475569; line-height: 1.6;">{alert.message}</p>
            <p style="color: #94A3B8; font-size: 12px; margin-top: 16px;">
                Alert generated at {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
            </p>
            <a href="#" style="display: inline-block; background: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin-top: 16px;">View in Dashboard</a>
        </div>
    </div>
    """
    
    await send_email_notification(
        settings["notification_email"],
        f"[OmniMine Alert] {alert.title}",
        html_content,
        alert.id
    )

# ============== SLA BREACH TRACKING ==============
async def check_sla_breaches():
    """Check for SLA due-soon + breaches per org and create alerts."""
    now = datetime.now(timezone.utc)
    due_soon_cutoff = now + timedelta(hours=max(1, SLA_DUE_SOON_HOURS))

    org_ids = await db.organizations.distinct("id")
    if not org_ids:
        org_ids = ["default"]

    breached_cases: List[Dict[str, Any]] = []

    for org_id in org_ids:
        settings = await db.system_settings.find_one({"id": "system_settings", "org_id": org_id}, {"_id": 0}) or {}

        # Find cases that are past due date and not resolved/closed
        cases = await db.cases.find({
            "org_id": org_id,
            "status": {"$in": ["open", "assigned", "in_progress"]},
            "sla_breached": {"$ne": True},
        }, {"_id": 0}).to_list(2000)

        for case in cases:
            due_date = case.get("due_date")
            if not due_date:
                continue
            if isinstance(due_date, str):
                try:
                    due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                except Exception:
                    continue

            # Due soon alert (once)
            if now <= due_date <= due_soon_cutoff and not case.get("sla_due_soon_alerted"):
                await db.cases.update_one(
                    {"id": case["id"], "org_id": org_id},
                    {"$set": {"sla_due_soon_alerted": True}},
                )
                due_alert = Alert(
                    type="sla_due_soon",
                    title="SLA Due Soon",
                    message=f"Case '{case.get('title','')[:80]}...' is due soon.",
                    severity=Priority.HIGH,
                    related_ids=[case["id"]],
                )
                await insert_alert_and_broadcast(due_alert, org_id=org_id)

            # Breach
            if now > due_date:
                breached_cases.append(case)
                await db.cases.update_one(
                    {"id": case["id"], "org_id": org_id},
                    {"$set": {"sla_breached": True, "status": "escalated", "updated_at": now.isoformat()}},
                )
                await log_case_action(
                    case["id"],
                    "sla_breached",
                    "SLA breached; case escalated automatically",
                    created_by="system",
                    metadata={"to_status": "escalated"},
                    org_id=org_id,
                )

                alert = Alert(
                    type="sla_breach",
                    title="SLA Breach Detected",
                    message=f"Case '{case.get('title','')[:80]}...' has exceeded its SLA deadline.",
                    severity=Priority.CRITICAL,
                    related_ids=[case["id"]],
                )
                await insert_alert_and_broadcast(alert, org_id=org_id)
                await send_alert_email(alert, settings)
                await create_escalation_alert(
                    case["id"],
                    title="Case Escalated (SLA Breach)",
                    message=f"Case '{case.get('title','')[:80]}...' was escalated due to SLA breach.",
                    severity=Priority.CRITICAL,
                )

    return breached_cases

@api_router.post("/sla/check")
async def trigger_sla_check(user: Dict = Depends(get_current_user)):
    """Manually trigger SLA breach check"""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins/managers can run SLA checks")
    breached = await check_sla_breaches()
    return {"message": f"SLA check completed. Found {len(breached)} breached cases."}


@api_router.put("/cases/{case_id}/escalate")
async def manual_escalate_case(case_id: str, reason: str = "Escalated manually", user: Dict = Depends(get_current_user)):
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins/managers can escalate cases")

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.cases.update_one(
        {"id": case_id},
        {"$set": {"status": CaseStatus.ESCALATED.value, "sla_breached": True, "updated_at": now_iso}},
    )

    await log_case_action(
        case_id,
        "escalated",
        reason,
        created_by=user["sub"],
        metadata={"from_status": case.get("status"), "to_status": CaseStatus.ESCALATED.value},
    )

    await create_escalation_alert(
        case_id,
        title="Case Escalated",
        message=f"Case '{case.get('title','')[:80]}...' was escalated. Reason: {reason}",
        severity=Priority.HIGH,
    )

    return {"message": "Case escalated"}

# ============== SYSTEM SETTINGS ==============
@api_router.get("/settings/system")
async def get_system_settings(user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    settings = await db.system_settings.find_one({"id": "system_settings", "org_id": org_id}, {"_id": 0})
    if not settings:
        # Create default settings
        default = SystemSettings()
        settings_dict = default.model_dump()
        settings_dict["org_id"] = org_id
        settings_dict["created_at"] = settings_dict["created_at"].isoformat()
        settings_dict["updated_at"] = settings_dict["updated_at"].isoformat()
        await db.system_settings.insert_one(settings_dict)
        return default.model_dump()
    return settings

@api_router.put("/settings/system")
async def update_system_settings(updates: SystemSettingsUpdate, request: Request, user: Dict = Depends(get_current_user)):
    if not has_permission(user.get("role"), Permission.SETTINGS_UPDATE.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    org_id = get_org_id(user)
    before = await db.system_settings.find_one({"id": "system_settings", "org_id": org_id}, {"_id": 0})
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["org_id"] = org_id
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.system_settings.update_one(
        {"id": "system_settings", "org_id": org_id},
        {"$set": update_data},
        upsert=True
    )
    after = await db.system_settings.find_one({"id": "system_settings", "org_id": org_id}, {"_id": 0})
    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="settings_update",
        resource_type="system_settings",
        resource_id="system_settings",
        request=request,
        status_code=200,
        before=before,
        after=after,
        metadata={"fields": list(update_data.keys())},
    )
    
    return {"message": "Settings updated successfully"}

# ============== SOCIAL MEDIA CONFIGURATION ==============
@api_router.get("/settings/social")
async def get_social_configs(user: Dict = Depends(get_current_user)):
    org_id = get_org_id(user)
    settings = await db.system_settings.find_one({"id": "system_settings", "org_id": org_id}, {"_id": 0})
    if not settings:
        return {"social_configs": {}}
    
    # Mask API keys for security
    configs = settings.get("social_configs", {})
    masked_configs = {}
    for platform, config in configs.items():
        masked_config = config.copy()
        if masked_config.get("api_key"):
            masked_config["api_key"] = "***" + masked_config["api_key"][-4:] if len(masked_config["api_key"]) > 4 else "****"
        if masked_config.get("api_secret"):
            masked_config["api_secret"] = "***" + masked_config["api_secret"][-4:] if len(masked_config["api_secret"]) > 4 else "****"
        if masked_config.get("access_token"):
            masked_config["access_token"] = "***" + masked_config["access_token"][-4:] if len(masked_config["access_token"]) > 4 else "****"
        masked_configs[platform] = masked_config
    
    return {"social_configs": masked_configs}

@api_router.put("/settings/social/{platform}")
async def update_social_config(platform: str, config: SocialMediaConfigUpdate, request: Request, user: Dict = Depends(get_current_user)):
    if not has_permission(user.get("role"), Permission.SOCIAL_SETTINGS_UPDATE.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    if platform not in ["twitter", "facebook", "youtube", "linkedin"]:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    config_data = config.model_dump()
    config_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Get current settings
    org_id = get_org_id(user)
    settings = await db.system_settings.find_one({"id": "system_settings", "org_id": org_id}, {"_id": 0})
    social_configs = settings.get("social_configs", {}) if settings else {}
    before = {"social_configs": (social_configs or {}).get(platform)}
    
    # Update the specific platform config
    social_configs[platform] = config_data
    
    await db.system_settings.update_one(
        {"id": "system_settings", "org_id": org_id},
        {"$set": {"social_configs": social_configs, "updated_at": datetime.now(timezone.utc).isoformat(), "org_id": org_id}},
        upsert=True
    )

    after_settings = await db.system_settings.find_one({"id": "system_settings", "org_id": org_id}, {"_id": 0})
    after = {"social_configs": ((after_settings or {}).get("social_configs", {}) or {}).get(platform)}
    await write_audit_event(
        org_id=org_id,
        actor=user,
        action="social_settings_update",
        resource_type="social_config",
        resource_id=platform,
        request=request,
        status_code=200,
        before=before,
        after=after,
        metadata={"platform": platform, "enabled": config.enabled},
    )
    
    return {"message": f"{platform} configuration updated successfully"}

@api_router.delete("/settings/social/{platform}")
async def delete_social_config(platform: str, user: Dict = Depends(get_current_user)):
    if user.get("role") not in ["admin"]:
        raise HTTPException(status_code=403, detail="Only admins can delete social media settings")
    
    org_id = get_org_id(user)
    settings = await db.system_settings.find_one({"id": "system_settings", "org_id": org_id}, {"_id": 0})
    if settings and platform in settings.get("social_configs", {}):
        social_configs = settings["social_configs"]
        del social_configs[platform]
        await db.system_settings.update_one(
            {"id": "system_settings", "org_id": org_id},
            {"$set": {"social_configs": social_configs, "org_id": org_id}}
        )
    
    return {"message": f"{platform} configuration deleted"}

# ============== EXPORT FUNCTIONALITY ==============
@api_router.post("/export/feedback/csv")
async def export_feedback_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sentiment: Optional[str] = None,
    source: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """Export feedback data to CSV"""
    query = {}
    if start_date:
        query["created_at"] = {"$gte": start_date}
    if end_date:
        query.setdefault("created_at", {})["$lte"] = end_date
    if sentiment:
        query["analysis.sentiment"] = sentiment
    if source:
        query["source"] = source
    
    feedbacks = await db.feedbacks.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "ID", "Content", "Source", "Author", "Sentiment", "Confidence",
        "Emotions", "Themes", "Created At", "Has Case"
    ])
    
    for fb in feedbacks:
        analysis = fb.get("analysis", {})
        writer.writerow([
            fb.get("id", ""),
            fb.get("content", "")[:500],
            fb.get("source", ""),
            fb.get("author_name", ""),
            analysis.get("sentiment", ""),
            analysis.get("confidence", ""),
            ", ".join(analysis.get("emotions", [])),
            ", ".join(analysis.get("themes", [])),
            fb.get("created_at", ""),
            "Yes" if fb.get("case_id") else "No"
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=omnimine_feedback_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@api_router.post("/export/cases/csv")
async def export_cases_csv(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """Export cases data to CSV"""
    query = {}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    
    cases = await db.cases.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "ID", "Title", "Status", "Priority", "Assigned To",
        "Created At", "Due Date", "SLA Breached", "Resolution Notes"
    ])
    
    for case in cases:
        writer.writerow([
            case.get("id", ""),
            case.get("title", ""),
            case.get("status", ""),
            case.get("priority", ""),
            case.get("assigned_to", ""),
            case.get("created_at", ""),
            case.get("due_date", ""),
            "Yes" if case.get("sla_breached") else "No",
            case.get("resolution_notes", "")
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=omnimine_cases_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@api_router.post("/export/analytics/pdf")
async def export_analytics_pdf(user: Dict = Depends(get_current_user)):
    """Export analytics report to PDF"""
    # Get analytics data
    total_feedback = await db.feedbacks.count_documents({})
    positive = await db.feedbacks.count_documents({"analysis.sentiment": "positive"})
    neutral = await db.feedbacks.count_documents({"analysis.sentiment": "neutral"})
    negative = await db.feedbacks.count_documents({"analysis.sentiment": "negative"})
    
    total_cases = await db.cases.count_documents({})
    open_cases = await db.cases.count_documents({"status": {"$in": ["open", "in_progress"]}})
    resolved_cases = await db.cases.count_documents({"status": {"$in": ["resolved", "closed"]}})
    breached_cases = await db.cases.count_documents({"sla_breached": True})
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=24, spaceAfter=30)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=16, spaceAfter=12, spaceBefore=20)
    
    elements = []
    
    # Title
    elements.append(Paragraph("OmniMine Analytics Report", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 30))
    
    # Feedback Summary
    elements.append(Paragraph("Feedback Summary", heading_style))
    feedback_data = [
        ["Metric", "Value"],
        ["Total Feedback", str(total_feedback)],
        ["Positive", f"{positive} ({(positive/total_feedback*100):.1f}%)" if total_feedback > 0 else "0"],
        ["Neutral", f"{neutral} ({(neutral/total_feedback*100):.1f}%)" if total_feedback > 0 else "0"],
        ["Negative", f"{negative} ({(negative/total_feedback*100):.1f}%)" if total_feedback > 0 else "0"],
    ]
    
    feedback_table = Table(feedback_data, colWidths=[3*inch, 2*inch])
    feedback_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(feedback_table)
    elements.append(Spacer(1, 20))
    
    # Cases Summary
    elements.append(Paragraph("Cases Summary", heading_style))
    cases_data = [
        ["Metric", "Value"],
        ["Total Cases", str(total_cases)],
        ["Open/In Progress", str(open_cases)],
        ["Resolved/Closed", str(resolved_cases)],
        ["SLA Breached", str(breached_cases)],
        ["Closure Rate", f"{(resolved_cases/total_cases*100):.1f}%" if total_cases > 0 else "N/A"],
    ]
    
    cases_table = Table(cases_data, colWidths=[3*inch, 2*inch])
    cases_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(cases_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=omnimine_report_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )

# ============== PHASE 3: SMART ROUTING ==============
async def analyze_case_for_routing(content: str, themes: List[str]) -> Dict[str, Any]:
    """Use AI to analyze case content and determine required skills"""
    try:
        if not EMERGENT_LLM_KEY or LlmChat is None or UserMessage is None:
            raise RuntimeError("LLM integration not configured")
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"routing-{uuid.uuid4()}",
            system_message="""You are an expert case routing AI. Analyze the customer feedback/issue and determine:
1. Required skills to handle this case
2. Priority level based on urgency
3. Complexity score (1-10)

Available skills: technical_support, billing, product_issues, general_inquiry, complaints, feature_requests, security, shipping, returns, account_management

Return ONLY valid JSON:
{
    "required_skills": ["skill1", "skill2"],
    "suggested_priority": "low|medium|high|critical",
    "complexity_score": 5,
    "category": "main category",
    "reasoning": "brief explanation"
}"""
        ).with_model("openai", "gpt-5.2")
        
        message = UserMessage(text=f"Analyze this case for routing:\n\nContent: {content}\nThemes detected: {', '.join(themes)}")
        response = await chat.send_message(message)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "required_skills": ["general_inquiry"],
                "suggested_priority": "medium",
                "complexity_score": 5,
                "category": "general",
                "reasoning": "Could not parse AI response"
            }
    except Exception as e:
        logger.error(f"AI routing analysis error: {e}")
        return {
            "required_skills": ["general_inquiry"],
            "suggested_priority": "medium", 
            "complexity_score": 5,
            "category": "general",
            "reasoning": "AI analysis unavailable"
        }

async def find_best_agent(required_skills: List[str], priority: str) -> SmartRoutingResult:
    """Find the best available agent based on skills, workload, and performance"""
    # Get all agents with profiles
    agents = await db.users.find({"role": {"$in": ["agent", "manager"]}}, {"_id": 0}).to_list(100)
    
    if not agents:
        return None
    
    scored_agents = []
    
    for agent in agents:
        # Get agent profile
        profile = await db.agent_profiles.find_one({"user_id": agent["id"]}, {"_id": 0})
        if not profile:
            # Create default profile
            profile = {
                "user_id": agent["id"],
                "skills": ["general_inquiry"],
                "max_workload": 10,
                "current_workload": 0,
                "avg_resolution_time": 24.0,
                "satisfaction_score": 3.5,
                "cases_resolved": 0,
                "is_available": True
            }
            await db.agent_profiles.insert_one(profile)
        
        if not profile.get("is_available", True):
            continue
            
        if profile.get("current_workload", 0) >= profile.get("max_workload", 10):
            continue
        
        # Calculate skill match score
        agent_skills = set(profile.get("skills", []))
        required_set = set(required_skills)
        matched_skills = agent_skills.intersection(required_set)
        skill_score = len(matched_skills) / max(len(required_set), 1) * 40  # 40% weight
        
        # Calculate workload score (lower is better)
        workload_ratio = profile.get("current_workload", 0) / max(profile.get("max_workload", 10), 1)
        workload_score = (1 - workload_ratio) * 30  # 30% weight
        
        # Calculate performance score
        satisfaction = profile.get("satisfaction_score", 3.0) / 5.0 * 20  # 20% weight
        
        # Resolution speed score
        avg_time = profile.get("avg_resolution_time", 24)
        speed_score = max(0, (48 - avg_time) / 48) * 10  # 10% weight
        
        total_score = skill_score + workload_score + satisfaction + speed_score
        
        scored_agents.append({
            "agent": agent,
            "profile": profile,
            "score": total_score,
            "matched_skills": list(matched_skills)
        })
    
    if not scored_agents:
        return None
    
    # Sort by score descending
    scored_agents.sort(key=lambda x: x["score"], reverse=True)
    
    best = scored_agents[0]
    alternatives = [
        {
            "agent_id": a["agent"]["id"],
            "agent_name": a["agent"]["name"],
            "score": round(a["score"], 2),
            "workload": a["profile"].get("current_workload", 0)
        }
        for a in scored_agents[1:4]
    ]
    
    return SmartRoutingResult(
        recommended_agent_id=best["agent"]["id"],
        recommended_agent_name=best["agent"]["name"],
        confidence_score=round(best["score"] / 100, 2),
        reasoning=f"Best match based on {len(best['matched_skills'])} matching skills, {best['profile'].get('current_workload', 0)}/{best['profile'].get('max_workload', 10)} workload capacity, and {best['profile'].get('satisfaction_score', 0):.1f}/5 satisfaction score.",
        matched_skills=best["matched_skills"],
        agent_workload=best["profile"].get("current_workload", 0),
        alternative_agents=alternatives
    )

@api_router.post("/routing/analyze/{case_id}")
async def analyze_case_routing(case_id: str, user: Dict = Depends(get_current_user)):
    """Analyze a case and get smart routing recommendations"""
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Get associated feedback
    feedback = await db.feedbacks.find_one({"id": case.get("feedback_id")}, {"_id": 0})
    content = feedback.get("content", case.get("title", "")) if feedback else case.get("title", "")
    themes = feedback.get("analysis", {}).get("themes", []) if feedback else []
    
    # Analyze with AI
    analysis = await analyze_case_for_routing(content, themes)
    
    # Find best agent
    routing_result = await find_best_agent(analysis.get("required_skills", []), analysis.get("suggested_priority", "medium"))
    
    if not routing_result:
        return {
            "analysis": analysis,
            "routing": None,
            "message": "No available agents found"
        }
    
    return {
        "analysis": analysis,
        "routing": routing_result.model_dump()
    }

@api_router.post("/routing/auto-assign/{case_id}")
async def auto_assign_case(case_id: str, user: Dict = Depends(get_current_user)):
    """Automatically assign a case using smart routing"""
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    if case.get("assigned_to"):
        raise HTTPException(status_code=400, detail="Case is already assigned")
    
    # Get routing recommendation
    feedback = await db.feedbacks.find_one({"id": case.get("feedback_id")}, {"_id": 0})
    content = feedback.get("content", case.get("title", "")) if feedback else case.get("title", "")
    themes = feedback.get("analysis", {}).get("themes", []) if feedback else []
    
    analysis = await analyze_case_for_routing(content, themes)
    routing_result = await find_best_agent(analysis.get("required_skills", []), analysis.get("suggested_priority", "medium"))
    
    if not routing_result:
        raise HTTPException(status_code=400, detail="No available agents found for auto-assignment")
    
    # Assign the case
    await db.cases.update_one(
        {"id": case_id},
        {"$set": {
            "assigned_to": routing_result.recommended_agent_id,
            "assigned_by": "smart_routing",
            "status": CaseStatus.IN_PROGRESS.value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Update agent workload
    await db.agent_profiles.update_one(
        {"user_id": routing_result.recommended_agent_id},
        {"$inc": {"current_workload": 1}}
    )
    
    # Log the assignment
    log = ResolutionLog(
        case_id=case_id,
        action="auto_assigned",
        notes=f"Smart Routing assigned to {routing_result.recommended_agent_name}. Reason: {routing_result.reasoning}",
        created_by="smart_routing"
    )
    log_dict = log.model_dump()
    log_dict["created_at"] = log_dict["created_at"].isoformat()
    await db.resolution_logs.insert_one(log_dict)
    
    return {
        "message": "Case auto-assigned successfully",
        "assigned_to": routing_result.recommended_agent_id,
        "agent_name": routing_result.recommended_agent_name,
        "routing_details": routing_result.model_dump()
    }

# ============== AGENT PROFILE MANAGEMENT ==============
@api_router.get("/agents/profiles")
async def get_agent_profiles(user: Dict = Depends(get_current_user)):
    """Get all agent profiles with their skills and workload"""
    agents = await db.users.find({"role": {"$in": ["agent", "manager"]}}, {"_id": 0, "password_hash": 0}).to_list(100)
    
    result = []
    for agent in agents:
        profile = await db.agent_profiles.find_one({"user_id": agent["id"]}, {"_id": 0})
        if not profile:
            profile = {
                "user_id": agent["id"],
                "skills": ["general_inquiry"],
                "max_workload": 10,
                "current_workload": 0,
                "avg_resolution_time": 24.0,
                "satisfaction_score": 3.5,
                "cases_resolved": 0,
                "is_available": True
            }
        
        result.append({
            **agent,
            "profile": profile
        })
    
    return result

@api_router.get("/agents/profiles/{user_id}")
async def get_agent_profile(user_id: str, user: Dict = Depends(get_current_user)):
    """Get a specific agent's profile"""
    agent = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    profile = await db.agent_profiles.find_one({"user_id": user_id}, {"_id": 0})
    if not profile:
        profile = {
            "user_id": user_id,
            "skills": ["general_inquiry"],
            "max_workload": 10,
            "current_workload": 0,
            "avg_resolution_time": 24.0,
            "satisfaction_score": 3.5,
            "cases_resolved": 0,
            "is_available": True
        }
    
    return {**agent, "profile": profile}

@api_router.put("/agents/profiles/{user_id}")
async def update_agent_profile(user_id: str, updates: AgentProfileUpdate, user: Dict = Depends(get_current_user)):
    """Update an agent's profile (skills, workload capacity, availability)"""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins and managers can update agent profiles")
    
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.agent_profiles.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True
    )
    
    return {"message": "Agent profile updated successfully"}

@api_router.get("/agents/skills")
async def get_available_skills(user: Dict = Depends(get_current_user)):
    """Get list of available skills for agent assignment"""
    return {
        "skills": [
            {"value": "technical_support", "label": "Technical Support"},
            {"value": "billing", "label": "Billing & Payments"},
            {"value": "product_issues", "label": "Product Issues"},
            {"value": "general_inquiry", "label": "General Inquiry"},
            {"value": "complaints", "label": "Complaints"},
            {"value": "feature_requests", "label": "Feature Requests"},
            {"value": "security", "label": "Security"},
            {"value": "shipping", "label": "Shipping & Delivery"},
            {"value": "returns", "label": "Returns & Refunds"},
            {"value": "account_management", "label": "Account Management"}
        ]
    }

# ============== BULK CSV IMPORT ==============
@api_router.post("/import/feedback/csv")
async def import_feedback_csv(
    csv_content: str,
    user: Dict = Depends(get_current_user)
):
    """Import feedback from CSV content (base64 encoded or raw CSV string)"""
    try:
        # Try to decode if base64
        try:
            import base64
            csv_content = base64.b64decode(csv_content).decode('utf-8')
        except:
            pass
        
        reader = csv.DictReader(io.StringIO(csv_content))
        
        imported = 0
        failed = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):
            try:
                content = row.get('content') or row.get('Content') or row.get('feedback') or row.get('Feedback')
                if not content:
                    errors.append(f"Row {row_num}: Missing content field")
                    failed += 1
                    continue
                
                source = row.get('source') or row.get('Source') or 'manual'
                source = source.lower().replace(' ', '_')
                if source not in [s.value for s in FeedbackSource]:
                    source = 'manual'
                
                author = row.get('author') or row.get('Author') or row.get('author_name') or None
                
                feedback = Feedback(
                    content=content,
                    source=FeedbackSource(source),
                    author_name=author
                )
                
                # Analyze with AI
                analysis = await analyze_feedback_with_ai(content)
                feedback.analysis = analysis
                feedback.is_processed = True
                
                feedback_dict = feedback.model_dump()
                feedback_dict["created_at"] = feedback_dict["created_at"].isoformat()
                await db.feedbacks.insert_one(feedback_dict)
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                failed += 1
        
        return BulkCSVImportResult(
            total_rows=imported + failed,
            imported=imported,
            failed=failed,
            errors=errors[:10]  # Limit errors shown
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

@api_router.post("/import/feedback/json")
async def import_feedback_json(
    feedbacks: List[FeedbackCreate],
    user: Dict = Depends(get_current_user)
):
    """Import multiple feedbacks from JSON array"""
    imported = 0
    failed = 0
    errors = []
    
    for i, fb_data in enumerate(feedbacks):
        try:
            feedback = Feedback(**fb_data.model_dump())
            analysis = await analyze_feedback_with_ai(feedback.content)
            feedback.analysis = analysis
            feedback.is_processed = True
            
            feedback_dict = feedback.model_dump()
            feedback_dict["created_at"] = feedback_dict["created_at"].isoformat()
            await db.feedbacks.insert_one(feedback_dict)
            imported += 1
        except Exception as e:
            errors.append(f"Item {i}: {str(e)}")
            failed += 1
    
    return BulkCSVImportResult(
        total_rows=len(feedbacks),
        imported=imported,
        failed=failed,
        errors=errors[:10]
    )

# ============== SCHEDULED REPORTS ==============
@api_router.get("/reports/scheduled")
async def get_scheduled_reports(user: Dict = Depends(get_current_user)):
    """Get all scheduled reports"""
    reports = await db.scheduled_reports.find({}, {"_id": 0}).to_list(100)
    for r in reports:
        if isinstance(r.get("created_at"), str):
            r["created_at"] = datetime.fromisoformat(r["created_at"])
        if r.get("last_sent") and isinstance(r["last_sent"], str):
            r["last_sent"] = datetime.fromisoformat(r["last_sent"])
    return reports

@api_router.post("/reports/scheduled")
async def create_scheduled_report(
    name: str,
    report_type: str,
    schedule: str,
    recipients: List[str],
    user: Dict = Depends(get_current_user)
):
    """Create a new scheduled report"""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins and managers can create scheduled reports")
    
    report = ScheduledReport(
        name=name,
        report_type=report_type,
        schedule=schedule,
        recipients=recipients
    )
    
    report_dict = report.model_dump()
    report_dict["created_at"] = report_dict["created_at"].isoformat()
    await db.scheduled_reports.insert_one(report_dict)
    
    return {"message": "Scheduled report created", "report_id": report.id}

@api_router.delete("/reports/scheduled/{report_id}")
async def delete_scheduled_report(report_id: str, user: Dict = Depends(get_current_user)):
    """Delete a scheduled report"""
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins and managers can delete scheduled reports")
    
    await db.scheduled_reports.delete_one({"id": report_id})
    return {"message": "Report deleted"}

# ============== STATUS CHECK ==============
@api_router.get("/")
async def root():
    return {"message": "OmniMine API is running", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Include router and configure app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_multi_tenant_bootstrap():
    """
    Phase 4: Multi-tenant bootstrap for local/dev.
    - Ensure a default org exists
    - Backfill org_id on legacy docs so the app keeps working
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.organizations.update_one(
        {"id": "default"},
        {"$setOnInsert": {"id": "default", "name": "Default Organization", "is_active": True, "created_at": now_iso}},
        upsert=True,
    )

    collections = [
        db.users,
        db.feedbacks,
        db.cases,
        db.alerts,
        db.surveys,
        db.teams,
        db.resolution_logs,
        db.agent_profiles,
        db.scheduled_reports,
        db.email_notifications,
    ]
    for col in collections:
        try:
            await col.update_many({"org_id": {"$exists": False}}, {"$set": {"org_id": "default"}})
        except Exception:
            # some collections may not exist yet
            pass

    # Audit retention cleanup (best-effort)
    if AUDIT_RETENTION_DAYS > 0:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=AUDIT_RETENTION_DAYS)).isoformat()
            await db.audit_events.delete_many({"ts": {"$lt": cutoff}})
        except Exception:
            pass

    # Start SLA engine loop (single-node dev). In production, run this in a worker/cron.
    global _sla_task
    if _sla_task is None and SLA_CHECK_INTERVAL_SECONDS > 0:
        async def sla_loop():
            while True:
                try:
                    await check_sla_breaches()
                except Exception as e:
                    logger.error(f"SLA loop error: {e}")
                await asyncio.sleep(SLA_CHECK_INTERVAL_SECONDS)

        _sla_task = asyncio.create_task(sla_loop())

    # Start monitoring spike detector loop (single-node dev).
    global _monitor_task
    if _monitor_task is None and MONITORING_TICK_SECONDS > 0:
        async def monitor_loop():
            while True:
                try:
                    spikes = await monitoring.detect_spikes()
                    for s in spikes:
                        org_id = s.get("org_id") or "default"
                        alert = Alert(
                            type=s.get("type", "sentiment_spike"),
                            title=s.get("title", "Spike detected"),
                            message=s.get("message", ""),
                            severity=Priority.HIGH if s.get("severity") == "high" else Priority.MEDIUM,
                            related_ids=[],
                        )
                        # Store metrics on the alert by embedding into message via metadata-like pattern
                        await insert_alert_and_broadcast(alert, org_id=org_id)
                except Exception as e:
                    logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(MONITORING_TICK_SECONDS)

        _monitor_task = asyncio.create_task(monitor_loop())

@app.on_event("shutdown")
async def shutdown_db_client():
    global _sla_task
    if _sla_task is not None:
        _sla_task.cancel()
        with contextlib.suppress(Exception):
            await _sla_task
        _sla_task = None
    global _monitor_task
    if _monitor_task is not None:
        _monitor_task.cancel()
        with contextlib.suppress(Exception):
            await _monitor_task
        _monitor_task = None
    client.close()

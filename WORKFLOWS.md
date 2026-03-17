# OmniMine — End-to-End Workflows

This document describes **all major workflows** in OmniMine, from authentication through feedback → AI → cases → SLA → surveys → alerts (including real-time alerts and the load-test generator).

## System overview

- **Frontend**: React app (dev server on `http://localhost:4005`)
- **Backend**: FastAPI (API root `http://localhost:8001/api`)
- **DB**: MongoDB (Motor async driver)
- **Auth**: JWT Bearer token (header) + JWT token in query param for SSE
- **Multi-tenant**: `org_id` scoped on data access
- **AI providers** (current priority):
  - **Hugging Face** (if `HF_TOKEN` is set)
  - DeepSeek (if `DEEPSEEK_API_KEY` is set)
  - Emergent/OpenAI integration (if `EMERGENT_LLM_KEY` is set)
  - Heuristic fallbacks

---

## 1) Authentication & Session workflow

### Register
1. User submits email/password/name/role.
2. Backend creates `User` in `db.users` (with `org_id` defaulting to `default` unless provided).
3. Backend returns:
   - `access_token` (JWT)
   - `user` payload (includes `org_id`)

**API**
- `POST /api/auth/register`

### Login
1. User submits email/password.
2. Backend validates password hash.
3. Backend returns JWT + user payload.

**API**
- `POST /api/auth/login`

### Load current user (`/me`)
1. Frontend stores token in `localStorage` as `omnimine_token`.
2. Frontend sets `Authorization: Bearer <token>` for axios.
3. Frontend loads `GET /api/auth/me`.

**API**
- `GET /api/auth/me`

---

## 2) Multi-tenant SaaS workflow (Org scoping)

### Default org bootstrap
On backend startup:
- Ensure a `default` organization exists
- Backfill `org_id` on existing documents (legacy safety)

### Org switching (admin)
1. Admin selects an org from the header Org switcher.
2. Frontend calls `POST /api/auth/switch-org` with `org_id`.
3. Backend re-issues JWT with that `org_id`.
4. Frontend replaces token and reconnects SSE.

**API**
- `GET /api/orgs` (admin)
- `POST /api/orgs` (admin)
- `PUT /api/orgs/{org_id}/users/{user_id}` (admin)
- `POST /api/auth/switch-org` (admin)

**Data isolation**
All reads/writes for key resources are scoped by the authenticated user’s `org_id`:
- feedbacks, cases, alerts, surveys, logs, teams, users, settings, agent profiles, reports

---

## 3) Feedback ingestion workflow (core)

### Create feedback (single)
1. User creates feedback from UI or API.
2. Backend:
   - attaches `org_id`
   - runs **AI sentiment analysis** (`analyze_feedback_with_ai`)
   - stores feedback in `db.feedbacks`
3. If sentiment is **negative** and confidence \(>\) 0.7:
   - create an alert **negative_feedback**
   - auto-create a **case**
   - (optional) auto-assign case (rules for high/critical)

**API**
- `POST /api/feedback`

### Bulk feedback upload
1. User submits list of feedback items.
2. Backend analyzes each, stores them.

**API**
- `POST /api/feedback/bulk`

### List and view feedback
**API**
- `GET /api/feedback`
- `GET /api/feedback/{feedback_id}`
- `POST /api/feedback/{feedback_id}/analyze` (reanalyze)

---

## 3.5) Ingestion + connectors + normalization (foundational)

This layer adds **enterprise ingestion primitives** without replacing existing feedback APIs.

### What gets stored
- **Raw events**: `db.raw_feedback` (full original payload)
- **Normalized events**: `db.normalized_feedback` (canonical schema)
- **Analyzed snapshot** (optional): `db.analyzed_feedback` (joins feedback + analysis + raw/normalized refs)

### Ingest flow
1. Admin/manager sends an external payload to ingestion endpoint.
2. Backend stores raw payload.
3. Backend normalizes into canonical `NormalizedFeedback`.
4. Backend creates a standard `Feedback` record by calling the existing `/feedback` pipeline.
5. Downstream rules apply normally (alerts, auto-case creation, etc.).

### Current ingestion endpoints (JWT-protected)
- `POST /api/ingest` (generic)
- `POST /api/ingest/website`
- `POST /api/ingest/support-ticket`

### Connector roadmap (next iterations)
- Social APIs (Twitter/X, Facebook/Instagram, YouTube)
- Ticket tools (Zendesk, Freshdesk, ServiceNow)
- Email ingestion (IMAP/Gmail API or webhook relay)
- Streaming ingestion (Kafka topics) + replay/backfill jobs

---

## 4) AI workflow (Sentiment + Copilot)

### Sentiment analysis
1. Backend chooses an AI provider (prefers Hugging Face when configured).
2. Produces a `SentimentAnalysis` object:
   - sentiment (positive/neutral/negative)
   - confidence
   - emotions, themes, key phrases, sarcasm flag
3. Saved into the feedback document and used downstream for:
   - alerts
   - auto-case creation
   - analytics aggregations

**Implementation**
- Backend function: `analyze_feedback_with_ai()`

### AI Copilot — “Run Triage”
1. User clicks “Run Triage” in the Case details dialog (frontend AI Copilot panel).
2. Backend loads feedback text and runs `agentic_triage_text()`:
   - category
   - suggested priority
   - required skills
   - summary + recommended actions
3. Backend stores the triage record and optionally escalates priority of an existing case (never lowers).

**API**
- `POST /api/agentic/triage/feedback/{feedback_id}`

### AI Copilot — “Draft Reply”
1. User clicks “Draft Reply” in the Case details dialog.
2. Backend loads:
   - case title/description
   - linked feedback content
3. Backend runs `agentic_response_draft()`:
   - `customer_reply`
   - `internal_note`
4. Backend stores draft response for auditability.

**API**
- `POST /api/agentic/response/case/{case_id}`

### Executive digest (analytics)
1. User requests an executive digest for last N days.
2. Backend summarizes trends and risks.

**API**
- `GET /api/agentic/executive/digest?days=7`

---

## 5) Alerts workflow (including real-time alerts)

### Alert generation
Alerts are produced by multiple events:
- negative feedback detected
- case created / auto-assigned
- case escalated
- SLA due soon / SLA breach

Alerts are stored in `db.alerts` and also broadcast to the SSE channel.

### Mark read
**API**
- `PUT /api/alerts/{alert_id}/read`
- `PUT /api/alerts/read-all`

### Real-time alerts (SSE)
1. Frontend opens an `EventSource` connection to:
   - `GET /api/stream/alerts?token=<jwt>`
2. Backend verifies the JWT from query param (EventSource cannot set auth headers).
3. Backend publishes events to **org-specific subscribers**.
4. Frontend:
   - shows toast notifications
   - updates unread badge

---

## 6) Case Management workflow (Closed Feedback Loop / CFL)

### Auto-create case from negative feedback
Triggered when:
- sentiment == negative AND confidence > 0.7

Backend creates:
- `Case` with SLA due date based on priority
- `ResolutionLog` entry (“created”)
- `Alert` entries for negative feedback + case created

### Create case manually
1. User chooses feedback and creates a case.
2. Backend writes case and links feedback via `case_id`.

**API**
- `POST /api/cases`

### List / view cases
**API**
- `GET /api/cases`
- `GET /api/cases/{case_id}`

### Assignment workflow
1. Manager/admin assigns a case:
   - sets `assigned_to`, `assigned_by`, `status=assigned`
   - updates agent workload counters
   - logs action

**API**
- `PUT /api/cases/{case_id}/assign?assignee_id=<user_id>`

### Start work
1. Assignee (or admin/manager) starts work:
   - `status=in_progress`
   - logs action

**API**
- `PUT /api/cases/{case_id}/start`

### Resolve case
1. Assignee/admin/manager resolves:
   - `status=resolved`
   - sets `resolved_at`, `resolution_notes`, `verification_status=pending`
   - logs action

**API**
- `PUT /api/cases/{case_id}/resolve?resolution_notes=...`

### Upload evidence
1. Assignee/admin/manager uploads a file.
2. Backend stores it in `backend/uploads/` and app serves it at `/uploads/<file>`.
3. Evidence metadata is stored on the case.

**API**
- `POST /api/cases/{case_id}/evidence` (multipart)

### Case history / audit log
**API**
- `GET /api/cases/{case_id}/logs`

---

## 7) Survey engine workflow (verification loop)

Surveys are used to verify resolution quality and close/reopen cases.

### Verify case (in case details)
1. User submits a rating for a resolved case.
2. Backend writes a `Survey` and updates case:
   - rating >= 4 → `status=closed`, `verification_status=passed`
   - rating < 4 → `status=in_progress`, `verification_status=failed`
3. Logs action and updates workload metrics (when closed).

**API**
- `POST /api/cases/{case_id}/verify`
- `POST /api/surveys` (manual survey submission)
- `GET /api/surveys`

---

## 8) SLA engine workflow

### SLA policy
SLA hours are configured per org in system settings:
- default, low, medium, high, critical

### Due soon + breach checks
1. SLA loop runs on backend startup (single-node dev) on an interval.
2. It scans open-like cases and:
   - emits `sla_due_soon` once (tracks `sla_due_soon_alerted`)
   - escalates when breached (`sla_breached=true`, `status=escalated`)
   - emits `sla_breach` and escalation alerts

**API**
- `POST /api/sla/check` (admin/manager; manual trigger)

---

## 9) Smart routing workflow

### Agent profiles
Agents have skills, max workload, availability, and metrics.

**API**
- `GET /api/agents/profiles`
- `GET /api/agents/profiles/{user_id}`
- `PUT /api/agents/profiles/{user_id}`
- `GET /api/agents/skills`

### Routing analysis and auto-assign
**API**
- `POST /api/routing/analyze/{case_id}`
- `POST /api/routing/auto-assign/{case_id}`

---

## 10) Settings workflow

System settings and social configuration are scoped by org.

**API**
- `GET /api/settings/system`
- `PUT /api/settings/system`
- `GET /api/settings/social`
- `PUT /api/settings/social/{platform}`
- `DELETE /api/settings/social/{platform}`

---

## 11) Analytics workflow

Analytics are computed from stored feedback and cases.

**API**
- `GET /api/analytics/overview`
- `GET /api/analytics/sentiment-trends`
- `GET /api/analytics/source-distribution`
- `GET /api/analytics/themes`
- `GET /api/analytics/emotions`

---

## 12) Exports & imports workflow

**Exports**
- `POST /api/export/feedback/csv`
- `POST /api/export/cases/csv`
- `POST /api/export/analytics/pdf`

**Imports**
- `POST /api/import/feedback/csv`
- `POST /api/import/feedback/json`

---

## 13) Scheduled reports workflow

**API**
- `GET /api/reports/scheduled`
- `POST /api/reports/scheduled`
- `DELETE /api/reports/scheduled/{report_id}`

---

## 14) Load-test / verification workflow (Play/Pause generator)

Purpose: exercise the entire system end-to-end automatically.

### Single dummy feedback
- `POST /api/dev/dummy-feedback`

### High-throughput batch generator
- `POST /api/dev/dummy-feedback/batch`
  - Frontend floater calls this once per second.
  - Batch size: **10 feedbacks/sec**
  - Negative ratio: targets **55–60%** by alternating **5 or 6 negative** per batch.

### UI control
The floating Play/Pause control starts/stops generation immediately.

---

## 15) Real-time monitoring + spike detection + live dashboards (Phase B)

### Live monitoring (rolling windows)
The backend maintains **in-memory rolling windows per org** to power live dashboards and spike detection.

**API**
- `GET /api/monitoring/live`
  - Returns live counts for the last **60s** and **5m**, plus top themes (last **5m**).

### Spike detection → alerts (SSE)
Every few seconds the backend evaluates rolling windows and emits spike alerts into the existing alerts pipeline:
- Negative sentiment spike (last 60s vs last 10m baseline)
- Theme spike (last 5m vs last 1h baseline)

These arrive in real-time via the existing alerts SSE stream:
- `GET /api/stream/alerts` (frontend uses EventSource)

### Live dashboards (UI)
Dashboard shows:
- Live counters (last 60s)
- Top themes (last 5m)

This updates automatically while the generator is running.

---

## 16) Agentic AI orchestration (LangGraph-style) + HITL gates (Phase C)

### Goal
Run a **multi-step AI workflow** over a case (triage → draft → routing proposals) while enforcing **Human-in-the-Loop (HITL)** approval gates for any side-effect actions.

### Orchestration model
- A **workflow run** is persisted in Mongo (org-scoped) with an ordered list of steps.
- Steps can be:
  - **normal nodes** (auto-executed): triage, draft reply
  - **gates** (pause + require approval): apply priority, apply suggested assignment

### API
- `POST /api/agentic/orchestrations/case/{case_id}`
  - Starts (or returns) the latest active run for that case.
  - Executes until the next gate or completion.
- `GET /api/agentic/orchestrations/{run_id}`
  - Fetch run state (steps, outputs, status).
- `POST /api/agentic/orchestrations/{run_id}/gates/{step_key}`
  - Body: `{ decision: "approve" | "reject", note?: string }`
  - **Only admin/manager** can approve/reject gates.
  - Approve applies the side effect (e.g., update case priority / assignment).
  - Reject skips the side effect and continues.

### UI (Cases → AI Copilot)
Inside a case, the AI Copilot panel now has a **Run Workflow** button:
- Shows step-by-step progress and any pending approvals.
- Admin/manager can click **Approve** / **Reject** directly from the panel.

---

## Quick “end-to-end” test checklist

1. Login as admin/manager
2. Press Play on generator
3. Confirm:
   - Feedback list grows rapidly
   - Alerts update in real time
   - Negative feedback creates cases automatically
4. Open a case:
   - Run Triage + Draft Reply (AI Copilot)
   - Assign → Start → Resolve → Verify
5. Confirm SLA due soon/breach alerts are generated over time (or via manual trigger)

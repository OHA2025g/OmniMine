from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid


@dataclass
class NormalizedFeedback:
    id: str
    org_id: str
    source: str
    content: str
    author_name: Optional[str]
    author_id: Optional[str]
    external_id: Optional[str]
    received_at: str
    metadata: Dict[str, Any]
    raw_ref_id: str


def normalize_feedback_payload(*, org_id: str, source: str, payload: Dict[str, Any], received_at: Optional[datetime] = None) -> NormalizedFeedback:
    """
    Convert arbitrary connector payloads into OmniMine's canonical feedback shape.
    This is additive and does not replace existing /feedback endpoint behavior.
    """
    if not received_at:
        received_at = datetime.now(timezone.utc)

    src = (source or "manual").strip().lower()
    raw_ref_id = str(uuid.uuid4())

    # Best-effort extraction (connector-specific adapters can enrich these fields later)
    content = (
        payload.get("content")
        or payload.get("text")
        or payload.get("message")
        or payload.get("body")
        or ""
    )
    content = str(content).strip()
    if not content:
        raise ValueError("payload missing feedback content")

    author_name = payload.get("author_name") or payload.get("author") or payload.get("from_name")
    author_id = payload.get("author_id") or payload.get("from_id") or payload.get("user_id")
    external_id = payload.get("external_id") or payload.get("id") or payload.get("ticket_id") or payload.get("post_id")

    # Preserve original payload + any connector metadata
    metadata = dict(payload.get("metadata") or {})
    for k in ["channel", "platform", "url", "subject", "tags", "priority", "rating"]:
        if k in payload and k not in metadata:
            metadata[k] = payload.get(k)

    return NormalizedFeedback(
        id=str(uuid.uuid4()),
        org_id=org_id,
        source=src,
        content=content,
        author_name=str(author_name).strip()[:120] if author_name else None,
        author_id=str(author_id).strip()[:120] if author_id else None,
        external_id=str(external_id).strip()[:200] if external_id else None,
        received_at=received_at.isoformat(),
        metadata=metadata,
        raw_ref_id=raw_ref_id,
    )


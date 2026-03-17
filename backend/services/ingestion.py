from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .normalization import normalize_feedback_payload, NormalizedFeedback


class IngestionService:
    """
    Stores raw + normalized events, then returns normalized feedback.
    AI analysis and CFL routing should be handled by the caller to preserve existing logic.
    """

    def __init__(self, db):
        self.db = db

    async def ingest(
        self,
        *,
        org_id: str,
        source: str,
        payload: Dict[str, Any],
        received_at: Optional[datetime] = None,
    ) -> NormalizedFeedback:
        if not received_at:
            received_at = datetime.now(timezone.utc)

        normalized = normalize_feedback_payload(org_id=org_id, source=source, payload=payload, received_at=received_at)

        raw_doc = {
            "id": normalized.raw_ref_id,
            "org_id": org_id,
            "source": normalized.source,
            "received_at": normalized.received_at,
            "payload": payload,
        }
        await self.db.raw_feedback.insert_one(raw_doc)

        norm_doc = {
            "id": normalized.id,
            "org_id": normalized.org_id,
            "source": normalized.source,
            "content": normalized.content,
            "author_name": normalized.author_name,
            "author_id": normalized.author_id,
            "external_id": normalized.external_id,
            "received_at": normalized.received_at,
            "metadata": normalized.metadata,
            "raw_ref_id": normalized.raw_ref_id,
        }
        await self.db.normalized_feedback.insert_one(norm_doc)

        return normalized


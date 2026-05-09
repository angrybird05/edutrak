import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scale_foundation import IdempotencyKey


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdempotencyService:
    async def check_existing(
        self,
        db: AsyncSession,
        *,
        idempotency_key: str,
        scope: str,
        request_payload: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        request_hash = self._hash_payload(request_payload)
        now = _utcnow()
        result = await db.execute(
            select(IdempotencyKey).where(
                and_(
                    IdempotencyKey.idempotency_key == idempotency_key,
                    IdempotencyKey.scope == scope,
                    IdempotencyKey.expires_at > now,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            return None

        if existing.request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key reused with different request payload",
            )

        if existing.response_ref:
            try:
                return json.loads(existing.response_ref)
            except json.JSONDecodeError:
                return None
        return None

    async def store_response(
        self,
        db: AsyncSession,
        *,
        idempotency_key: str,
        scope: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        status_code: int = 200,
        ttl_hours: int = 24,
    ) -> None:
        request_hash = self._hash_payload(request_payload)
        now = _utcnow()
        expires_at = now + timedelta(hours=ttl_hours)

        result = await db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.idempotency_key == idempotency_key,
                IdempotencyKey.scope == scope,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.request_hash = request_hash
            existing.response_ref = json.dumps(response_payload, default=str)
            existing.status_code = status_code
            existing.expires_at = expires_at
            db.add(existing)
        else:
            record = IdempotencyKey(
                idempotency_key=idempotency_key,
                scope=scope,
                request_hash=request_hash,
                response_ref=json.dumps(response_payload, default=str),
                status_code=status_code,
                expires_at=expires_at,
            )
            db.add(record)
        await db.commit()

    @staticmethod
    def _hash_payload(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


idempotency_service = IdempotencyService()

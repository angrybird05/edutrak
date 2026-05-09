"""
Platform module — Event subscribers for audit logging.

Subscribes to auth and identity events to create audit trail entries.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from app.core.event_bus import event_bus
from app.shared.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    # AuditLog.created_at is currently stored as a naive timestamp in Postgres.
    # Normalize to naive UTC for compatibility with existing schema.
    return datetime.now(timezone.utc).replace(tzinfo=None)


@event_bus.on("auth.login_success")
async def audit_login_success(payload: dict) -> None:
    """Log successful logins to the audit trail."""
    try:
        from app.modules.platform.models import AuditLog
        async with SessionLocal() as db:
            db.add(AuditLog(
                user_id=UUID(payload["user_id"]) if payload.get("user_id") else None,
                action=f"LOGIN_SUCCESS_{payload.get('method', 'unknown').upper()}",
                resource_type="user",
                resource_id=payload.get("user_id"),
                details={"method": payload.get("method"), "ip": payload.get("ip")},
                ip_address=payload.get("ip"),
                created_at=_utcnow(),
            ))
            await db.commit()
    except Exception as e:
        logger.error("Failed to audit login success: %s", e)


@event_bus.on("auth.login_failed")
async def audit_login_failed(payload: dict) -> None:
    """Log failed login attempts to the audit trail."""
    try:
        from app.modules.platform.models import AuditLog
        async with SessionLocal() as db:
            db.add(AuditLog(
                action="LOGIN_FAILED",
                resource_type="user",
                details={
                    "phone": payload.get("phone"),
                    "username": payload.get("username"),
                    "reason": payload.get("reason"),
                    "ip": payload.get("ip"),
                },
                ip_address=payload.get("ip"),
                created_at=_utcnow(),
            ))
            await db.commit()
    except Exception as e:
        logger.error("Failed to audit login failure: %s", e)


@event_bus.on("identity.student_created")
async def audit_student_created(payload: dict) -> None:
    """Log student creation to the audit trail."""
    try:
        from app.modules.platform.models import AuditLog
        async with SessionLocal() as db:
            db.add(AuditLog(
                action="CREATE_STUDENT",
                resource_type="student",
                resource_id=payload.get("student_id"),
                school_id=UUID(payload["school_id"]) if payload.get("school_id") else None,
                student_id=UUID(payload["student_id"]) if payload.get("student_id") else None,
                details={"admission_number": payload.get("admission_number")},
                created_at=_utcnow(),
            ))
            await db.commit()
    except Exception as e:
        logger.error("Failed to audit student creation: %s", e)

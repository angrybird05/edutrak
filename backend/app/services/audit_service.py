from typing import Optional, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog

class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        *,
        user_id: Optional[UUID] = None,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        school_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        trace_id: Optional[str] = None,
    ):
        """
        Creates a new audit log entry.
        """
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            school_id=school_id,
            student_id=student_id,
            trace_id=trace_id,
        )
        self.db.add(audit_entry)
        await self.db.commit()

def get_audit_service(db: AsyncSession) -> AuditService:
    return AuditService(db)

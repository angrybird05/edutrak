from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scale_foundation import NotificationEvent, UserNotification
from app.models.student import Student, parent_student


class NotificationService:
    async def emit_event(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        actor_id: Optional[UUID],
        student_id: Optional[UUID],
        school_id: Optional[UUID],
        payload_json: dict,
        recipient_user_ids: Iterable[UUID],
        channel: str = "in_app",
    ) -> NotificationEvent:
        event = NotificationEvent(
            event_type=event_type,
            actor_id=actor_id,
            student_id=student_id,
            school_id=school_id,
            payload_json=payload_json,
        )
        db.add(event)
        await db.flush()

        for uid in set(recipient_user_ids):
            db.add(
                UserNotification(
                    event_id=event.id,
                    user_id=uid,
                    channel=channel,
                    status="unread",
                )
            )
        await db.commit()
        return event

    async def recipients_for_student(self, db: AsyncSession, *, student_id: UUID) -> set[UUID]:
        recipients: set[UUID] = set()
        student_result = await db.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalar_one_or_none()
        if not student:
            return recipients

        recipients.add(student.user_id)
        parent_ids_result = await db.execute(
            select(parent_student.c.parent_id).where(parent_student.c.student_id == student_id)
        )
        recipients.update(parent_ids_result.scalars().all())
        return recipients


notification_service = NotificationService()

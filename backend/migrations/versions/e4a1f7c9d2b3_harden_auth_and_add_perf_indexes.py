"""harden auth and add performance indexes

Revision ID: e4a1f7c9d2b3
Revises: c8f6d0e4a219
Create Date: 2026-03-27 23:05:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4a1f7c9d2b3"
down_revision: Union[str, Sequence[str], None] = "c8f6d0e4a219"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # OTP session hardening
    op.add_column(
        "otpsession",
        sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("otpsession", sa.Column("locked_until", sa.DateTime(), nullable=True))
    op.add_column("otpsession", sa.Column("request_ip", sa.String(), nullable=True))
    op.create_index(
        "ix_otpsession_phone_created_at",
        "otpsession",
        ["phone", "created_at"],
        unique=False,
    )

    # Query-path indexes
    op.create_index(
        "ix_attendance_student_date",
        "attendance",
        ["student_id", "date"],
        unique=False,
    )
    op.create_index(
        "ix_mark_student_exam_subject",
        "mark",
        ["student_id", "exam_id", "subject_id"],
        unique=False,
    )
    op.create_index(
        "ix_reportcard_student_generated_at",
        "reportcard",
        ["student_id", "generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_exam_section_exam_date",
        "exam",
        ["section_id", "exam_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_exam_section_exam_date", table_name="exam")
    op.drop_index("ix_reportcard_student_generated_at", table_name="reportcard")
    op.drop_index("ix_mark_student_exam_subject", table_name="mark")
    op.drop_index("ix_attendance_student_date", table_name="attendance")
    op.drop_index("ix_otpsession_phone_created_at", table_name="otpsession")
    op.drop_column("otpsession", "request_ip")
    op.drop_column("otpsession", "locked_until")
    op.drop_column("otpsession", "attempts_count")


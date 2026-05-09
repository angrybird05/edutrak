"""add ai insights v2 table

Revision ID: 0f9c6b3e1d2a
Revises: f2ce8a4511aa
Create Date: 2026-04-26 14:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0f9c6b3e1d2a"
down_revision: Union[str, Sequence[str], None] = "f2ce8a4511aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_insights",
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("insight_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("recommendations_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("performance_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_version", sa.String(), nullable=False, server_default="v2.0"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_ai_insights_status",
        ),
        sa.ForeignKeyConstraint(["exam_id"], ["exam.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "exam_id", name="uq_ai_insights_student_exam"),
    )
    op.create_index(
        "ix_ai_insights_student_exam",
        "ai_insights",
        ["student_id", "exam_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_insights_student_exam", table_name="ai_insights")
    op.drop_table("ai_insights")


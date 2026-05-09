"""add teacher subject assignments

Revision ID: f1a2b3c4d5e6
Revises: e7a1c2b4d903
Create Date: 2026-04-01 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e7a1c2b4d903"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teacher_subject",
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subject.id"), nullable=False),
        sa.PrimaryKeyConstraint("teacher_id", "subject_id"),
    )


def downgrade() -> None:
    op.drop_table("teacher_subject")

"""add section_subject assignments

Revision ID: a8f3e1b2c4d6
Revises: f1a2b3c4d5e6
Create Date: 2026-04-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a8f3e1b2c4d6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "section_subject",
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("section.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subject.id"), nullable=False),
        sa.PrimaryKeyConstraint("section_id", "subject_id"),
    )


def downgrade() -> None:
    op.drop_table("section_subject")

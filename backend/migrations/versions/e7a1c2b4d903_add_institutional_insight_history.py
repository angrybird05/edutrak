"""Add institutional insight history

Revision ID: e7a1c2b4d903
Revises: d4b2c6e8f901
Create Date: 2026-04-01 12:25:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7a1c2b4d903"
down_revision: Union[str, Sequence[str], None] = "d4b2c6e8f901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "institutionalinsight",
        sa.Column("school_id", sa.UUID(), nullable=True),
        sa.Column("summary_text", sa.String(), nullable=False),
        sa.Column("insight_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("prompt_version", sa.String(), server_default="v1.0", nullable=False),
        sa.Column("status", sa.String(), server_default="generated", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["school.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_institutionalinsight_school_id"), "institutionalinsight", ["school_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_institutionalinsight_school_id"), table_name="institutionalinsight")
    op.drop_table("institutionalinsight")

"""add mark_status for exam absence handling

Revision ID: 9d7c4a2b1f11
Revises: f12bf1a52c98
Create Date: 2026-03-27 21:42:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9d7c4a2b1f11"
down_revision = "f12bf1a52c98"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mark",
        sa.Column("mark_status", sa.String(), nullable=False, server_default="present"),
    )


def downgrade() -> None:
    op.drop_column("mark", "mark_status")

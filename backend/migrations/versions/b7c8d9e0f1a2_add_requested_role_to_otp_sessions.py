"""add requested role to otp sessions

Revision ID: b7c8d9e0f1a2
Revises: 91b2d4e6f8a1
Create Date: 2026-04-01 22:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7c8d9e0f1a2"
down_revision = "91b2d4e6f8a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("otpsession", sa.Column("requested_role", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("otpsession", "requested_role")

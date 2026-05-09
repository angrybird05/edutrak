"""scope user phone uniqueness to role

Revision ID: d1e2f3a4b5c6
Revises: b7c8d9e0f1a2
Create Date: 2026-04-01 23:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_user_phone", table_name="user")
    op.create_index("ix_user_phone", "user", ["phone"], unique=False)
    op.create_unique_constraint("uq_user_role_phone", "user", ["role", "phone"])


def downgrade() -> None:
    op.drop_constraint("uq_user_role_phone", "user", type_="unique")
    op.drop_index("ix_user_phone", table_name="user")
    op.create_index("ix_user_phone", "user", ["phone"], unique=True)

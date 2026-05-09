"""Sync school schema with modular models

Revision ID: d4b2c6e8f901
Revises: bd42a19b945f
Create Date: 2026-04-01 11:35:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4b2c6e8f901"
down_revision: Union[str, Sequence[str], None] = "bd42a19b945f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("school", sa.Column("email", sa.String(), nullable=True))
    op.add_column("school", sa.Column("village", sa.String(), nullable=True))
    op.add_column("school", sa.Column("mandal", sa.String(), nullable=True))
    op.add_column("school", sa.Column("district_city", sa.String(), nullable=True))
    op.add_column("school", sa.Column("pincode", sa.String(), nullable=True))

    op.execute("UPDATE school SET district_city = COALESCE(district_city, city, '')")
    op.execute("UPDATE school SET pincode = COALESCE(pincode, '')")

    op.alter_column("school", "district_city", existing_type=sa.String(), nullable=False)
    op.alter_column("school", "pincode", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("school", "pincode")
    op.drop_column("school", "district_city")
    op.drop_column("school", "mandal")
    op.drop_column("school", "village")
    op.drop_column("school", "email")

"""add mark_status check constraint

Revision ID: c8f6d0e4a219
Revises: b1c4a7d3e2f0
Create Date: 2026-03-27 22:12:00
"""

from alembic import context
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8f6d0e4a219"
down_revision = "b1c4a7d3e2f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize bad legacy values before adding strict constraint.
    op.execute(
        "UPDATE mark SET mark_status = 'present' "
        "WHERE mark_status IS NULL OR LOWER(mark_status) NOT IN ('present','absent','exempt')"
    )

    if context.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("mark") as batch_op:
            batch_op.create_check_constraint(
                "ck_mark_mark_status_valid",
                "LOWER(mark_status) IN ('present','absent','exempt')",
            )
    else:
        op.create_check_constraint(
            "ck_mark_mark_status_valid",
            "mark",
            "LOWER(mark_status) IN ('present','absent','exempt')",
        )


def downgrade() -> None:
    if context.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("mark") as batch_op:
            batch_op.drop_constraint("ck_mark_mark_status_valid", type_="check")
    else:
        op.drop_constraint("ck_mark_mark_status_valid", "mark", type_="check")

"""scope student admission number uniqueness to a school

Revision ID: 91b2d4e6f8a1
Revises: 6f4d2c9b7a10
Create Date: 2026-04-01 21:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "91b2d4e6f8a1"
down_revision = "6f4d2c9b7a10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_student_admission_number", table_name="student")
    op.create_index("ix_student_admission_number", "student", ["admission_number"], unique=False)
    op.create_unique_constraint(
        "uq_student_school_admission_number",
        "student",
        ["school_id", "admission_number"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_student_school_admission_number", "student", type_="unique")
    op.drop_index("ix_student_admission_number", table_name="student")
    op.create_index("ix_student_admission_number", "student", ["admission_number"], unique=True)

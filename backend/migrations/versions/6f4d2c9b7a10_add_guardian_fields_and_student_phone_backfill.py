"""add guardian fields and backfill shared student login data

Revision ID: 6f4d2c9b7a10
Revises: a8f3e1b2c4d6
Create Date: 2026-04-01 19:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6f4d2c9b7a10"
down_revision = "a8f3e1b2c4d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student", sa.Column("guardian_name", sa.String(), nullable=True))
    op.add_column("student", sa.Column("guardian_relation", sa.String(), nullable=True))
    op.add_column("student", sa.Column("guardian_phone", sa.String(), nullable=True))
    op.create_index("ix_student_guardian_phone", "student", ["guardian_phone"], unique=False)

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE student AS s
            SET guardian_phone = u.phone
            FROM "user" AS u
            WHERE s.user_id = u.id
              AND s.guardian_phone IS NULL
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE "user" AS u
            SET phone = 'student_' || REPLACE(CAST(u.id AS TEXT), '-', '')
            FROM student AS s
            WHERE s.user_id = u.id
              AND u.role = 'STUDENT'
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_student_guardian_phone", table_name="student")
    op.drop_column("student", "guardian_phone")
    op.drop_column("student", "guardian_relation")
    op.drop_column("student", "guardian_name")

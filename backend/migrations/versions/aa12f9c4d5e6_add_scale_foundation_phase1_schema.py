"""add scale foundation phase1 schema

Revision ID: aa12f9c4d5e6
Revises: e4a1f7c9d2b3
Create Date: 2026-03-28 11:10:00
"""

from typing import Sequence, Union

from alembic import context
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aa12f9c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e4a1f7c9d2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1.1: notification_event
    op.create_table(
        "notification_event",
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("student_id", sa.UUID(), nullable=True),
        sa.Column("school_id", sa.UUID(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["school.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_event_event_type_created_at",
        "notification_event",
        ["event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_notification_event_student_created_at",
        "notification_event",
        ["student_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_notification_event_school_created_at",
        "notification_event",
        ["school_id", "created_at"],
        unique=False,
    )

    # Step 1.2: user_notification
    op.create_table(
        "user_notification",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["notification_event.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id", "channel", name="uq_user_notification_event_user_channel"),
    )
    op.create_index(
        "ix_user_notification_user_read_at",
        "user_notification",
        ["user_id", "read_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_notification_user_created_at",
        "user_notification",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_notification_status_created_at",
        "user_notification",
        ["status", "created_at"],
        unique=False,
    )

    # Step 1.3: device_token
    op.create_table(
        "device_token",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        "ix_device_token_user_active",
        "device_token",
        ["user_id", "is_active"],
        unique=False,
    )

    # Step 1.4: idempotency_key
    op.create_table(
        "idempotency_key",
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("response_ref", sa.String(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_idempotency_key_scope",
        "idempotency_key",
        ["idempotency_key", "scope"],
        unique=False,
    )
    op.create_index(
        "ix_idempotency_key_expires_at",
        "idempotency_key",
        ["expires_at"],
        unique=False,
    )

    # Step 1.5: outbox_job
    op.create_table(
        "outbox_job",
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbox_job_status_next_run_at",
        "outbox_job",
        ["status", "next_run_at"],
        unique=False,
    )
    op.create_index(
        "ix_outbox_job_job_type_created_at",
        "outbox_job",
        ["job_type", "created_at"],
        unique=False,
    )

    # Step 1.6: audit extension + api_request_log
    op.add_column("auditlog", sa.Column("school_id", sa.UUID(), nullable=True))
    op.add_column("auditlog", sa.Column("student_id", sa.UUID(), nullable=True))
    op.add_column("auditlog", sa.Column("trace_id", sa.String(), nullable=True))
    if context.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("auditlog") as batch_op:
            batch_op.create_foreign_key(
                "fk_auditlog_school_id_school",
                "school",
                ["school_id"],
                ["id"],
            )
            batch_op.create_foreign_key(
                "fk_auditlog_student_id_student",
                "student",
                ["student_id"],
                ["id"],
            )
    else:
        op.create_foreign_key(
            "fk_auditlog_school_id_school",
            "auditlog",
            "school",
            ["school_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_auditlog_student_id_student",
            "auditlog",
            "student",
            ["student_id"],
            ["id"],
        )
    op.create_index("ix_auditlog_action_created_at", "auditlog", ["action", "created_at"], unique=False)
    op.create_index("ix_auditlog_user_created_at", "auditlog", ["user_id", "created_at"], unique=False)
    op.create_index("ix_auditlog_school_created_at", "auditlog", ["school_id", "created_at"], unique=False)
    op.create_index("ix_auditlog_student_created_at", "auditlog", ["student_id", "created_at"], unique=False)
    op.create_index("ix_auditlog_trace_id_created_at", "auditlog", ["trace_id", "created_at"], unique=False)

    op.create_table(
        "api_request_log",
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_api_request_log_trace_id_created_at",
        "api_request_log",
        ["trace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_api_request_log_user_created_at",
        "api_request_log",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_api_request_log_path_method_created_at",
        "api_request_log",
        ["path", "method", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_api_request_log_status_created_at",
        "api_request_log",
        ["status_code", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_api_request_log_status_created_at", table_name="api_request_log")
    op.drop_index("ix_api_request_log_path_method_created_at", table_name="api_request_log")
    op.drop_index("ix_api_request_log_user_created_at", table_name="api_request_log")
    op.drop_index("ix_api_request_log_trace_id_created_at", table_name="api_request_log")
    op.drop_table("api_request_log")

    op.drop_index("ix_auditlog_trace_id_created_at", table_name="auditlog")
    op.drop_index("ix_auditlog_student_created_at", table_name="auditlog")
    op.drop_index("ix_auditlog_school_created_at", table_name="auditlog")
    op.drop_index("ix_auditlog_user_created_at", table_name="auditlog")
    op.drop_index("ix_auditlog_action_created_at", table_name="auditlog")
    if context.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("auditlog") as batch_op:
            batch_op.drop_constraint("fk_auditlog_student_id_student", type_="foreignkey")
            batch_op.drop_constraint("fk_auditlog_school_id_school", type_="foreignkey")
    else:
        op.drop_constraint("fk_auditlog_student_id_student", "auditlog", type_="foreignkey")
        op.drop_constraint("fk_auditlog_school_id_school", "auditlog", type_="foreignkey")
    op.drop_column("auditlog", "trace_id")
    op.drop_column("auditlog", "student_id")
    op.drop_column("auditlog", "school_id")

    op.drop_index("ix_outbox_job_job_type_created_at", table_name="outbox_job")
    op.drop_index("ix_outbox_job_status_next_run_at", table_name="outbox_job")
    op.drop_table("outbox_job")

    op.drop_index("ix_idempotency_key_expires_at", table_name="idempotency_key")
    op.drop_index("ix_idempotency_key_scope", table_name="idempotency_key")
    op.drop_table("idempotency_key")

    op.drop_index("ix_device_token_user_active", table_name="device_token")
    op.drop_table("device_token")

    op.drop_index("ix_user_notification_status_created_at", table_name="user_notification")
    op.drop_index("ix_user_notification_user_created_at", table_name="user_notification")
    op.drop_index("ix_user_notification_user_read_at", table_name="user_notification")
    op.drop_table("user_notification")

    op.drop_index("ix_notification_event_school_created_at", table_name="notification_event")
    op.drop_index("ix_notification_event_student_created_at", table_name="notification_event")
    op.drop_index("ix_notification_event_event_type_created_at", table_name="notification_event")
    op.drop_table("notification_event")

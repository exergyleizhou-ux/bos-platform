"""001 — Initial Schema: tenants, users, batches, calculations, audit_log

Revision ID: 001_initial
Revises: None
Create Date: 2024-01-01 00:01:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    timestamp_default = sa.text("CURRENT_TIMESTAMP") if is_sqlite else sa.text("NOW()")
    big_int_pk = sa.Integer() if is_sqlite else sa.BigInteger()
    # ══════════════════════════════════════
    # 1. Tenants
    # ══════════════════════════════════════
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("max_batches", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("max_calculations", sa.Integer(), nullable=False, server_default=sa.text("1000")),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_is_active", "tenants", ["is_active"])
    op.create_index("ix_tenants_plan", "tenants", ["plan"])

    # ══════════════════════════════════════
    # 2. Users
    # ══════════════════════════════════════
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_tenant_role", "users", ["tenant_id", "role"])

    # ══════════════════════════════════════
    # 3. Batches
    # ══════════════════════════════════════
    op.create_table(
        "batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.String(100), nullable=False),
        sa.Column("species", sa.String(100), nullable=False, server_default="BSF"),
        sa.Column("substrate", sa.String(255), nullable=True),
        sa.Column("dm_in", sa.Float(), nullable=True),
        sa.Column("dm_out", sa.Float(), nullable=True),
        sa.Column("n_in", sa.Float(), nullable=True),
        sa.Column("n_larvae", sa.Float(), nullable=True),
        sa.Column("n_frass", sa.Float(), nullable=True),
        sa.Column("ash_in", sa.Float(), nullable=True),
        sa.Column("ash_out", sa.Float(), nullable=True),
        sa.Column("fat_in", sa.Float(), nullable=True),
        sa.Column("fat_out", sa.Float(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("moisture", sa.Float(), nullable=True),
        sa.Column("feed_rate", sa.Float(), nullable=True),
        sa.Column("density", sa.Float(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="logged"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("operator", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("batch_date", sa.Date(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_batches_batch_id", "batches", ["batch_id"])
    op.create_index("ix_batches_tenant_id", "batches", ["tenant_id"])
    op.create_index("ix_batches_user_id", "batches", ["user_id"])
    op.create_index("ix_batches_species", "batches", ["species"])
    op.create_index("ix_batches_status", "batches", ["status"])
    op.create_index("ix_batches_created_at", "batches", ["created_at"])
    op.create_index("ix_batches_batch_date", "batches", ["batch_date"])
    op.create_index("ix_batches_tenant_status", "batches", ["tenant_id", "status"])
    op.create_index("ix_batches_tenant_species", "batches", ["tenant_id", "species"])
    op.create_index("ix_batches_tenant_created", "batches", ["tenant_id", "created_at"])
    op.create_index("ix_batches_valid_range", "batches", ["valid_from", "valid_to"])

    # ══════════════════════════════════════
    # 4. Calculations
    # ══════════════════════════════════════
    op.create_table(
        "calculations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("calc_type", sa.String(50), nullable=False, server_default="ser"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("inputs", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("ser_value", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("fail_codes", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("mc_samples", sa.Integer(), nullable=True),
        sa.Column("engine_version", sa.String(50), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_calculations_batch_id", "calculations", ["batch_id"])
    op.create_index("ix_calculations_tenant_id", "calculations", ["tenant_id"])
    op.create_index("ix_calculations_user_id", "calculations", ["user_id"])
    op.create_index("ix_calculations_calc_type", "calculations", ["calc_type"])
    op.create_index("ix_calculations_status", "calculations", ["status"])
    op.create_index("ix_calculations_passed", "calculations", ["passed"])
    op.create_index("ix_calculations_created_at", "calculations", ["created_at"])
    op.create_index("ix_calculations_tenant_type", "calculations", ["tenant_id", "calc_type"])
    op.create_index("ix_calculations_tenant_passed", "calculations", ["tenant_id", "passed"])

    # ══════════════════════════════════════
    # 5. Audit Log
    # ══════════════════════════════════════
    op.create_table(
        "audit_log",
        sa.Column("id", big_int_pk, autoincrement=True, nullable=False),
        sa.Column("table_name", sa.String(100), nullable=True),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource", sa.String(255), nullable=True),
        sa.Column("old_data", sa.JSON(), nullable=True),
        sa.Column("new_data", sa.JSON(), nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("username", sa.String(150), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_table_name", "audit_log", ["table_name"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_tenant_action", "audit_log", ["tenant_id", "action"])
    op.create_index("ix_audit_log_tenant_created", "audit_log", ["tenant_id", "created_at"])

    # ══════════════════════════════════════
    # 6. Row-Level Security Policies
    # ══════════════════════════════════════
    # Enable RLS on tenant-scoped tables
    if not is_sqlite:
        for table in ["users", "batches", "calculations", "audit_log"]:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

            # Policy: users can only see rows belonging to their tenant
            op.execute(
                f"""
                CREATE POLICY tenant_isolation_select ON {table}
                FOR SELECT
                USING (tenant_id = current_tenant_id() OR current_tenant_id() = 0)
            """
            )

            op.execute(
                f"""
                CREATE POLICY tenant_isolation_insert ON {table}
                FOR INSERT
                WITH CHECK (tenant_id = current_tenant_id() OR current_tenant_id() = 0)
            """
            )

            op.execute(
                f"""
                CREATE POLICY tenant_isolation_update ON {table}
                FOR UPDATE
                USING (tenant_id = current_tenant_id() OR current_tenant_id() = 0)
            """
            )

            op.execute(
                f"""
                CREATE POLICY tenant_isolation_delete ON {table}
                FOR DELETE
                USING (tenant_id = current_tenant_id() OR current_tenant_id() = 0)
            """
            )

    # ══════════════════════════════════════
    # 7. Triggers
    # ══════════════════════════════════════
    # updated_at auto-timestamp
    if not is_sqlite:
        for table in ["tenants", "users", "batches"]:
            op.execute(
                f"""
                CREATE TRIGGER trg_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
            """
            )

        # Prevent tenant_id changes
        for table in ["users", "batches", "calculations"]:
            op.execute(
                f"""
                CREATE TRIGGER trg_{table}_prevent_tenant_change
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION prevent_tenant_change()
            """
            )

        # Audit triggers on batches and calculations
        for table in ["batches", "calculations"]:
            op.execute(
                f"""
                CREATE TRIGGER trg_{table}_audit
                AFTER INSERT OR UPDATE OR DELETE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION audit_trigger_func()
            """
            )


def downgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    if not is_sqlite:
        # Drop triggers
        for table in ["batches", "calculations"]:
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_audit ON {table}")
        for table in ["users", "batches", "calculations"]:
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_prevent_tenant_change ON {table}")
        for table in ["tenants", "users", "batches"]:
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")

        # Drop RLS policies
        for table in ["users", "batches", "calculations", "audit_log"]:
            for action in ["select", "insert", "update", "delete"]:
                op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{action} ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse dependency order
    op.drop_table("audit_log")
    op.drop_table("calculations")
    op.drop_table("batches")
    op.drop_table("users")
    op.drop_table("tenants")

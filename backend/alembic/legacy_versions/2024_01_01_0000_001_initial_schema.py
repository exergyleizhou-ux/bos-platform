"""
BOS Pipeline v9.0 �� Initial Database Schema

Revision ID: 001
Create Date: 2024-01-01 00:00:00.000000+00:00

Creates all core tables:
  - tenants
  - users
  - batches
  - calculations
  - digital_twins
  - digital_twin_snapshots
  - audit_logs
  - webhooks
  - api_keys

Plus:
  - Indexes for performance
  - RLS policies for multi-tenant isolation
  - Materialized views for dashboard
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # tenants
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("max_batches", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("max_calculations", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("billing_email", sa.String(255), nullable=True),
        sa.Column("settings", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # users
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preferences", JSONB, nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # batches
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.String(100), nullable=False),
        sa.Column("species", sa.String(100), nullable=False, server_default="BSF"),
        sa.Column("status", sa.String(50), nullable=False, server_default="logged"),
        sa.Column("dm_in", sa.Float(), nullable=True),
        sa.Column("dm_out", sa.Float(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
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
        sa.Column("operator", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("batch_date", sa.Date(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_batches_tenant_id", "batches", ["tenant_id"])
    op.create_index("ix_batches_species", "batches", ["species"])
    op.create_index("ix_batches_status", "batches", ["status"])
    op.create_index("ix_batches_batch_date", "batches", ["batch_date"])
    op.create_index("ix_batches_tenant_species", "batches", ["tenant_id", "species"])
    op.create_index("ix_batches_tenant_status", "batches", ["tenant_id", "status"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # calculations
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "calculations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("calc_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("inputs", JSONB, nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("ser_value", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("fail_codes", JSONB, nullable=True),
        sa.Column("mc_samples", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("engine_version", sa.String(50), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_calculations_tenant_id", "calculations", ["tenant_id"])
    op.create_index("ix_calculations_batch_id", "calculations", ["batch_id"])
    op.create_index("ix_calculations_calc_type", "calculations", ["calc_type"])
    op.create_index("ix_calculations_status", "calculations", ["status"])
    op.create_index("ix_calculations_tenant_type", "calculations", ["tenant_id", "calc_type"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # digital_twins
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "digital_twins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("twin_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("species", sa.String(100), nullable=False, server_default="BSF"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("state", JSONB, nullable=True),
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_digital_twins_tenant_id", "digital_twins", ["tenant_id"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # digital_twin_snapshots
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "digital_twin_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("twin_id", sa.Integer(), sa.ForeignKey("digital_twins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", JSONB, nullable=True),
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column("trigger", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_dt_snapshots_twin_id", "digital_twin_snapshots", ["twin_id"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # audit_logs
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # webhooks
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "webhooks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("events", JSONB, nullable=False),
        sa.Column("secret", sa.String(256), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("headers", JSONB, nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_triggered", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_webhooks_tenant_id", "webhooks", ["tenant_id"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # api_keys
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("scopes", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # Row-Level Security Policies
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    rls_tables = ["batches", "calculations", "digital_twins", "audit_logs", "webhooks", "api_keys"]
    for table in rls_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.current_tenant_id', true)::int)
        """)

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # Materialized Views
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_tenant_batch_stats AS
        SELECT
            tenant_id,
            COUNT(*) AS total_batches,
            COUNT(*) FILTER (WHERE status = 'active') AS active_batches,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed_batches,
            AVG(score) FILTER (WHERE score IS NOT NULL) AS avg_ser,
            MIN(created_at) AS first_batch_at,
            MAX(created_at) AS last_batch_at
        FROM batches
        GROUP BY tenant_id
    """)
    op.execute("CREATE UNIQUE INDEX ON mv_tenant_batch_stats (tenant_id)")

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ser_daily_trend AS
        SELECT
            tenant_id,
            batch_date,
            AVG(score) AS avg_ser,
            COUNT(*) AS batch_count
        FROM batches
        WHERE batch_date IS NOT NULL AND score IS NOT NULL
        GROUP BY tenant_id, batch_date
        ORDER BY tenant_id, batch_date
    """)
    op.execute("CREATE UNIQUE INDEX ON mv_ser_daily_trend (tenant_id, batch_date)")

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_species_distribution AS
        SELECT
            tenant_id,
            species,
            COUNT(*) AS batch_count,
            AVG(score) FILTER (WHERE score IS NOT NULL) AS avg_ser
        FROM batches
        GROUP BY tenant_id, species
    """)
    op.execute("CREATE UNIQUE INDEX ON mv_species_distribution (tenant_id, species)")


def downgrade() -> None:
    # Drop materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_species_distribution")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_ser_daily_trend")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_tenant_batch_stats")

    # Drop RLS policies
    rls_tables = ["batches", "calculations", "digital_twins", "audit_logs", "webhooks", "api_keys"]
    for table in rls_tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse dependency order
    op.drop_table("api_keys")
    op.drop_table("webhooks")
    op.drop_table("audit_logs")
    op.drop_table("digital_twin_snapshots")
    op.drop_table("digital_twins")
    op.drop_table("calculations")
    op.drop_table("batches")
    op.drop_table("users")
    op.drop_table("tenants")

"""003 �� Feature flags and notification preferences tables

Revision ID: 003_feature_flags
Revises: 002_api_keys_webhooks
Create Date: 2024-02-01 00:03:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_feature_flags"
down_revision: Union[str, None] = "002_api_keys_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # 1. Feature Flags (runtime overrides)
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("percentage_rollout", sa.Integer(), nullable=True),
        sa.Column("tenant_overrides", sa.JSON(), nullable=True),
        sa.Column("user_overrides", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feature_flags_name", "feature_flags", ["name"], unique=True)

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # 2. Notification Preferences
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("weekly_digest", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ser_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("anomaly_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("batch_complete_alerts", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("webhook_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_notification_prefs_user"),
    )
    op.create_index("ix_notification_prefs_user_id", "notification_preferences", ["user_id"])
    op.create_index("ix_notification_prefs_tenant_id", "notification_preferences", ["tenant_id"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # 3. Scheduled Reports
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "scheduled_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("schedule_cron", sa.String(100), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("recipients", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_scheduled_reports_tenant_id", "scheduled_reports", ["tenant_id"])
    op.create_index("ix_scheduled_reports_is_active", "scheduled_reports", ["is_active"])
    op.create_index("ix_scheduled_reports_next_run", "scheduled_reports", ["next_run"])

    # ���� RLS for notification_preferences and scheduled_reports ����
    for table in ["notification_preferences", "scheduled_reports"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        for action in ["select", "insert", "update", "delete"]:
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action} ON {table}
                FOR {action.upper()}
                {"USING" if action != "insert" else "WITH CHECK"} (tenant_id = current_tenant_id() OR current_tenant_id() = 0)
            """)

    # ���� Triggers ����
    op.execute("""
        CREATE TRIGGER trg_feature_flags_updated_at
        BEFORE UPDATE ON feature_flags
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)

    op.execute("""
        CREATE TRIGGER trg_notification_prefs_updated_at
        BEFORE UPDATE ON notification_preferences
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)

    op.execute("""
        CREATE TRIGGER trg_scheduled_reports_updated_at
        BEFORE UPDATE ON scheduled_reports
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)

    # ���� Seed default feature flags ����
    op.execute("""
        INSERT INTO feature_flags (name, description, enabled) VALUES
        ('enable_monte_carlo', 'Monte Carlo simulation engine', true),
        ('enable_digital_twin', 'Digital Twin management', true),
        ('enable_automl', 'AutoML hyperparameter optimization', false),
        ('enable_websocket', 'Real-time WebSocket streaming', true),
        ('enable_export_parquet', 'Parquet format data export', true),
        ('enable_billing', 'Stripe billing integration', true),
        ('enable_multi_language', 'Multi-language i18n support', true),
        ('enable_dark_mode', 'Dark mode theme toggle', true)
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_scheduled_reports_updated_at ON scheduled_reports")
    op.execute("DROP TRIGGER IF EXISTS trg_notification_prefs_updated_at ON notification_preferences")
    op.execute("DROP TRIGGER IF EXISTS trg_feature_flags_updated_at ON feature_flags")

    # Drop RLS policies
    for table in ["notification_preferences", "scheduled_reports"]:
        for action in ["select", "insert", "update", "delete"]:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{action} ON {table}")

    # Drop tables
    op.drop_table("scheduled_reports")
    op.drop_table("notification_preferences")
    op.drop_table("feature_flags")

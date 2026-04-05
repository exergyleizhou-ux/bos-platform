"""004 �� Digital Twins and Traces tables

Revision ID: 004_digital_twins
Revises: 003_feature_flags
Create Date: 2024-03-01 00:04:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_digital_twins"
down_revision: Union[str, None] = "003_feature_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # 1. Digital Twins
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "digital_twins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("twin_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("species", sa.String(100), nullable=False, server_default="BSF"),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("last_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_digital_twins_twin_id", "digital_twins", ["twin_id"])
    op.create_index("ix_digital_twins_tenant_id", "digital_twins", ["tenant_id"])
    op.create_index("ix_digital_twins_user_id", "digital_twins", ["user_id"])
    op.create_index("ix_digital_twins_species", "digital_twins", ["species"])
    op.create_index("ix_digital_twins_is_active", "digital_twins", ["is_active"])
    op.create_index("ix_digital_twins_tenant_twin", "digital_twins", ["tenant_id", "twin_id"], unique=True)

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # 2. Digital Twin Snapshots (history)
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "digital_twin_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("twin_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("trigger", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["twin_id"], ["digital_twins.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_twin_snapshots_twin_id", "digital_twin_snapshots", ["twin_id"])
    op.create_index("ix_twin_snapshots_created_at", "digital_twin_snapshots", ["created_at"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # 3. Traces (internal request tracing)
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "traces",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("span_id", sa.String(32), nullable=True),
        sa.Column("parent_span_id", sa.String(32), nullable=True),
        sa.Column("operation", sa.String(255), nullable=False),
        sa.Column("service", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("events", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_traces_trace_id", "traces", ["trace_id"])
    op.create_index("ix_traces_operation", "traces", ["operation"])
    op.create_index("ix_traces_service", "traces", ["service"])
    op.create_index("ix_traces_timestamp", "traces", ["timestamp"])
    op.create_index("ix_traces_tenant_id", "traces", ["tenant_id"])
    op.create_index("ix_traces_duration", "traces", ["duration_ms"])

    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    # 4. GDPR Data Deletion Requests
    # �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
    op.create_table(
        "gdpr_deletion_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_by", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_gdpr_deletion_user_id", "gdpr_deletion_requests", ["user_id"])
    op.create_index("ix_gdpr_deletion_status", "gdpr_deletion_requests", ["status"])
    op.create_index("ix_gdpr_deletion_requested_at", "gdpr_deletion_requests", ["requested_at"])

    # ���� RLS for new tables ����
    for table in ["digital_twins"]:
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
        CREATE TRIGGER trg_digital_twins_updated_at
        BEFORE UPDATE ON digital_twins
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)

    op.execute("""
        CREATE TRIGGER trg_digital_twins_prevent_tenant_change
        BEFORE UPDATE ON digital_twins
        FOR EACH ROW
        EXECUTE FUNCTION prevent_tenant_change()
    """)

    # ���� Auto-snapshot trigger on digital twin state changes ����
    op.execute("""
        CREATE OR REPLACE FUNCTION digital_twin_snapshot_func()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.state IS DISTINCT FROM NEW.state THEN
                INSERT INTO digital_twin_snapshots (twin_id, state, parameters, trigger)
                VALUES (NEW.id, OLD.state, OLD.parameters, 'auto');
                NEW.version := OLD.version + 1;
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    op.execute("""
        CREATE TRIGGER trg_digital_twins_auto_snapshot
        BEFORE UPDATE ON digital_twins
        FOR EACH ROW
        EXECUTE FUNCTION digital_twin_snapshot_func()
    """)

    # ���� Partition traces table by month (for production volume) ����
    # Note: This is a hint for future optimization.
    # In PostgreSQL, partitioning existing tables requires recreation.
    # For now, we rely on indexes and periodic cleanup via Celery beat.
    op.execute("""
        COMMENT ON TABLE traces IS 'Request traces. Consider partitioning by month for >1M rows.'
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_digital_twins_auto_snapshot ON digital_twins")
    op.execute("DROP FUNCTION IF EXISTS digital_twin_snapshot_func()")
    op.execute("DROP TRIGGER IF EXISTS trg_digital_twins_prevent_tenant_change ON digital_twins")
    op.execute("DROP TRIGGER IF EXISTS trg_digital_twins_updated_at ON digital_twins")

    # Drop RLS policies
    for action in ["select", "insert", "update", "delete"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{action} ON digital_twins")

    # Drop tables
    op.drop_table("gdpr_deletion_requests")
    op.drop_table("traces")
    op.drop_table("digital_twin_snapshots")
    op.drop_table("digital_twins")

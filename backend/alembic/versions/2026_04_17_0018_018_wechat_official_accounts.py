"""018 add wechat official account integration tables

Revision ID: 018_wechat_official_accounts
Revises: 017_bos_code_task_packets
Create Date: 2026-04-17 09:30:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "018_wechat_official_accounts"
down_revision: Union[str, None] = "017_bos_code_task_packets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wechat_official_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("default_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("account_key", sa.String(length=100), nullable=False),
        sa.Column("app_id", sa.String(length=128), nullable=False),
        sa.Column("app_secret", sa.String(length=255), nullable=True),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("encoding_aes_key", sa.String(length=255), nullable=True),
        sa.Column("welcome_message", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_access_token", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["default_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_key", name="uq_wechat_official_accounts_account_key"),
    )
    op.create_index(op.f("ix_wechat_official_accounts_tenant_id"), "wechat_official_accounts", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_wechat_official_accounts_default_user_id"),
        "wechat_official_accounts",
        ["default_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wechat_official_accounts_account_key"),
        "wechat_official_accounts",
        ["account_key"],
        unique=True,
    )
    op.create_index(op.f("ix_wechat_official_accounts_is_active"), "wechat_official_accounts", ["is_active"], unique=False)

    op.create_table(
        "wechat_contact_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("official_account_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("openid", sa.String(length=128), nullable=False),
        sa.Column("unionid", sa.String(length=128), nullable=True),
        sa.Column("default_session_id", sa.Integer(), nullable=True),
        sa.Column("last_inbound_message", sa.Text(), nullable=True),
        sa.Column("last_outbound_message", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["official_account_id"], ["wechat_official_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["default_session_id"], ["code_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "official_account_id",
            "openid",
            name="uq_wechat_contact_bindings_account_openid",
        ),
    )
    op.create_index(
        op.f("ix_wechat_contact_bindings_official_account_id"),
        "wechat_contact_bindings",
        ["official_account_id"],
        unique=False,
    )
    op.create_index(op.f("ix_wechat_contact_bindings_tenant_id"), "wechat_contact_bindings", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_wechat_contact_bindings_user_id"), "wechat_contact_bindings", ["user_id"], unique=False)
    op.create_index(op.f("ix_wechat_contact_bindings_openid"), "wechat_contact_bindings", ["openid"], unique=False)
    op.create_index(op.f("ix_wechat_contact_bindings_unionid"), "wechat_contact_bindings", ["unionid"], unique=False)
    op.create_index(
        op.f("ix_wechat_contact_bindings_default_session_id"),
        "wechat_contact_bindings",
        ["default_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wechat_contact_bindings_last_message_at"),
        "wechat_contact_bindings",
        ["last_message_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_wechat_contact_bindings_last_message_at"), table_name="wechat_contact_bindings")
    op.drop_index(op.f("ix_wechat_contact_bindings_default_session_id"), table_name="wechat_contact_bindings")
    op.drop_index(op.f("ix_wechat_contact_bindings_unionid"), table_name="wechat_contact_bindings")
    op.drop_index(op.f("ix_wechat_contact_bindings_openid"), table_name="wechat_contact_bindings")
    op.drop_index(op.f("ix_wechat_contact_bindings_user_id"), table_name="wechat_contact_bindings")
    op.drop_index(op.f("ix_wechat_contact_bindings_tenant_id"), table_name="wechat_contact_bindings")
    op.drop_index(op.f("ix_wechat_contact_bindings_official_account_id"), table_name="wechat_contact_bindings")
    op.drop_table("wechat_contact_bindings")

    op.drop_index(op.f("ix_wechat_official_accounts_is_active"), table_name="wechat_official_accounts")
    op.drop_index(op.f("ix_wechat_official_accounts_account_key"), table_name="wechat_official_accounts")
    op.drop_index(op.f("ix_wechat_official_accounts_default_user_id"), table_name="wechat_official_accounts")
    op.drop_index(op.f("ix_wechat_official_accounts_tenant_id"), table_name="wechat_official_accounts")
    op.drop_table("wechat_official_accounts")

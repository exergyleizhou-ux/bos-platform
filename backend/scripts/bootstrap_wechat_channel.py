"""Bootstrap a local admin user and optionally seed a WeChat official account."""

from __future__ import annotations

import argparse
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import async_session_factory
from app.models import Tenant, User, WechatOfficialAccount
from app.routers.auth import create_access_token
from app.security.passwords import pwd_context


async def _resolve_tenant_id(session, tenant_id: int | None) -> int:
    if tenant_id is not None:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            raise RuntimeError(f"Tenant {tenant_id} does not exist")
        return tenant.id

    result = await session.execute(select(Tenant).order_by(Tenant.id.asc()))
    tenant = result.scalars().first()
    if tenant is None:
        raise RuntimeError("No tenant exists; create a tenant first")
    return tenant.id


async def _ensure_admin(session, *, tenant_id: int, username: str, password: str | None) -> tuple[User, str | None]:
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    generated_password = password
    if generated_password is None:
        generated_password = secrets.token_urlsafe(18)

    if user is None:
        user = User(
            username=username,
            full_name="WeChat Channel Admin",
            email=f"{username}@local.bos",
            hashed_password=pwd_context.hash(generated_password),
            role="admin",
            is_active=True,
            tenant_id=tenant_id,
            password_changed_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
        return user, generated_password

    user.role = "admin"
    user.is_active = True
    user.tenant_id = tenant_id
    if password is not None:
        user.hashed_password = pwd_context.hash(password)
        user.password_changed_at = datetime.now(UTC)
        generated_password = password
    else:
        generated_password = None
    await session.flush()
    return user, generated_password


async def _upsert_account(
    session,
    *,
    tenant_id: int,
    default_user_id: int,
    account_key: str,
    name: str,
    app_id: str,
    app_secret: str | None,
    token: str,
) -> WechatOfficialAccount:
    result = await session.execute(select(WechatOfficialAccount).where(WechatOfficialAccount.account_key == account_key))
    account = result.scalar_one_or_none()
    if account is None:
        account = WechatOfficialAccount(
            tenant_id=tenant_id,
            default_user_id=default_user_id,
            name=name,
            account_key=account_key,
            app_id=app_id,
            app_secret=app_secret,
            token=token,
            is_active=True,
        )
        session.add(account)
    else:
        account.tenant_id = tenant_id
        account.default_user_id = default_user_id
        account.name = name
        account.app_id = app_id
        account.app_secret = app_secret
        account.token = token
        account.is_active = True
    await session.flush()
    return account


async def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap BOS WeChat integration")
    parser.add_argument("--tenant-id", type=int, default=None)
    parser.add_argument("--admin-username", default="wechat_admin")
    parser.add_argument("--admin-password", default=None)
    parser.add_argument("--account-key", default=None)
    parser.add_argument("--account-name", default="BOS WeChat Assistant")
    parser.add_argument("--app-id", default=None)
    parser.add_argument("--app-secret", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--base-url", default="https://YOUR_PUBLIC_BASE_URL")
    args = parser.parse_args()

    async with async_session_factory() as session:
        tenant_id = await _resolve_tenant_id(session, args.tenant_id)
        admin_user, generated_password = await _ensure_admin(
            session,
            tenant_id=tenant_id,
            username=args.admin_username,
            password=args.admin_password,
        )

        account = None
        if args.account_key and args.app_id and args.token:
            account = await _upsert_account(
                session,
                tenant_id=tenant_id,
                default_user_id=admin_user.id,
                account_key=args.account_key,
                name=args.account_name,
                app_id=args.app_id,
                app_secret=args.app_secret,
                token=args.token,
            )

        await session.commit()

    print(f"tenant_id={tenant_id}")
    print(f"admin_username={admin_user.username}")
    print(f"admin_user_id={admin_user.id}")
    if generated_password:
        print(f"admin_password={generated_password}")
    print(f"admin_bearer_token={create_access_token(admin_user.id, admin_user.role, admin_user.tenant_id)}")
    if account is not None:
        print(f"official_account_id={account.id}")
        print(f"callback_url={args.base_url.rstrip('/')}/api/v1/wechat/official-accounts/{account.account_key}/callback")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

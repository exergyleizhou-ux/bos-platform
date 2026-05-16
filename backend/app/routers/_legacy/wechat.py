"""WeChat official account router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_async_session
from app.deps import require_role
from app.models import User
from app.schemas import (
    WechatContactBindingResponse,
    WechatOfficialAccountCreate,
    WechatOfficialAccountResponse,
    WechatOfficialAccountUpdate,
)
from app.services.wechat import wechat_service

router = APIRouter(prefix="/wechat", tags=["WeChat"])
settings = get_settings()
logger = logging.getLogger("bos.wechat")


def _callback_path(account_key: str) -> str:
    return f"/api/v1/wechat/official-accounts/{account_key}/callback"


def _serialize_account(account) -> WechatOfficialAccountResponse:
    return WechatOfficialAccountResponse(
        id=account.id,
        tenant_id=account.tenant_id,
        default_user_id=account.default_user_id,
        name=account.name,
        account_key=account.account_key,
        app_id=account.app_id,
        token=account.token,
        encoding_aes_key=account.encoding_aes_key,
        welcome_message=account.welcome_message,
        is_active=account.is_active,
        callback_path=_callback_path(account.account_key),
        has_app_secret=bool(account.app_secret),
        access_token_expires_at=account.access_token_expires_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@router.get("/official-accounts", response_model=list[WechatOfficialAccountResponse])
async def list_official_accounts(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    accounts = await wechat_service.list_accounts(db, tenant_id=current_user.tenant_id)
    return [_serialize_account(account) for account in accounts]


@router.post(
    "/official-accounts",
    response_model=WechatOfficialAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_official_account(
    body: WechatOfficialAccountCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        account = await wechat_service.create_account(
            db,
            tenant_id=current_user.tenant_id,
            default_user_id=body.default_user_id,
            name=body.name,
            account_key=body.account_key,
            app_id=body.app_id,
            app_secret=body.app_secret,
            token=body.token,
            encoding_aes_key=body.encoding_aes_key,
            welcome_message=body.welcome_message,
            is_active=body.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_account(account)


@router.patch("/official-accounts/{account_id}", response_model=WechatOfficialAccountResponse)
async def update_official_account(
    account_id: int,
    body: WechatOfficialAccountUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        account = await wechat_service.update_account(
            db,
            tenant_id=current_user.tenant_id,
            account_id=account_id,
            updates=body.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_account(account)


@router.get("/official-accounts/{account_id}/contacts", response_model=list[WechatContactBindingResponse])
async def list_official_account_contacts(
    account_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    contacts = await wechat_service.list_contacts(
        db,
        tenant_id=current_user.tenant_id,
        official_account_id=account_id,
    )
    return [WechatContactBindingResponse.model_validate(item) for item in contacts]


@router.get("/official-accounts/{account_key}/callback")
async def verify_official_account_callback(
    account_key: str,
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(""),
    db: AsyncSession = Depends(get_async_session),
):
    if not settings.WECHAT_ENABLE_OFFICIAL_ACCOUNTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WeChat integration is disabled")

    account = await wechat_service.get_account_by_key(db, account_key=account_key)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Official account not found")
    if not wechat_service.verify_signature(
        token=account.token,
        signature=signature,
        timestamp=timestamp,
        nonce=nonce,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid WeChat signature")
    return PlainTextResponse(content=echostr or "")


@router.post("/official-accounts/{account_key}/callback")
async def receive_official_account_callback(
    account_key: str,
    request: Request,
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    db: AsyncSession = Depends(get_async_session),
):
    if not settings.WECHAT_ENABLE_OFFICIAL_ACCOUNTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WeChat integration is disabled")

    account = await wechat_service.get_account_by_key(db, account_key=account_key)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Official account not found")
    if not wechat_service.verify_signature(
        token=account.token,
        signature=signature,
        timestamp=timestamp,
        nonce=nonce,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid WeChat signature")

    raw_body = (await request.body()).decode("utf-8", errors="replace")
    try:
        payload = wechat_service.parse_xml_message(raw_body)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid WeChat XML payload") from exc

    if payload.get("Encrypt"):
        xml = wechat_service.build_text_reply(
            to_user=payload.get("FromUserName", ""),
            from_user=payload.get("ToUserName", ""),
            content="当前仅支持明文模式接入，请将公众号消息加解密方式改为明文模式后再试。",
        )
        return Response(content=xml, media_type="application/xml")

    try:
        reply_text, _deferred = await wechat_service.process_inbound_message_with_timeout(
            db,
            account=account,
            payload=payload,
        )
    except Exception as exc:
        logger.exception("WeChat callback processing failed", extra={"account_key": account_key, "payload": payload})
        await db.rollback()
        reply_text = settings.WECHAT_DEFAULT_ERROR_MESSAGE

    xml = wechat_service.build_text_reply(
        to_user=payload.get("FromUserName", ""),
        from_user=payload.get("ToUserName", ""),
        content=reply_text,
    )
    return Response(content=xml, media_type="application/xml")

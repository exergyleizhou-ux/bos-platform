import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CodeSession, CodeTask, WechatContactBinding, WechatOfficialAccount
from app.services.code.providers import OpenAICodexProvider
from app.services.wechat import wechat_service


def _signature(token: str, timestamp: str, nonce: str) -> str:
    return hashlib.sha1("".join(sorted([token, timestamp, nonce])).encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def _force_stub_provider_for_wechat_router():
    original_provider = wechat_service.session_service.provider
    wechat_service.session_service.provider = OpenAICodexProvider(enabled=False)
    try:
        yield
    finally:
        wechat_service.session_service.provider = original_provider


class TestWechatRouter:
    @pytest.mark.asyncio
    async def test_admin_can_create_and_list_official_accounts(
        self,
        client: AsyncClient,
        admin_user,
        admin_headers: dict[str, str],
    ):
        create_response = await client.post(
            "/api/v1/wechat/official-accounts",
            json={
                "name": "BOS WeChat Assistant",
                "account_key": "bos-wechat-admin",
                "app_id": "wx-test-app",
                "app_secret": "secret-value",
                "token": "wechat-token",
                "default_user_id": admin_user.id,
                "welcome_message": "Welcome to BOS",
                "is_active": True,
            },
            headers=admin_headers,
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["account_key"] == "bos-wechat-admin"
        assert created["callback_path"] == "/api/v1/wechat/official-accounts/bos-wechat-admin/callback"
        assert created["has_app_secret"] is True

        list_response = await client.get("/api/v1/wechat/official-accounts", headers=admin_headers)
        assert list_response.status_code == 200
        accounts = list_response.json()
        assert len(accounts) == 1
        assert accounts[0]["name"] == "BOS WeChat Assistant"

    @pytest.mark.asyncio
    async def test_callback_verification_and_text_message_flow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user,
        admin_headers: dict[str, str],
    ):
        create_response = await client.post(
            "/api/v1/wechat/official-accounts",
            json={
                "name": "BOS WeChat Assistant",
                "account_key": "bos-wechat-callback",
                "app_id": "wx-test-app",
                "token": "wechat-token",
                "default_user_id": scientist_user.id,
                "is_active": True,
            },
            headers=admin_headers,
        )
        assert create_response.status_code == 201
        account_id = create_response.json()["id"]

        timestamp = "1713348000"
        nonce = "nonce-123"
        signature = _signature("wechat-token", timestamp, nonce)

        verify_response = await client.get(
            "/api/v1/wechat/official-accounts/bos-wechat-callback/callback",
            params={
                "signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
                "echostr": "hello-wechat",
            },
        )
        assert verify_response.status_code == 200
        assert verify_response.text == "hello-wechat"

        xml_payload = """
<xml>
  <ToUserName><![CDATA[gh_test_account]]></ToUserName>
  <FromUserName><![CDATA[user_openid_1]]></FromUserName>
  <CreateTime>1713348000</CreateTime>
  <MsgType><![CDATA[text]]></MsgType>
  <Content><![CDATA[hello bos]]></Content>
  <MsgId>1234567890</MsgId>
</xml>
""".strip()

        message_response = await client.post(
            "/api/v1/wechat/official-accounts/bos-wechat-callback/callback",
            params={
                "signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
            },
            content=xml_payload,
            headers={"Content-Type": "application/xml"},
        )
        assert message_response.status_code == 200
        assert "<MsgType><![CDATA[text]]></MsgType>" in message_response.text
        assert "BOS Code provider boundary is active" in message_response.text
        assert "user_openid_1" in message_response.text

        binding_result = await db_session.execute(
            select(WechatContactBinding).where(WechatContactBinding.openid == "user_openid_1")
        )
        binding = binding_result.scalar_one_or_none()
        assert binding is not None
        assert binding.official_account_id == account_id
        assert binding.default_session_id is not None

        session_result = await db_session.execute(
            select(CodeSession).where(CodeSession.id == binding.default_session_id)
        )
        session = session_result.scalar_one_or_none()
        assert session is not None
        assert session.user_id == scientist_user.id

        contacts_response = await client.get(
            f"/api/v1/wechat/official-accounts/{account_id}/contacts",
            headers=admin_headers,
        )
        assert contacts_response.status_code == 200
        contacts = contacts_response.json()
        assert len(contacts) == 1
        assert contacts[0]["openid"] == "user_openid_1"

        account_result = await db_session.execute(
            select(WechatOfficialAccount).where(WechatOfficialAccount.id == account_id)
        )
        account = account_result.scalar_one_or_none()
        assert account is not None
        assert account.default_user_id == scientist_user.id

    @pytest.mark.asyncio
    async def test_callback_task_command_creates_code_task(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user,
        admin_headers: dict[str, str],
    ):
        create_response = await client.post(
            "/api/v1/wechat/official-accounts",
            json={
                "name": "BOS WeChat Assistant",
                "account_key": "bos-wechat-task",
                "app_id": "wx-test-app",
                "token": "wechat-token",
                "default_user_id": scientist_user.id,
                "is_active": True,
            },
            headers=admin_headers,
        )
        assert create_response.status_code == 201

        timestamp = "1713348000"
        nonce = "nonce-task"
        signature = _signature("wechat-token", timestamp, nonce)
        xml_payload = """
<xml>
  <ToUserName><![CDATA[gh_test_account]]></ToUserName>
  <FromUserName><![CDATA[user_openid_task]]></FromUserName>
  <CreateTime>1713348000</CreateTime>
  <MsgType><![CDATA[text]]></MsgType>
  <Content><![CDATA[发任务 微信助手接入 | 完成微信入口与网页版线程联动 | bos/private-assistant]]></Content>
  <MsgId>1234567891</MsgId>
</xml>
""".strip()

        message_response = await client.post(
            "/api/v1/wechat/official-accounts/bos-wechat-task/callback",
            params={
                "signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
            },
            content=xml_payload,
            headers={"Content-Type": "application/xml"},
        )
        assert message_response.status_code == 200
        assert "任务已创建" in message_response.text

        task_result = await db_session.execute(
            select(CodeTask).where(CodeTask.title == "微信助手接入").order_by(CodeTask.id.desc())
        )
        task = task_result.scalar_one_or_none()
        assert task is not None
        assert task.objective == "完成微信入口与网页版线程联动"
        assert task.scope == "bos/private-assistant"

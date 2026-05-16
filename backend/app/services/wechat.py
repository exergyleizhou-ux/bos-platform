"""WeChat official account channel adapter."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_factory
from app.models import CodeSession, User, WechatContactBinding, WechatOfficialAccount
from app.services.code.task_service import CodeTaskService
from app.services.code.workspace_service import CodeWorkspaceService
from app.services.code.session_service import CodeSessionService

settings = get_settings()

_CUSTOM_MESSAGE_ENDPOINT = "https://api.weixin.qq.com/cgi-bin/message/custom/send"
_TOKEN_ENDPOINT = "https://api.weixin.qq.com/cgi-bin/token"


class WechatService:
    def __init__(self) -> None:
        self.session_service = CodeSessionService()

    @staticmethod
    def verify_signature(*, token: str, signature: str | None, timestamp: str | None, nonce: str | None) -> bool:
        if not signature or not timestamp or not nonce:
            return False
        joined = "".join(sorted([token, timestamp, nonce]))
        expected = hashlib.sha1(joined.encode("utf-8")).hexdigest()
        return expected == signature

    @staticmethod
    def parse_xml_message(raw_body: str) -> dict[str, str]:
        root = ET.fromstring(raw_body)
        payload: dict[str, str] = {}
        for child in root:
            payload[child.tag] = child.text or ""
        return payload

    @staticmethod
    def build_text_reply(*, to_user: str, from_user: str, content: str) -> str:
        timestamp = int(datetime.now(UTC).timestamp())
        safe_content = (content or settings.WECHAT_DEFAULT_EMPTY_MESSAGE).strip().replace("]]>", "]] ]>")
        return (
            "<xml>"
            f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
            f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
            f"<CreateTime>{timestamp}</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{safe_content}]]></Content>"
            "</xml>"
        )

    @staticmethod
    def normalize_reply_text(text: str) -> str:
        cleaned = (text or settings.WECHAT_DEFAULT_ERROR_MESSAGE).strip()
        if len(cleaned) <= 1200:
            return cleaned
        return f"{cleaned[:1180].rstrip()}\n\n[回复已截断，请继续追问查看剩余内容]"

    @staticmethod
    def _effective_prompt_prelude() -> str:
        return settings.WECHAT_DEFAULT_PROMPT_PREFIX.strip()

    @staticmethod
    def _normalize_command(text: str) -> str:
        return " ".join((text or "").strip().split())

    @staticmethod
    def _web_base_url() -> str | None:
        base = settings.WECHAT_WEB_BASE_URL.strip()
        if not base:
            return None
        return base.rstrip("/")

    def _session_web_link(self, session_id: int) -> str | None:
        base = self._web_base_url()
        if not base:
            return None
        return f"{base}/bos?sessionId={session_id}"

    def _route_link(self, path: str) -> str | None:
        base = self._web_base_url()
        if not base:
            return None
        return f"{base}{path}"

    async def _handle_command(
        self,
        db: AsyncSession,
        *,
        account: WechatOfficialAccount,
        binding: WechatContactBinding,
        text: str,
    ) -> str | None:
        normalized = self._normalize_command(text)
        if not normalized:
            return None

        lowered = normalized.lower()
        user = await self._get_tenant_user_or_raise(db, tenant_id=account.tenant_id, user_id=binding.user_id)
        workspace = None

        if lowered in {"/help", "帮助", "命令", "能做什么控制"}:
            session_link = self._session_web_link(binding.default_session_id) if binding.default_session_id else None
            lines = [
                "我现在可以作为你的微信私人助理来做这些事：",
                "",
                "1. 直接聊天：普通问题、总结、润色、分析、方案",
                "2. 发任务：`发任务 标题 | 目标 | 范围`",
                "3. 看任务：`任务列表`",
                "4. 请求评审：`请求评审 任务ID`",
                "5. 路由任务：`路由任务 任务ID executor`",
                "6. 打开网页助手：`打开网页`",
                "7. 打开编排台：`打开编排台`",
            ]
            if session_link:
                lines.extend(["", f"当前线程网页版：{session_link}"])
            return "\n".join(lines)

        if lowered in {"/web", "打开网页", "网页版", "打开助手"}:
            base = self._web_base_url()
            if not base:
                return "网页版地址还没配置好，等我把固定网页地址接上后你就可以直接从微信跳过去。"
            if binding.default_session_id is None:
                return f"打开网页版 BOS Assistant：\n{base}/bos"
            session_link = self._session_web_link(binding.default_session_id)
            if not session_link:
                return f"打开网页版 BOS Assistant：\n{base}/bos"
            return f"打开网页版 BOS Assistant：\n{session_link}"

        if lowered in {"/orchestrator", "打开编排台", "打开控制台"}:
            orchestrator = self._route_link("/bos/orchestrator")
            console = self._route_link("/bos/console")
            if not orchestrator or not console:
                return "网页版地址还没配置好，暂时没法从微信直接跳转。"
            return f"编排台：\n{orchestrator}\n\n控制台：\n{console}"

        if normalized.startswith("发任务 ") or lowered.startswith("/task "):
            command_body = normalized[4:] if normalized.startswith("发任务 ") else normalized[6:]
            parts = [part.strip() for part in command_body.split("|")]
            if len(parts) < 2:
                return "发任务格式：发任务 标题 | 目标 | 范围"
            title, objective = parts[0], parts[1]
            scope = parts[2] if len(parts) >= 3 and parts[2] else "wechat/private-assistant"
            workspace = await CodeWorkspaceService.get_workspace(db, tenant_id=account.tenant_id)
            if workspace is None:
                workspace = await CodeWorkspaceService.ensure_workspace(db, user=user)
            task = await CodeTaskService.create_task(
                db,
                workspace=workspace,
                user=user,
                session_id=binding.default_session_id,
                title=title,
                objective=objective,
                scope=scope,
                acceptance_criteria=[],
                task_packet={"source": "wechat_private_assistant"},
            )
            await db.commit()
            thread_link = self._session_web_link(binding.default_session_id) if binding.default_session_id else None
            message = [f"任务已创建：#{task.id} {task.title}", f"状态：{task.task_status}", f"范围：{scope}"]
            if thread_link:
                message.extend(["", f"在线程里继续：{thread_link}"])
            return "\n".join(message)

        if lowered in {"任务列表", "/tasks"}:
            workspace = await CodeWorkspaceService.get_workspace(db, tenant_id=account.tenant_id)
            if workspace is None:
                workspace = await CodeWorkspaceService.ensure_workspace(db, user=user)
            tasks = await CodeTaskService.list_tasks(db, workspace_id=workspace.id)
            if not tasks:
                return "当前还没有任务。你可以这样发：发任务 标题 | 目标 | 范围"
            top = tasks[:5]
            lines = ["最近任务：", ""]
            for task in top:
                lines.append(f"#{task.id} [{task.task_status}] {task.title}")
            return "\n".join(lines)

        if normalized.startswith("请求评审 ") or lowered.startswith("/review "):
            raw = normalized[5:] if normalized.startswith("请求评审 ") else normalized[8:]
            try:
                task_id = int(raw.strip())
            except ValueError:
                return "请求评审格式：请求评审 任务ID"
            workspace = await CodeWorkspaceService.get_workspace(db, tenant_id=account.tenant_id)
            if workspace is None:
                workspace = await CodeWorkspaceService.ensure_workspace(db, user=user)
            task, _executor, _reviewer = await CodeTaskService.request_review(
                db,
                workspace_id=workspace.id,
                task_id=task_id,
                summary="Requested from WeChat private assistant",
                payload={"source": "wechat_private_assistant"},
            )
            await db.commit()
            return f"任务 #{task.id} 已送审，当前状态：{task.task_status}"

        if normalized.startswith("路由任务 ") or lowered.startswith("/route "):
            raw = normalized[5:] if normalized.startswith("路由任务 ") else normalized[7:]
            parts = raw.split()
            if len(parts) < 2:
                return "路由任务格式：路由任务 任务ID executor"
            try:
                task_id = int(parts[0])
            except ValueError:
                return "路由任务格式：路由任务 任务ID executor"
            route_to = parts[1].strip().lower()
            if route_to not in {"executor", "reviewer", "architect"}:
                return "route_to 仅支持 architect / executor / reviewer"
            workspace = await CodeWorkspaceService.get_workspace(db, tenant_id=account.tenant_id)
            if workspace is None:
                workspace = await CodeWorkspaceService.ensure_workspace(db, user=user)
            task, _architect, _target = await CodeTaskService.architect_route_task(
                db,
                workspace_id=workspace.id,
                task_id=task_id,
                summary=f"Routed from WeChat to {route_to}",
                route_to=route_to,
                payload={"source": "wechat_private_assistant"},
            )
            await db.commit()
            return f"任务 #{task.id} 已路由到 {route_to}，当前状态：{task.task_status}"

        return None

    async def get_account_by_key(
        self,
        db: AsyncSession,
        *,
        account_key: str,
        active_only: bool = True,
    ) -> WechatOfficialAccount | None:
        stmt = select(WechatOfficialAccount).where(WechatOfficialAccount.account_key == account_key)
        if active_only:
            stmt = stmt.where(WechatOfficialAccount.is_active.is_(True))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_accounts(self, db: AsyncSession, *, tenant_id: int) -> list[WechatOfficialAccount]:
        result = await db.execute(
            select(WechatOfficialAccount)
            .where(WechatOfficialAccount.tenant_id == tenant_id)
            .order_by(WechatOfficialAccount.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_contacts(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        official_account_id: int,
    ) -> list[WechatContactBinding]:
        result = await db.execute(
            select(WechatContactBinding)
            .where(
                WechatContactBinding.tenant_id == tenant_id,
                WechatContactBinding.official_account_id == official_account_id,
            )
            .order_by(WechatContactBinding.last_message_at.desc(), WechatContactBinding.id.desc())
        )
        return list(result.scalars().all())

    async def create_account(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        default_user_id: int,
        name: str,
        account_key: str,
        app_id: str,
        app_secret: str | None,
        token: str,
        encoding_aes_key: str | None,
        welcome_message: str | None,
        is_active: bool,
    ) -> WechatOfficialAccount:
        user = await self._get_tenant_user_or_raise(db, tenant_id=tenant_id, user_id=default_user_id)
        if user.role not in {"operator", "scientist", "admin"}:
            raise ValueError("default_user_id must belong to an operator, scientist, or admin user")

        existing = await self.get_account_by_key(db, account_key=account_key, active_only=False)
        if existing is not None:
            raise ValueError("account_key already exists")

        account = WechatOfficialAccount(
            tenant_id=tenant_id,
            default_user_id=default_user_id,
            name=name,
            account_key=account_key,
            app_id=app_id,
            app_secret=app_secret,
            token=token,
            encoding_aes_key=encoding_aes_key,
            welcome_message=welcome_message,
            is_active=is_active,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    async def update_account(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        account_id: int,
        updates: dict[str, Any],
    ) -> WechatOfficialAccount:
        result = await db.execute(
            select(WechatOfficialAccount).where(
                WechatOfficialAccount.id == account_id,
                WechatOfficialAccount.tenant_id == tenant_id,
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise LookupError("Official account not found")

        if "default_user_id" in updates and updates["default_user_id"] is not None:
            user = await self._get_tenant_user_or_raise(db, tenant_id=tenant_id, user_id=int(updates["default_user_id"]))
            if user.role not in {"operator", "scientist", "admin"}:
                raise ValueError("default_user_id must belong to an operator, scientist, or admin user")

        for field, value in updates.items():
            setattr(account, field, value)

        await db.commit()
        await db.refresh(account)
        return account

    async def process_inbound_message(
        self,
        db: AsyncSession,
        *,
        account: WechatOfficialAccount,
        payload: dict[str, str],
    ) -> str:
        msg_type = (payload.get("MsgType") or "").strip().lower()
        from_user = (payload.get("FromUserName") or "").strip()
        if not from_user:
            return settings.WECHAT_DEFAULT_ERROR_MESSAGE

        if msg_type == "event":
            event = (payload.get("Event") or "").strip().lower()
            if event == "subscribe":
                return account.welcome_message or settings.WECHAT_DEFAULT_WELCOME_MESSAGE
            return "事件已收到。"

        if msg_type != "text":
            return settings.WECHAT_DEFAULT_UNSUPPORTED_MESSAGE

        text = (payload.get("Content") or "").strip()
        if not text:
            return settings.WECHAT_DEFAULT_EMPTY_MESSAGE

        binding = await self._get_or_create_contact_binding(db, account=account, openid=from_user)
        command_reply = await self._handle_command(db, account=account, binding=binding, text=text)
        if command_reply is not None:
            binding.last_inbound_message = text
            binding.last_outbound_message = command_reply
            binding.last_message_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(binding)
            return self.normalize_reply_text(command_reply)
        session = await self._get_or_create_contact_session(db, account=account, binding=binding)
        turn, reply_text = await self.session_service.create_turn(
            db,
            session=session,
            user_message=text,
            prompt_prelude=self._effective_prompt_prelude(),
        )
        binding.default_session_id = session.id
        binding.last_inbound_message = text
        binding.last_outbound_message = reply_text
        binding.last_message_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(binding)
        if turn.assistant_summary:
            return self.normalize_reply_text(turn.assistant_summary)
        return self.normalize_reply_text(reply_text)

    async def process_inbound_message_with_timeout(
        self,
        db: AsyncSession,
        *,
        account: WechatOfficialAccount,
        payload: dict[str, str],
    ) -> tuple[str, bool]:
        try:
            reply = await asyncio.wait_for(
                self.process_inbound_message(db, account=account, payload=payload),
                timeout=max(1, settings.WECHAT_REPLY_TIMEOUT_SECONDS),
            )
            return reply, False
        except TimeoutError:
            await self._schedule_async_followup(account_id=account.id, payload=payload)
            return "消息已收到，正在处理中，稍后会继续回复你。", True

    async def _schedule_async_followup(self, *, account_id: int, payload: dict[str, str]) -> None:
        async def _runner() -> None:
            async with async_session_factory() as db:
                account = await db.get(WechatOfficialAccount, account_id)
                if account is None or not account.is_active:
                    return
                try:
                    reply = await self.process_inbound_message(db, account=account, payload=payload)
                except Exception:
                    await db.rollback()
                    reply = settings.WECHAT_DEFAULT_ERROR_MESSAGE
                openid = (payload.get("FromUserName") or "").strip()
                if openid:
                    await self.send_custom_text_message(db, account=account, openid=openid, content=reply)

        asyncio.create_task(_runner())

    async def send_custom_text_message(
        self,
        db: AsyncSession,
        *,
        account: WechatOfficialAccount,
        openid: str,
        content: str,
    ) -> None:
        if not account.app_secret:
            return
        access_token = await self._get_access_token(db, account=account)
        payload = {
            "touser": openid,
            "msgtype": "text",
            "text": {"content": self.normalize_reply_text(content)},
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{_CUSTOM_MESSAGE_ENDPOINT}?access_token={access_token}",
                json=payload,
            )
            response.raise_for_status()

    async def _get_access_token(self, db: AsyncSession, *, account: WechatOfficialAccount) -> str:
        now = datetime.now(UTC)
        if account.last_access_token and account.access_token_expires_at and account.access_token_expires_at > now:
            return account.last_access_token
        if not account.app_secret:
            raise RuntimeError("WeChat app_secret is required for custom message delivery")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                _TOKEN_ENDPOINT,
                params={
                    "grant_type": "client_credential",
                    "appid": account.app_id,
                    "secret": account.app_secret,
                },
            )
            response.raise_for_status()
            body = response.json()

        access_token = body.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise RuntimeError(f"Failed to obtain WeChat access token: {body}")

        expires_in = int(body.get("expires_in") or 7200)
        account.last_access_token = access_token
        account.access_token_expires_at = now + timedelta(seconds=max(60, expires_in - 120))
        await db.commit()
        await db.refresh(account)
        return access_token

    async def _get_or_create_contact_binding(
        self,
        db: AsyncSession,
        *,
        account: WechatOfficialAccount,
        openid: str,
    ) -> WechatContactBinding:
        result = await db.execute(
            select(WechatContactBinding).where(
                WechatContactBinding.official_account_id == account.id,
                WechatContactBinding.openid == openid,
            )
        )
        binding = result.scalar_one_or_none()
        if binding is not None:
            return binding

        binding = WechatContactBinding(
            official_account_id=account.id,
            tenant_id=account.tenant_id,
            user_id=account.default_user_id,
            openid=openid,
            last_message_at=datetime.now(UTC),
        )
        db.add(binding)
        await db.flush()
        return binding

    async def _get_or_create_contact_session(
        self,
        db: AsyncSession,
        *,
        account: WechatOfficialAccount,
        binding: WechatContactBinding,
    ) -> CodeSession:
        if binding.default_session_id is not None:
            result = await db.execute(
                select(CodeSession).where(
                    CodeSession.id == binding.default_session_id,
                    CodeSession.tenant_id == account.tenant_id,
                )
            )
            session = result.scalar_one_or_none()
            if session is not None and session.session_status not in {"cancelled", "failed"}:
                return session

        user = await self._get_tenant_user_or_raise(db, tenant_id=account.tenant_id, user_id=binding.user_id)
        session = await self.session_service.create_session(db, user=user, acquire_write_lease=False)
        await db.flush()
        binding.default_session_id = session.id
        return session

    @staticmethod
    async def _get_tenant_user_or_raise(db: AsyncSession, *, tenant_id: int, user_id: int) -> User:
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise LookupError("Default WeChat user not found in tenant")
        return user


wechat_service = WechatService()

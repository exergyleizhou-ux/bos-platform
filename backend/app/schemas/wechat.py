"""WeChat official account integration schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WechatOfficialAccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    account_key: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    app_id: str = Field(..., min_length=1, max_length=128)
    app_secret: str | None = Field(default=None, max_length=255)
    token: str = Field(..., min_length=3, max_length=255)
    encoding_aes_key: str | None = Field(default=None, max_length=255)
    default_user_id: int = Field(..., gt=0)
    welcome_message: str | None = Field(default=None, max_length=4000)
    is_active: bool = True


class WechatOfficialAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    app_id: str | None = Field(default=None, min_length=1, max_length=128)
    app_secret: str | None = Field(default=None, max_length=255)
    token: str | None = Field(default=None, min_length=3, max_length=255)
    encoding_aes_key: str | None = Field(default=None, max_length=255)
    default_user_id: int | None = Field(default=None, gt=0)
    welcome_message: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class WechatOfficialAccountResponse(BaseModel):
    id: int
    tenant_id: int
    default_user_id: int
    name: str
    account_key: str
    app_id: str
    token: str
    encoding_aes_key: str | None = None
    welcome_message: str | None = None
    is_active: bool
    callback_path: str
    has_app_secret: bool
    access_token_expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class WechatContactBindingResponse(BaseModel):
    id: int
    official_account_id: int
    tenant_id: int
    user_id: int
    openid: str
    unionid: str | None = None
    default_session_id: int | None = None
    last_inbound_message: str | None = None
    last_outbound_message: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

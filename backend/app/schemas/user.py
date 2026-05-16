"""
BOS Pipeline v9.0 -User Schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


ROLE_PATTERN = (
    r"^(admin|scientist|operator|viewer|billing|final_release_approver|model_governance_approver|"
    r"external_release_share_approver|external_release_delivery_approver|external_runtime_activation_approver)"
    r"([\s,;|]+(admin|scientist|operator|viewer|billing|final_release_approver|model_governance_approver|"
    r"external_release_share_approver|external_release_delivery_approver|external_runtime_activation_approver))*$"
)

FINAL_ACTION_GRANT_ROLES = {
    "final_release_approver",
    "model_governance_approver",
    "external_release_share_approver",
    "external_release_delivery_approver",
}

GOVERNANCE_GRANT_ROLES = {
    *FINAL_ACTION_GRANT_ROLES,
    "external_runtime_activation_approver",
}

BASE_ROLE_GRANT_ROLES = {"viewer", "billing", "operator", "scientist", "admin"}
DB_BACKED_ROLE_ASSIGNMENT_SCOPE = "tenant"
ROLE_GRANT_POLICY_VERSION = "tenant_governance_grants_v1"

GOVERNANCE_GRANT_ROLE_CATALOG = {
    "final_release_approver": {
        "label": "Final release approver",
        "category": "final_action",
        "description": "Can execute approved final release approval requests.",
    },
    "model_governance_approver": {
        "label": "Model governance approver",
        "category": "final_action",
        "description": "Can execute approved model activation requests.",
    },
    "external_release_share_approver": {
        "label": "External share approver",
        "category": "final_action",
        "description": "Can prepare approved external release share records.",
    },
    "external_release_delivery_approver": {
        "label": "External delivery approver",
        "category": "final_action",
        "description": "Can deliver approved external release shares to allowlisted endpoints.",
    },
    "external_runtime_activation_approver": {
        "label": "Runtime activation approver",
        "category": "runtime_activation",
        "description": "Can approve and execute external knowledge runtime activation and rollback.",
    },
}


class UserCreate(BaseModel):
    """Create user request."""

    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    role: str = Field(default="operator", pattern=ROLE_PATTERN)


class UserUpdate(BaseModel):
    """Update user request (partial)."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[str] = Field(None, pattern=ROLE_PATTERN)
    is_active: Optional[bool] = None
    preferences: Optional[Dict[str, Any]] = None


class UserSelfUpdate(BaseModel):
    """Current user profile update request."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    preferences: Optional[Dict[str, Any]] = None


class UserPasswordResetRequest(BaseModel):
    """Admin password reset request."""

    new_password: str = Field(..., min_length=8, max_length=128)


class UserRoleGrantUpdateRequest(BaseModel):
    """Replace a user's active elevated governance role grants."""

    roles: List[str] = Field(default_factory=list, max_length=len(GOVERNANCE_GRANT_ROLES))
    reason: Optional[str] = Field(None, max_length=500)


class UserRoleGrantResponse(BaseModel):
    """Single DB-backed role grant."""

    id: int
    user_id: int
    tenant_id: int
    role: str
    is_active: bool
    granted_by_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserRoleGrantPolicyRoleResponse(BaseModel):
    """A DB-backed role that the grant endpoint can manage."""

    role: str
    label: str
    category: str
    assignment_scope: str
    grant_endpoint_allowed: bool
    final_action_role: bool
    description: str


class UserRoleGrantPolicyResponse(BaseModel):
    """Tenant-scoped role-grant policy for the admin grant endpoint."""

    policy_version: str
    assignment_scope: str
    grant_endpoint: str
    audit_history_endpoint: str
    tenant_scoped: bool
    legacy_role_fallback: bool
    admin_grant_allowed: bool
    self_grant_allowed: bool
    grant_audit_table: str
    final_action_audit_table: str
    supported_roles: List[str]
    forbidden_roles: List[str]
    roles: List[UserRoleGrantPolicyRoleResponse]


class UserRoleGrantSummaryResponse(BaseModel):
    """User role state with legacy fallback and DB-backed grants."""

    user_id: int
    tenant_id: int
    assignment_scope: str
    grant_policy_version: str
    base_role: str
    legacy_roles: List[str]
    db_grants: List[UserRoleGrantResponse]
    resolved_roles: List[str]
    manageable_governance_grants: List[str]
    supported_governance_grants: List[str]
    manageable_final_action_grants: List[str]
    supported_final_action_grants: List[str]


class UserRoleGrantAuditRecordResponse(BaseModel):
    """Single immutable role-grant audit event."""

    id: int
    tenant_id: int
    user_id: int
    role_grant_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    actor_username: Optional[str] = None
    actor_full_name: Optional[str] = None
    role: str
    action: str
    previous_is_active: Optional[bool] = None
    new_is_active: Optional[bool] = None
    previous_reason: Optional[str] = None
    new_reason: Optional[str] = None
    previous_granted_by_user_id: Optional[int] = None
    new_granted_by_user_id: Optional[int] = None
    created_at: Optional[datetime] = None


class UserRoleGrantAuditRecordListResponse(BaseModel):
    """Tenant-scoped role-grant audit history for one user."""

    user_id: int
    tenant_id: int
    assignment_scope: str
    grant_policy_version: str
    count: int
    audit_records: List[UserRoleGrantAuditRecordResponse]


class UserResponse(BaseModel):
    """User list/create response."""

    id: int
    username: str
    full_name: str
    email: str
    role: str
    is_active: bool
    tenant_id: int
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserProfileResponse(UserResponse):
    """Detailed user profile response."""

    preferences: Optional[Dict[str, Any]] = None
    password_changed_at: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None

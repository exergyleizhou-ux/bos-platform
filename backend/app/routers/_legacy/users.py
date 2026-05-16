"""
BOS Pipeline v9.0 — Users Router

CRUD operations for user management within a tenant.
Only admins can create/update/deactivate users.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_async_session
from app.deps import PaginationParams, get_current_user, get_pagination, parse_user_roles, require_role, resolve_user_roles, set_tenant_context
from app.models import Tenant, User, UserRoleGrant, UserRoleGrantAuditRecord
from app.schemas import (
    MessageResponse,
    PaginatedResponse,
    UserCreate,
    UserPasswordResetRequest,
    UserProfileResponse,
    UserRoleGrantAuditRecordListResponse,
    UserRoleGrantAuditRecordResponse,
    UserRoleGrantPolicyResponse,
    UserRoleGrantPolicyRoleResponse,
    UserRoleGrantResponse,
    UserRoleGrantSummaryResponse,
    UserRoleGrantUpdateRequest,
    UserResponse,
    UserSelfUpdate,
    UserUpdate,
)
from app.schemas.user import (
    BASE_ROLE_GRANT_ROLES,
    DB_BACKED_ROLE_ASSIGNMENT_SCOPE,
    FINAL_ACTION_GRANT_ROLES,
    GOVERNANCE_GRANT_ROLE_CATALOG,
    GOVERNANCE_GRANT_ROLES,
    ROLE_GRANT_POLICY_VERSION,
    ROLE_PATTERN,
)
from app.security.passwords import pwd_context

router = APIRouter()
settings = get_settings()


async def _get_tenant_user_or_404(db: AsyncSession, *, user_id: int, tenant_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def _build_user_role_grant_summary(
    db: AsyncSession,
    *,
    user: User,
) -> UserRoleGrantSummaryResponse:
    result = await db.execute(
        select(UserRoleGrant)
        .where(
            UserRoleGrant.user_id == user.id,
            UserRoleGrant.tenant_id == user.tenant_id,
            UserRoleGrant.role.in_(GOVERNANCE_GRANT_ROLES),
            UserRoleGrant.is_active.is_(True),
        )
        .order_by(UserRoleGrant.role.asc(), UserRoleGrant.id.asc())
    )
    active_grants = list(result.scalars().all())
    resolved_roles = await resolve_user_roles(db, user)
    return UserRoleGrantSummaryResponse(
        user_id=user.id,
        tenant_id=user.tenant_id,
        assignment_scope=DB_BACKED_ROLE_ASSIGNMENT_SCOPE,
        grant_policy_version=ROLE_GRANT_POLICY_VERSION,
        base_role=user.role,
        legacy_roles=sorted(parse_user_roles(user.role)),
        db_grants=[UserRoleGrantResponse.model_validate(grant) for grant in active_grants],
        resolved_roles=sorted(resolved_roles),
        manageable_governance_grants=sorted(
            role for role in resolved_roles if role in GOVERNANCE_GRANT_ROLES
        ),
        supported_governance_grants=sorted(GOVERNANCE_GRANT_ROLES),
        manageable_final_action_grants=sorted(
            role for role in resolved_roles if role in FINAL_ACTION_GRANT_ROLES
        ),
        supported_final_action_grants=sorted(FINAL_ACTION_GRANT_ROLES),
    )


def _build_role_grant_policy() -> UserRoleGrantPolicyResponse:
    return UserRoleGrantPolicyResponse(
        policy_version=ROLE_GRANT_POLICY_VERSION,
        assignment_scope=DB_BACKED_ROLE_ASSIGNMENT_SCOPE,
        grant_endpoint="/api/v1/users/{user_id}/role-grants",
        audit_history_endpoint="/api/v1/users/{user_id}/role-grants/audit-records",
        tenant_scoped=True,
        legacy_role_fallback=True,
        admin_grant_allowed=False,
        self_grant_allowed=False,
        grant_audit_table="user_role_grant_audit_records",
        final_action_audit_table="final_action_audit_records",
        supported_roles=sorted(GOVERNANCE_GRANT_ROLES),
        forbidden_roles=sorted(BASE_ROLE_GRANT_ROLES),
        roles=[
            UserRoleGrantPolicyRoleResponse(
                role=role,
                label=metadata["label"],
                category=metadata["category"],
                assignment_scope=DB_BACKED_ROLE_ASSIGNMENT_SCOPE,
                grant_endpoint_allowed=True,
                final_action_role=role in FINAL_ACTION_GRANT_ROLES,
                description=metadata["description"],
            )
            for role, metadata in sorted(GOVERNANCE_GRANT_ROLE_CATALOG.items())
        ],
    )


def _serialize_role_grant_audit_record(
    record: UserRoleGrantAuditRecord,
    *,
    actors_by_id: dict[int, User],
) -> UserRoleGrantAuditRecordResponse:
    actor = actors_by_id.get(record.actor_user_id) if record.actor_user_id is not None else None
    return UserRoleGrantAuditRecordResponse(
        id=record.id,
        tenant_id=record.tenant_id,
        user_id=record.user_id,
        role_grant_id=record.role_grant_id,
        actor_user_id=record.actor_user_id,
        actor_username=actor.username if actor else None,
        actor_full_name=actor.full_name if actor else None,
        role=record.role,
        action=record.action,
        previous_is_active=record.previous_is_active,
        new_is_active=record.new_is_active,
        previous_reason=record.previous_reason,
        new_reason=record.new_reason,
        previous_granted_by_user_id=record.previous_granted_by_user_id,
        new_granted_by_user_id=record.new_granted_by_user_id,
        created_at=record.created_at,
    )


def _add_role_grant_audit(
    db: AsyncSession,
    *,
    grant: UserRoleGrant,
    actor_user_id: int,
    action: str,
    previous_is_active: bool | None,
    new_is_active: bool | None,
    previous_reason: str | None,
    new_reason: str | None,
    previous_granted_by_user_id: int | None,
    new_granted_by_user_id: int | None,
) -> None:
    db.add(
        UserRoleGrantAuditRecord(
            tenant_id=grant.tenant_id,
            user_id=grant.user_id,
            role_grant_id=grant.id,
            actor_user_id=actor_user_id,
            role=grant.role,
            action=action,
            previous_is_active=previous_is_active,
            new_is_active=new_is_active,
            previous_reason=previous_reason,
            new_reason=new_reason,
            previous_granted_by_user_id=previous_granted_by_user_id,
            new_granted_by_user_id=new_granted_by_user_id,
        )
    )


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    pagination: PaginationParams = Depends(get_pagination),
    role: str | None = Query(None, pattern=ROLE_PATTERN),
    is_active: bool | None = None,
    search: str | None = Query(None, max_length=100),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """List users in the current tenant (with filtering and pagination)."""
    query = select(User).where(User.tenant_id == current_user.tenant_id)

    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (User.username.ilike(search_filter))
            | (User.full_name.ilike(search_filter))
            | (User.email.ilike(search_filter))
        )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch
    query = query.order_by(User.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    users = result.scalars().all()

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_current_profile(
    current_user: User = Depends(get_current_user),
):
    """Get the current authenticated user's profile."""
    return UserProfileResponse.model_validate(current_user)


@router.patch("/me", response_model=UserProfileResponse)
async def update_current_profile(
    body: UserSelfUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update the current authenticated user's own profile."""
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    await db.commit()
    await db.refresh(current_user)
    return UserProfileResponse.model_validate(current_user)


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific user by ID (same tenant only)."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserProfileResponse.model_validate(user)


@router.get("/{user_id}/role-grants", response_model=UserRoleGrantSummaryResponse)
async def get_user_role_grants(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a user's elevated governance role grants and resolved role state."""
    user = await _get_tenant_user_or_404(db, user_id=user_id, tenant_id=current_user.tenant_id)
    return await _build_user_role_grant_summary(db, user=user)


@router.get("/{user_id}/role-grants/audit-records", response_model=UserRoleGrantAuditRecordListResponse)
async def list_user_role_grant_audit_records(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=10, ge=1, le=100),
    action: str | None = Query(default=None, pattern=r"^(grant|revoke|reactivate|update)$"),
    role: str | None = Query(default=None, pattern=ROLE_PATTERN),
):
    """List immutable tenant-scoped role-grant audit events for one user."""
    user = await _get_tenant_user_or_404(db, user_id=user_id, tenant_id=current_user.tenant_id)
    if role is not None and role not in GOVERNANCE_GRANT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported role grant audit filter: {role}",
        )

    query = select(UserRoleGrantAuditRecord).where(
        UserRoleGrantAuditRecord.user_id == user.id,
        UserRoleGrantAuditRecord.tenant_id == current_user.tenant_id,
    )
    if action is not None:
        query = query.where(UserRoleGrantAuditRecord.action == action)
    if role is not None:
        query = query.where(UserRoleGrantAuditRecord.role == role)

    result = await db.execute(query.order_by(UserRoleGrantAuditRecord.created_at.desc(), UserRoleGrantAuditRecord.id.desc()).limit(limit))
    audit_records = list(result.scalars().all())
    actor_ids = sorted(
        {record.actor_user_id for record in audit_records if record.actor_user_id is not None}
    )
    actors_by_id: dict[int, User] = {}
    if actor_ids:
        actor_result = await db.execute(
            select(User).where(User.id.in_(actor_ids), User.tenant_id == current_user.tenant_id)
        )
        actors_by_id = {actor.id: actor for actor in actor_result.scalars().all()}

    return UserRoleGrantAuditRecordListResponse(
        user_id=user.id,
        tenant_id=user.tenant_id,
        assignment_scope=DB_BACKED_ROLE_ASSIGNMENT_SCOPE,
        grant_policy_version=ROLE_GRANT_POLICY_VERSION,
        count=len(audit_records),
        audit_records=[
            _serialize_role_grant_audit_record(record, actors_by_id=actors_by_id)
            for record in audit_records
        ],
    )


@router.get("/role-grants/policy", response_model=UserRoleGrantPolicyResponse)
async def get_role_grant_policy(
    current_user: User = Depends(require_role("admin")),
):
    """Get the tenant-scoped DB-backed role assignment policy."""
    del current_user
    return _build_role_grant_policy()


@router.put("/{user_id}/role-grants", response_model=UserRoleGrantSummaryResponse)
async def replace_user_role_grants(
    user_id: int,
    body: UserRoleGrantUpdateRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Replace a user's active elevated governance grants without changing their base role."""
    user = await _get_tenant_user_or_404(db, user_id=user_id, tenant_id=current_user.tenant_id)
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role grants")

    requested_roles = set(body.roles)
    unsupported_roles = requested_roles - GOVERNANCE_GRANT_ROLES
    if unsupported_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported role grants: {', '.join(sorted(unsupported_roles))}",
        )

    result = await db.execute(
        select(UserRoleGrant).where(
            UserRoleGrant.user_id == user.id,
            UserRoleGrant.tenant_id == current_user.tenant_id,
            UserRoleGrant.role.in_(GOVERNANCE_GRANT_ROLES),
        )
    )
    grants_by_role = {grant.role: grant for grant in result.scalars().all()}

    for role in GOVERNANCE_GRANT_ROLES:
        grant = grants_by_role.get(role)
        if role in requested_roles:
            if grant is None:
                grant = UserRoleGrant(
                    tenant_id=current_user.tenant_id,
                    user_id=user.id,
                    role=role,
                    granted_by_user_id=current_user.id,
                    reason=body.reason,
                    is_active=True,
                )
                db.add(grant)
                await db.flush()
                _add_role_grant_audit(
                    db,
                    grant=grant,
                    actor_user_id=current_user.id,
                    action="grant",
                    previous_is_active=None,
                    new_is_active=True,
                    previous_reason=None,
                    new_reason=body.reason,
                    previous_granted_by_user_id=None,
                    new_granted_by_user_id=current_user.id,
                )
            else:
                previous_is_active = grant.is_active
                previous_reason = grant.reason
                previous_granted_by_user_id = grant.granted_by_user_id
                grant.is_active = True
                grant.granted_by_user_id = current_user.id
                grant.reason = body.reason
                if previous_is_active is not True:
                    action = "reactivate"
                elif previous_reason != body.reason or previous_granted_by_user_id != current_user.id:
                    action = "update"
                else:
                    action = None
                if action:
                    _add_role_grant_audit(
                        db,
                        grant=grant,
                        actor_user_id=current_user.id,
                        action=action,
                        previous_is_active=previous_is_active,
                        new_is_active=True,
                        previous_reason=previous_reason,
                        new_reason=body.reason,
                        previous_granted_by_user_id=previous_granted_by_user_id,
                        new_granted_by_user_id=current_user.id,
                    )
        elif grant is not None and grant.is_active:
            previous_reason = grant.reason
            previous_granted_by_user_id = grant.granted_by_user_id
            grant.is_active = False
            _add_role_grant_audit(
                db,
                grant=grant,
                actor_user_id=current_user.id,
                action="revoke",
                previous_is_active=True,
                new_is_active=False,
                previous_reason=previous_reason,
                new_reason=previous_reason,
                previous_granted_by_user_id=previous_granted_by_user_id,
                new_granted_by_user_id=previous_granted_by_user_id,
            )

    await db.commit()
    await db.refresh(user)
    return await _build_user_role_grant_summary(db, user=user)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new user in the current tenant (admin only)."""
    # Check tenant limits
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()

    if tenant:
        user_count_result = await db.execute(
            select(func.count()).where(User.tenant_id == current_user.tenant_id)
        )
        current_count = user_count_result.scalar() or 0
        if current_count >= tenant.max_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant user limit reached ({tenant.max_users}). Upgrade your plan.",
            )

    # Check uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' is already taken",
        )

    user = User(
        username=body.username,
        hashed_password=pwd_context.hash(body.password),
        full_name=body.full_name,
        email=body.email,
        role=body.role,
        tenant_id=current_user.tenant_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a user (admin only)."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent self-deactivation / role-change for admins
    if user_id == current_user.id:
        if body.is_active is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")
        if body.role and body.role != current_user.role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Deactivate a user (soft delete, admin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    await db.commit()

    return MessageResponse(message=f"User '{user.username}' has been deactivated")


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
async def reset_user_password(
    user_id: int,
    body: UserPasswordResetRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Reset another user's password (admin only)."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.hashed_password = pwd_context.hash(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    return MessageResponse(message=f"Password reset for user '{user.username}'")

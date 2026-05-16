import uuid
from collections import Counter

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, User, UserRoleGrant, UserRoleGrantAuditRecord
from app.models_bos import FinalActionAuditRecord
from app.routers.auth import pwd_context
from app.schemas.user import DB_BACKED_ROLE_ASSIGNMENT_SCOPE, GOVERNANCE_GRANT_ROLES, ROLE_GRANT_POLICY_VERSION


class TestCurrentUserProfile:
    @pytest.mark.asyncio
    async def test_get_my_profile(self, client: AsyncClient, admin_headers):
        response = await client.get("/api/v1/users/me", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "test_admin"

    @pytest.mark.asyncio
    async def test_update_my_profile(self, client: AsyncClient, admin_headers):
        response = await client.patch(
            "/api/v1/users/me",
            json={
                "full_name": "Updated Admin",
                "email": "updated_admin@bos.io",
            },
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Admin"
        assert data["email"] == "updated_admin@bos.io"


class TestAdminPasswordReset:
    @pytest.mark.asyncio
    async def test_admin_can_reset_another_user_password(
        self,
        client: AsyncClient,
        admin_headers,
        operator_user,
    ):
        reset_response = await client.post(
            f"/api/v1/users/{operator_user.id}/reset-password",
            json={"new_password": "OperatorReset456!"},
            headers=admin_headers,
        )

        assert reset_response.status_code == 200

        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": operator_user.username,
                "password": "OperatorReset456!",
            },
        )

        assert login_response.status_code == 200
        body = login_response.json()
        assert "access_token" in body


class TestAdminRoleGrants:
    @pytest.mark.asyncio
    async def test_admin_users_list_includes_batched_role_grant_summary(
        self,
        client: AsyncClient,
        admin_headers,
        operator_user,
        db_session: AsyncSession,
    ):
        suffix = uuid.uuid4().hex[:8]
        other_tenant = Tenant(name="Other Admin List Tenant", slug=f"other-admin-list-tenant-{suffix}")
        listed_user_record = User(
            username=f"admin_list_grant_user_{suffix}",
            email=f"admin_list_grant_user_{suffix}@bos.io",
            full_name="Admin List Grant User",
            hashed_password=pwd_context.hash("AdminListGrant123!"),
            role="operator external_release_share_approver",
            tenant_id=operator_user.tenant_id,
            is_active=True,
        )
        db_session.add_all([other_tenant, listed_user_record])
        await db_session.flush()
        db_session.add_all(
            [
                UserRoleGrant(
                    tenant_id=listed_user_record.tenant_id,
                    user_id=listed_user_record.id,
                    role="final_release_approver",
                    granted_by_user_id=None,
                    reason="admin list summary test",
                    is_active=True,
                ),
                UserRoleGrant(
                    tenant_id=listed_user_record.tenant_id,
                    user_id=listed_user_record.id,
                    role="external_runtime_activation_approver",
                    granted_by_user_id=None,
                    reason="runtime activation duty",
                    is_active=True,
                ),
                UserRoleGrant(
                    tenant_id=listed_user_record.tenant_id,
                    user_id=listed_user_record.id,
                    role="external_release_delivery_approver",
                    granted_by_user_id=None,
                    reason="inactive grant should not list",
                    is_active=False,
                ),
                UserRoleGrant(
                    tenant_id=other_tenant.id,
                    user_id=listed_user_record.id,
                    role="model_governance_approver",
                    granted_by_user_id=None,
                    reason="cross-tenant grant should not resolve",
                    is_active=True,
                ),
            ]
        )
        await db_session.commit()

        response = await client.get("/api/v1/admin/users", headers=admin_headers)

        assert response.status_code == 200
        users = response.json()["items"]
        listed_user = next(user for user in users if user["id"] == listed_user_record.id)
        summary = listed_user["role_grant_summary"]
        assert summary["user_id"] == listed_user_record.id
        assert summary["tenant_id"] == listed_user_record.tenant_id
        assert summary["assignment_scope"] == DB_BACKED_ROLE_ASSIGNMENT_SCOPE
        assert summary["grant_policy_version"] == ROLE_GRANT_POLICY_VERSION
        assert summary["legacy_roles"] == ["external_release_share_approver", "operator"]
        assert summary["manageable_governance_grants"] == [
            "external_release_share_approver",
            "external_runtime_activation_approver",
            "final_release_approver",
        ]
        assert summary["manageable_final_action_grants"] == [
            "external_release_share_approver",
            "final_release_approver",
        ]
        assert [grant["role"] for grant in summary["db_grants"]] == [
            "external_runtime_activation_approver",
            "final_release_approver",
        ]
        assert "model_governance_approver" not in summary["resolved_roles"]

    @pytest.mark.asyncio
    async def test_admin_can_replace_elevated_governance_role_grants(
        self,
        client: AsyncClient,
        admin_headers,
        operator_user,
        db_session: AsyncSession,
    ):
        initial_response = await client.get(
            f"/api/v1/users/{operator_user.id}/role-grants",
            headers=admin_headers,
        )
        assert initial_response.status_code == 200
        initial = initial_response.json()
        assert initial["assignment_scope"] == "tenant"
        assert initial["grant_policy_version"] == ROLE_GRANT_POLICY_VERSION
        assert initial["base_role"] == "operator"
        assert initial["db_grants"] == []
        assert "operator" in initial["resolved_roles"]
        assert "final_release_approver" in initial["supported_final_action_grants"]
        assert initial["supported_governance_grants"] == sorted(GOVERNANCE_GRANT_ROLES)
        assert "external_runtime_activation_approver" in initial["supported_governance_grants"]
        assert "external_runtime_activation_approver" not in initial["supported_final_action_grants"]

        replace_response = await client.put(
            f"/api/v1/users/{operator_user.id}/role-grants",
            json={
                "roles": [
                    "final_release_approver",
                    "external_release_delivery_approver",
                    "external_runtime_activation_approver",
                ],
                "reason": "governance duty rotation",
            },
            headers=admin_headers,
        )
        assert replace_response.status_code == 200
        replaced = replace_response.json()
        assert replaced["manageable_governance_grants"] == [
            "external_release_delivery_approver",
            "external_runtime_activation_approver",
            "final_release_approver",
        ]
        assert replaced["manageable_final_action_grants"] == [
            "external_release_delivery_approver",
            "final_release_approver",
        ]
        assert set(replaced["resolved_roles"]) >= {
            "operator",
            "final_release_approver",
            "external_release_delivery_approver",
            "external_runtime_activation_approver",
        }

        active_grants = (
            await db_session.execute(
                select(UserRoleGrant).where(
                    UserRoleGrant.user_id == operator_user.id,
                    UserRoleGrant.is_active.is_(True),
                )
            )
        ).scalars().all()
        assert {grant.role for grant in active_grants} == {
            "final_release_approver",
            "external_release_delivery_approver",
            "external_runtime_activation_approver",
        }

        shrink_response = await client.put(
            f"/api/v1/users/{operator_user.id}/role-grants",
            json={"roles": ["external_runtime_activation_approver"], "reason": "narrow runtime activation duty"},
            headers=admin_headers,
        )
        assert shrink_response.status_code == 200
        shrunk = shrink_response.json()
        assert shrunk["manageable_governance_grants"] == ["external_runtime_activation_approver"]
        assert shrunk["manageable_final_action_grants"] == []

        all_grants = (
            await db_session.execute(
                select(UserRoleGrant).where(UserRoleGrant.user_id == operator_user.id)
            )
        ).scalars().all()
        grants_by_role = {grant.role: grant for grant in all_grants}
        assert grants_by_role["final_release_approver"].is_active is False
        assert grants_by_role["external_release_delivery_approver"].is_active is False
        assert grants_by_role["external_runtime_activation_approver"].is_active is True

        audit_records = (
            await db_session.execute(
                select(UserRoleGrantAuditRecord)
                .where(UserRoleGrantAuditRecord.user_id == operator_user.id)
                .order_by(UserRoleGrantAuditRecord.id.asc())
            )
        ).scalars().all()
        assert Counter((record.role, record.action) for record in audit_records) == Counter(
            [
                ("external_release_delivery_approver", "grant"),
                ("external_runtime_activation_approver", "grant"),
                ("final_release_approver", "grant"),
                ("external_release_delivery_approver", "revoke"),
                ("external_runtime_activation_approver", "update"),
                ("final_release_approver", "revoke"),
            ]
        )
        runtime_update = next(
            record
            for record in audit_records
            if record.role == "external_runtime_activation_approver" and record.action == "update"
        )
        assert runtime_update.previous_is_active is True
        assert runtime_update.new_is_active is True
        assert runtime_update.previous_reason == "governance duty rotation"
        assert runtime_update.new_reason == "narrow runtime activation duty"
        final_action_audit_count = (
            await db_session.execute(select(func.count()).select_from(FinalActionAuditRecord))
        ).scalar() or 0
        assert final_action_audit_count == 0

    @pytest.mark.asyncio
    async def test_role_grant_management_is_admin_and_tenant_scoped(
        self,
        client: AsyncClient,
        admin_headers,
        operator_headers,
        admin_user,
        operator_user,
        db_session: AsyncSession,
    ):
        operator_attempt = await client.put(
            f"/api/v1/users/{operator_user.id}/role-grants",
            json={"roles": ["final_release_approver"]},
            headers=operator_headers,
        )
        assert operator_attempt.status_code == 403

        self_attempt = await client.put(
            f"/api/v1/users/{admin_user.id}/role-grants",
            json={"roles": ["final_release_approver"]},
            headers=admin_headers,
        )
        assert self_attempt.status_code == 400
        assert self_attempt.json()["detail"] == "Cannot change your own role grants"

        unsupported_attempt = await client.put(
            f"/api/v1/users/{operator_user.id}/role-grants",
            json={"roles": ["admin"]},
            headers=admin_headers,
        )
        assert unsupported_attempt.status_code == 422
        assert "Unsupported role grants" in unsupported_attempt.json()["detail"]

        policy_response = await client.get("/api/v1/users/role-grants/policy", headers=admin_headers)
        assert policy_response.status_code == 200
        policy = policy_response.json()
        assert policy["policy_version"] == ROLE_GRANT_POLICY_VERSION
        assert policy["assignment_scope"] == DB_BACKED_ROLE_ASSIGNMENT_SCOPE
        assert policy["audit_history_endpoint"] == "/api/v1/users/{user_id}/role-grants/audit-records"
        assert policy["tenant_scoped"] is True
        assert policy["legacy_role_fallback"] is True
        assert policy["admin_grant_allowed"] is False
        assert policy["self_grant_allowed"] is False
        assert policy["grant_audit_table"] == "user_role_grant_audit_records"
        assert policy["final_action_audit_table"] == "final_action_audit_records"
        assert policy["supported_roles"] == sorted(GOVERNANCE_GRANT_ROLES)
        assert set(policy["forbidden_roles"]) == {"admin", "billing", "operator", "scientist", "viewer"}
        policy_by_role = {role["role"]: role for role in policy["roles"]}
        assert policy_by_role["final_release_approver"]["final_action_role"] is True
        assert policy_by_role["external_runtime_activation_approver"]["category"] == "runtime_activation"

        operator_audit_attempt = await client.get(
            f"/api/v1/users/{operator_user.id}/role-grants/audit-records",
            headers=operator_headers,
        )
        assert operator_audit_attempt.status_code == 403

        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant(name="Other Grant Tenant", slug=f"other-grant-tenant-{suffix}")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)
        other_user = User(
            username=f"other_grant_user_{suffix}",
            email=f"other_grant_user_{suffix}@bos.io",
            full_name="Other Grant User",
            hashed_password=pwd_context.hash("OtherGrant123!"),
            role="operator",
            tenant_id=tenant.id,
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        cross_tenant_response = await client.get(
            f"/api/v1/users/{other_user.id}/role-grants",
            headers=admin_headers,
        )
        assert cross_tenant_response.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_can_read_tenant_scoped_role_grant_audit_history(
        self,
        client: AsyncClient,
        admin_headers,
        operator_user,
        db_session: AsyncSession,
    ):
        await client.put(
            f"/api/v1/users/{operator_user.id}/role-grants",
            json={"roles": ["final_release_approver"], "reason": "initial final release duty"},
            headers=admin_headers,
        )
        await client.put(
            f"/api/v1/users/{operator_user.id}/role-grants",
            json={"roles": [], "reason": "remove final release duty"},
            headers=admin_headers,
        )
        await client.put(
            f"/api/v1/users/{operator_user.id}/role-grants",
            json={"roles": ["final_release_approver"], "reason": "restore final release duty"},
            headers=admin_headers,
        )
        await client.put(
            f"/api/v1/users/{operator_user.id}/role-grants",
            json={"roles": ["final_release_approver"], "reason": "metadata refresh"},
            headers=admin_headers,
        )

        response = await client.get(
            f"/api/v1/users/{operator_user.id}/role-grants/audit-records",
            headers=admin_headers,
        )

        assert response.status_code == 200
        history = response.json()
        assert history["user_id"] == operator_user.id
        assert history["tenant_id"] == operator_user.tenant_id
        assert history["assignment_scope"] == DB_BACKED_ROLE_ASSIGNMENT_SCOPE
        assert history["grant_policy_version"] == ROLE_GRANT_POLICY_VERSION
        assert history["count"] == 4
        records = history["audit_records"]
        assert [record["action"] for record in records] == ["update", "reactivate", "revoke", "grant"]
        assert {record["role"] for record in records} == {"final_release_approver"}
        assert all(record["actor_username"] == "test_admin" for record in records)
        assert records[0]["previous_is_active"] is True
        assert records[0]["new_is_active"] is True
        assert records[0]["previous_reason"] == "restore final release duty"
        assert records[0]["new_reason"] == "metadata refresh"
        assert records[1]["previous_is_active"] is False
        assert records[1]["new_is_active"] is True
        assert records[2]["previous_is_active"] is True
        assert records[2]["new_is_active"] is False
        assert records[3]["previous_is_active"] is None
        assert records[3]["new_is_active"] is True

        filtered_response = await client.get(
            f"/api/v1/users/{operator_user.id}/role-grants/audit-records",
            params={"action": "reactivate", "role": "final_release_approver"},
            headers=admin_headers,
        )
        assert filtered_response.status_code == 200
        filtered_records = filtered_response.json()["audit_records"]
        assert len(filtered_records) == 1
        assert filtered_records[0]["action"] == "reactivate"

        final_action_audit_count = (
            await db_session.execute(select(func.count()).select_from(FinalActionAuditRecord))
        ).scalar() or 0
        assert final_action_audit_count == 0

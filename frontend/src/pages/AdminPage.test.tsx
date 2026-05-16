/**
 * @vitest-environment jsdom
 */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { adminApiMock, userApiMock } = vi.hoisted(() => ({
  adminApiMock: {
    getHealth: vi.fn(),
    getUsers: vi.fn(),
    getSessions: vi.fn(),
    getFeatureFlags: vi.fn(),
    setFeatureFlag: vi.fn(),
    resetFeatureFlag: vi.fn(),
  },
  userApiMock: {
    create: vi.fn(),
    update: vi.fn(),
    deactivate: vi.fn(),
    resetPassword: vi.fn(),
    getRoleGrants: vi.fn(),
    getRoleGrantPolicy: vi.fn(),
    getRoleGrantAuditRecords: vi.fn(),
    replaceRoleGrants: vi.fn(),
  },
}));

vi.mock("react-hot-toast", () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/api/adminApi", () => ({
  adminApi: adminApiMock,
}));

vi.mock("@/api/userApi", () => ({
  userApi: userApiMock,
}));

import AdminPage from "@/pages/AdminPage";

const testGlobal = globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean };

describe("AdminPage governance grant presentation", () => {
  let container: HTMLDivElement;
  let root: ReturnType<typeof createRoot>;

  beforeEach(() => {
    testGlobal.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    adminApiMock.getHealth.mockResolvedValue({
      status: "healthy",
      database: "connected",
      redis: "connected",
      version: "test",
      uptime_seconds: 3600,
    });
    const roleGrantSummary = {
      user_id: 7,
      tenant_id: 1,
      assignment_scope: "tenant",
      grant_policy_version: "tenant_governance_grants_v1",
      base_role: "operator",
      legacy_roles: ["operator"],
      db_grants: [
        {
          id: 1,
          user_id: 7,
          tenant_id: 1,
          role: "final_release_approver",
          is_active: true,
          granted_by_user_id: 1,
          reason: "test",
          created_at: "2026-04-26T00:00:00Z",
          updated_at: "2026-04-26T00:00:00Z",
        },
        {
          id: 2,
          user_id: 7,
          tenant_id: 1,
          role: "external_runtime_activation_approver",
          is_active: true,
          granted_by_user_id: 1,
          reason: "test",
          created_at: "2026-04-26T00:00:00Z",
          updated_at: "2026-04-26T00:00:00Z",
        },
      ],
      resolved_roles: ["external_runtime_activation_approver", "final_release_approver", "operator"],
      manageable_governance_grants: ["external_runtime_activation_approver", "final_release_approver"],
      supported_governance_grants: [
        "external_release_delivery_approver",
        "external_release_share_approver",
        "external_runtime_activation_approver",
        "final_release_approver",
        "model_governance_approver",
      ],
      manageable_final_action_grants: ["final_release_approver"],
      supported_final_action_grants: [
        "external_release_delivery_approver",
        "external_release_share_approver",
        "final_release_approver",
        "model_governance_approver",
      ],
    };
    adminApiMock.getUsers.mockResolvedValue([
      {
        id: 7,
        username: "release_approver",
        full_name: "Release Approver",
        email: "release@example.com",
        role: "operator",
        tenant_id: 1,
        is_active: true,
        created_at: "2026-04-26T00:00:00Z",
        last_login: null,
        role_grant_summary: roleGrantSummary,
      },
      {
        id: 8,
        username: "audit_viewer",
        full_name: "Audit Viewer",
        email: "audit@example.com",
        role: "operator",
        tenant_id: 1,
        is_active: true,
        created_at: "2026-04-26T00:00:00Z",
        last_login: null,
        role_grant_summary: {
          ...roleGrantSummary,
          user_id: 8,
          db_grants: [],
          resolved_roles: ["operator"],
          manageable_governance_grants: [],
          manageable_final_action_grants: [],
        },
      },
    ]);
    adminApiMock.getSessions.mockResolvedValue([]);
    adminApiMock.getFeatureFlags.mockResolvedValue({ flags: {}, source: "test" });
    userApiMock.getRoleGrantPolicy.mockResolvedValue({
      policy_version: "tenant_governance_grants_v1",
      assignment_scope: "tenant",
      grant_endpoint: "/api/v1/users/{user_id}/role-grants",
      audit_history_endpoint: "/api/v1/users/{user_id}/role-grants/audit-records",
      tenant_scoped: true,
      legacy_role_fallback: true,
      admin_grant_allowed: false,
      self_grant_allowed: false,
      grant_audit_table: "user_role_grant_audit_records",
      final_action_audit_table: "final_action_audit_records",
      supported_roles: [
        "external_release_delivery_approver",
        "external_release_share_approver",
        "external_runtime_activation_approver",
        "final_release_approver",
        "model_governance_approver",
      ],
      forbidden_roles: ["admin", "billing", "operator", "scientist", "viewer"],
      roles: [
        {
          role: "final_release_approver",
          label: "Final release approver",
          category: "final_action",
          assignment_scope: "tenant",
          grant_endpoint_allowed: true,
          final_action_role: true,
          description: "Can execute approved final release approval requests.",
        },
        {
          role: "external_runtime_activation_approver",
          label: "Runtime activation approver",
          category: "runtime_activation",
          assignment_scope: "tenant",
          grant_endpoint_allowed: true,
          final_action_role: false,
          description: "Can approve and execute external knowledge runtime activation and rollback.",
        },
      ],
    });
    userApiMock.getRoleGrantAuditRecords.mockResolvedValue({
      user_id: 7,
      tenant_id: 1,
      assignment_scope: "tenant",
      grant_policy_version: "tenant_governance_grants_v1",
      count: 2,
      audit_records: [
        {
          id: 12,
          tenant_id: 1,
          user_id: 7,
          role_grant_id: 2,
          actor_user_id: 1,
          actor_username: "test_admin",
          actor_full_name: "Test Admin",
          role: "external_runtime_activation_approver",
          action: "update",
          previous_is_active: true,
          new_is_active: true,
          previous_reason: "initial",
          new_reason: "rotation update",
          previous_granted_by_user_id: 1,
          new_granted_by_user_id: 1,
          created_at: "2026-04-26T00:10:00Z",
        },
        {
          id: 11,
          tenant_id: 1,
          user_id: 7,
          role_grant_id: 1,
          actor_user_id: 1,
          actor_username: "test_admin",
          actor_full_name: "Test Admin",
          role: "final_release_approver",
          action: "grant",
          previous_is_active: null,
          new_is_active: true,
          previous_reason: null,
          new_reason: "initial",
          previous_granted_by_user_id: null,
          new_granted_by_user_id: 1,
          created_at: "2026-04-26T00:00:00Z",
        },
      ],
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  it("shows base role separately from elevated governance grants", async () => {
    await act(async () => {
      root.render(<AdminPage />);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(userApiMock.getRoleGrants).not.toHaveBeenCalled();
    expect(userApiMock.getRoleGrantPolicy).toHaveBeenCalledOnce();
    expect(userApiMock.getRoleGrantAuditRecords).toHaveBeenCalledWith(7);
    expect(userApiMock.getRoleGrantAuditRecords).toHaveBeenCalledTimes(1);
    const operatorsTab = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "Operators",
    );
    expect(operatorsTab).toBeTruthy();
    await act(async () => {
      operatorsTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
    });

    expect(container.textContent).toContain("2 governance grants");
    expect(container.textContent).toContain("Governance grants");
    expect(container.textContent).toContain("Final release approver");
    expect(container.textContent).toContain("Runtime activation approver");
    expect(container.textContent).toContain("Recent grant history");
    expect(container.textContent).toContain("Read-only from user_role_grant_audit_records");
    expect(container.textContent).toContain("Final Action audit stays separate");
    expect(container.textContent).toContain("Update");
    expect(container.textContent).toContain("Grant");
    expect(container.textContent).toContain("Test Admin");
    expect(container.textContent).toContain("rotation update");
    expect(container.textContent).toContain("Admin grant forbidden");
    expect(container.textContent).toContain("Self grant forbidden");
    expect(container.textContent).toContain("Operator");

    const auditViewerRow = Array.from(container.querySelectorAll("tr")).find((row) =>
      row.textContent?.includes("audit_viewer"),
    );
    expect(auditViewerRow).toBeTruthy();
    await act(async () => {
      auditViewerRow?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(userApiMock.getRoleGrantAuditRecords).toHaveBeenCalledTimes(2);
    expect(userApiMock.getRoleGrantAuditRecords).toHaveBeenLastCalledWith(8);
    expect(userApiMock.getRoleGrants).not.toHaveBeenCalled();
  });
});

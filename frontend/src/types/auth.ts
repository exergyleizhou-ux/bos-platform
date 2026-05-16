/**
 * BOS Pipeline v9.0 auth types.
 *
 * Type definitions for authentication, users, and roles.
 */

// Roles
export const ROLES = [
  "viewer",
  "billing",
  "operator",
  "scientist",
  "admin",
  "final_release_approver",
  "model_governance_approver",
  "external_release_share_approver",
  "external_release_delivery_approver",
  "external_runtime_activation_approver",
] as const;
export type Role = (typeof ROLES)[number];

export const BASE_ROLES = ["viewer", "billing", "operator", "scientist", "admin"] as const;
export type BaseRole = (typeof BASE_ROLES)[number];

export const FINAL_ACTION_GRANT_ROLES = [
  "final_release_approver",
  "model_governance_approver",
  "external_release_share_approver",
  "external_release_delivery_approver",
] as const;
export type FinalActionGrantRole = (typeof FINAL_ACTION_GRANT_ROLES)[number];

export const GOVERNANCE_GRANT_ROLES = [
  ...FINAL_ACTION_GRANT_ROLES,
  "external_runtime_activation_approver",
] as const;
export type GovernanceGrantRole = (typeof GOVERNANCE_GRANT_ROLES)[number];

// Role hierarchy (index = privilege level)
const ROLE_HIERARCHY: Record<string, number> = {
  viewer: 0,
  billing: 0,
  operator: 1,
  final_release_approver: 1,
  model_governance_approver: 1,
  external_release_share_approver: 1,
  external_release_delivery_approver: 1,
  external_runtime_activation_approver: 1,
  scientist: 2,
  admin: 3,
};

function parseRoles(role: string): string[] {
  return role.split(/[\s,;|]+/).filter(Boolean);
}

/**
 * Check if userRole meets or exceeds requiredRole.
 */
export function hasMinimumRole(userRole: string, requiredRole: string): boolean {
  const userLevels = parseRoles(userRole).map((role) => ROLE_HIERARCHY[role] ?? -1);
  const userLevel = userLevels.length ? Math.max(...userLevels) : -1;
  const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 999;
  return userLevel >= requiredLevel;
}

import { translateText } from "@/lib/i18n";

/**
 * Human-readable role label.
 */
export function getRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    viewer: "Viewer",
    billing: "Billing",
    operator: "Operator",
    scientist: "Scientist",
    admin: "Administrator",
    final_release_approver: "Final release approver",
    model_governance_approver: "Model governance approver",
    external_release_share_approver: "External share approver",
    external_release_delivery_approver: "External delivery approver",
    external_runtime_activation_approver: "External runtime activation approver",
  };
  return parseRoles(role)
    .map((roleName) => translateText(labels[roleName] ?? roleName))
    .join(", ");
}

// User types
export interface User {
  id: number;
  username: string;
  full_name: string;
  email: string | null;
  role: string;
  tenant_id: number;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
  role_grant_summary?: UserRoleGrantSummary | null;
}

export interface UserRoleGrant {
  id: number;
  user_id: number;
  tenant_id: number;
  role: string;
  is_active: boolean;
  granted_by_user_id: number | null;
  reason: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserRoleGrantSummary {
  user_id: number;
  tenant_id: number;
  assignment_scope: string;
  grant_policy_version: string;
  base_role: string;
  legacy_roles: string[];
  db_grants: UserRoleGrant[];
  resolved_roles: string[];
  manageable_governance_grants?: string[];
  supported_governance_grants?: string[];
  manageable_final_action_grants: string[];
  supported_final_action_grants: string[];
}

export interface UserRoleGrantAuditRecord {
  id: number;
  tenant_id: number;
  user_id: number;
  role_grant_id: number | null;
  actor_user_id: number | null;
  actor_username: string | null;
  actor_full_name: string | null;
  role: string;
  action: "grant" | "revoke" | "reactivate" | "update";
  previous_is_active: boolean | null;
  new_is_active: boolean | null;
  previous_reason: string | null;
  new_reason: string | null;
  previous_granted_by_user_id: number | null;
  new_granted_by_user_id: number | null;
  created_at: string | null;
}

export interface UserRoleGrantAuditRecordList {
  user_id: number;
  tenant_id: number;
  assignment_scope: string;
  grant_policy_version: string;
  count: number;
  audit_records: UserRoleGrantAuditRecord[];
}

export interface UserRoleGrantPolicyRole {
  role: string;
  label: string;
  category: string;
  assignment_scope: string;
  grant_endpoint_allowed: boolean;
  final_action_role: boolean;
  description: string;
}

export interface UserRoleGrantPolicy {
  policy_version: string;
  assignment_scope: string;
  grant_endpoint: string;
  audit_history_endpoint: string;
  tenant_scoped: boolean;
  legacy_role_fallback: boolean;
  admin_grant_allowed: boolean;
  self_grant_allowed: boolean;
  grant_audit_table: string;
  final_action_audit_table: string;
  supported_roles: string[];
  forbidden_roles: string[];
  roles: UserRoleGrantPolicyRole[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type TokenPair = TokenResponse;

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface ProfileUpdateRequest {
  full_name?: string;
  email?: string;
}

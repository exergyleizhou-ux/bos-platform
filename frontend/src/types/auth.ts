/**
 * BOS Pipeline v9.0 �� Auth Types
 *
 * Type definitions for authentication, users, and roles.
 */

// ���� Roles ����
export const ROLES = ["viewer", "operator", "analyst", "admin"] as const;
export type Role = (typeof ROLES)[number];

// ���� Role Hierarchy (index = privilege level) ����
const ROLE_HIERARCHY: Record<string, number> = {
  viewer: 0,
  operator: 1,
  analyst: 2,
  admin: 3,
};

/**
 * Check if userRole meets or exceeds requiredRole.
 */
export function hasMinimumRole(
  userRole: string,
  requiredRole: string,
): boolean {
  const userLevel = ROLE_HIERARCHY[userRole] ?? -1;
  const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 999;
  return userLevel >= requiredLevel;
}

/**
 * Human-readable role label.
 */
export function getRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    viewer: "Viewer",
    operator: "Operator",
    analyst: "Analyst",
    admin: "Administrator",
  };
  return labels[role] ?? role;
}

// ���� User Types ����
export interface User {
  id: number;
  username: string;
  full_name: string;
  email: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
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

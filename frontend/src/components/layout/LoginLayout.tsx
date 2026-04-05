/**
 * BOS Pipeline v9.0 �� Login Layout
 *
 * Minimal layout wrapper for the login page (no sidebar, no top bar).
 */

import { Outlet, Navigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";

export function LoginLayout() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);

  // If already authenticated, redirect to dashboard
  if (isAuthenticated && user) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}

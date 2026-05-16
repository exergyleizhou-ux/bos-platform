/**
 * BOS Pipeline v9.0 -Login Layout
 *
 * Minimal layout wrapper for the login page (no sidebar, no top bar).
 */

import { Outlet, Navigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { useUIStore } from "@/store/uiStore";

export function LoginLayout() {
 const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
 const user = useAuthStore((s) => s.user);
 const loginTransitionActive = useUIStore((s) => s.loginTransitionActive);

  // If already authenticated, redirect to the assistant first
  if (isAuthenticated && user && !loginTransitionActive) {
  return <Navigate to="/bos" replace />;
  }

 return <Outlet />;
}

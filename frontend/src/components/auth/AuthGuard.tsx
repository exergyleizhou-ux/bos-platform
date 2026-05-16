/**
 * BOS Pipeline v9.0 auth guard.
 *
 * Protects routes by verifying authentication and optional role requirements.
 * Redirects to /login if unauthenticated, or /bos if the role is insufficient.
 */

import { useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { LoadingScreen } from "@/components/ui/LoadingScreen";
import { useAuthStore } from "@/store/authStore";
import { hasMinimumRole } from "@/types/auth";

interface AuthGuardProps {
  children: React.ReactNode;
  requiredRole?: string;
}

export function AuthGuard({ children, requiredRole }: AuthGuardProps) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const fetchProfile = useAuthStore((s) => s.fetchProfile);
  const location = useLocation();

  useEffect(() => {
    if (accessToken && !user && !isLoading) {
      fetchProfile();
    }
  }, [accessToken, user, isLoading, fetchProfile]);

  if (isLoading || (accessToken && !user)) {
    return <LoadingScreen label="Authenticating..." />;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (requiredRole && !hasMinimumRole(user.role, requiredRole)) {
    return <Navigate to="/bos" replace />;
  }

  return <>{children}</>;
}

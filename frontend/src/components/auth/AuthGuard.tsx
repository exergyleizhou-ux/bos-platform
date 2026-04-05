/**
 * BOS Pipeline v9.0 �� Auth Guard
 *
 * Protects routes by verifying authentication and optional role requirements.
 * Redirects to /login if unauthenticated, /dashboard if insufficient role.
 */

import { useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuthStore } from "@/store/authStore";
import { hasMinimumRole } from "@/types/auth";
import { LoadingScreen } from "@/components/ui/LoadingScreen";

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

  // Attempt profile fetch on mount if we have a token but no user
  useEffect(() => {
    if (accessToken && !user && !isLoading) {
      fetchProfile();
    }
  }, [accessToken, user, isLoading, fetchProfile]);

  // Loading state
  if (isLoading || (accessToken && !user)) {
    return <LoadingScreen label="Authenticating��" />;
  }

  // Not authenticated
  if (!isAuthenticated || !user) {
    return (
      <Navigate
        to="/login"
        state={{ from: location.pathname }}
        replace
      />
    );
  }

  // Role check
  if (requiredRole && !hasMinimumRole(user.role, requiredRole)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

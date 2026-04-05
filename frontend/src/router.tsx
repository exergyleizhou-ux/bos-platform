/**
 * BOS Pipeline v9.0 �� Router Configuration
 *
 * React Router with lazy-loaded pages, auth guards, and nested layouts.
 */

import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { LoginLayout } from "@/components/layout/LoginLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { LoadingScreen } from "@/components/ui/LoadingScreen";

// ���� Lazy Page Imports ����
const LoginPage = lazy(() => import("@/pages/LoginPage"));
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const BatchListPage = lazy(() => import("@/pages/BatchListPage"));
const BatchDetailPage = lazy(() => import("@/pages/BatchDetailPage"));
const BatchCreatePage = lazy(() => import("@/pages/BatchCreatePage"));
const SERPage = lazy(() => import("@/pages/SERPage"));
const SimulationPage = lazy(() => import("@/pages/SimulationPage"));
const ForecastPage = lazy(() => import("@/pages/ForecastPage"));
const TwinListPage = lazy(() => import("@/pages/TwinListPage"));
const TwinDetailPage = lazy(() => import("@/pages/TwinDetailPage"));
const SustainabilityPage = lazy(() => import("@/pages/SustainabilityPage"));
const SettingsPage = lazy(() => import("@/pages/SettingsPage"));
const AdminPage = lazy(() => import("@/pages/AdminPage"));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));

// ���� Suspense Wrapper ����
function SuspenseWrap({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<LoadingScreen label="Loading page��" />}>
      {children}
    </Suspense>
  );
}

// ���� Router ����
export const router = createBrowserRouter([
  // ���� Public: Login ����
  {
    element: <LoginLayout />,
    children: [
      {
        path: "/login",
        element: (
          <SuspenseWrap>
            <LoginPage />
          </SuspenseWrap>
        ),
      },
    ],
  },

  // ���� Protected: App Shell ����
  {
    element: (
      <AuthGuard>
        <AppLayout />
      </AuthGuard>
    ),
    children: [
      {
        path: "/dashboard",
        element: (
          <SuspenseWrap>
            <DashboardPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/batches",
        element: (
          <SuspenseWrap>
            <BatchListPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/batches/new",
        element: (
          <SuspenseWrap>
            <BatchCreatePage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/batches/:id",
        element: (
          <SuspenseWrap>
            <BatchDetailPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/ser",
        element: (
          <SuspenseWrap>
            <SERPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/simulation",
        element: (
          <SuspenseWrap>
            <SimulationPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/forecast",
        element: (
          <SuspenseWrap>
            <ForecastPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/twins",
        element: (
          <SuspenseWrap>
            <TwinListPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/twins/:id",
        element: (
          <SuspenseWrap>
            <TwinDetailPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/sustainability",
        element: (
          <SuspenseWrap>
            <SustainabilityPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/settings",
        element: (
          <SuspenseWrap>
            <SettingsPage />
          </SuspenseWrap>
        ),
      },
      {
        path: "/admin",
        element: (
          <AuthGuard requiredRole="admin">
            <SuspenseWrap>
              <AdminPage />
            </SuspenseWrap>
          </AuthGuard>
        ),
      },
    ],
  },

  // ���� Redirects & Catch-all ����
  {
    path: "/",
    element: <Navigate to="/dashboard" replace />,
  },
  {
    path: "*",
    element: (
      <SuspenseWrap>
        <NotFoundPage />
      </SuspenseWrap>
    ),
  },
]);

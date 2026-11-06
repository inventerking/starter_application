import { createBrowserRouter, Navigate } from "react-router"

import { AdminDetailPage } from "@/features/admin-management/admin-detail-page"
import { AdminsListPage } from "@/features/admin-management/admins-list-page"
import { AdminRoleDetailPage, AdminRolesPage } from "@/features/admin-roles/pages"
import { AuditPage } from "@/features/audit/audit-page"
import { ChangePasswordPage } from "@/features/authentication/change-password-page"
import { RequireAuthenticated, RequirePermission, RequireSession } from "@/features/authentication/guards"
import { LoginPage } from "@/features/authentication/login-page"
import { MfaVerifyPage } from "@/features/authentication/mfa-verify-page"
import { ClientRoleDetailPage, ClientRolesPage } from "@/features/client-roles/pages"
import { DashboardPage } from "@/features/dashboard/dashboard-page"
import { SetupMfaPage } from "@/features/mfa/setup-mfa-page"
import { PermissionsPage } from "@/features/permissions/permissions-page"
import { SecurityPage } from "@/features/security/security-page"
import { UserDetailPage } from "@/features/user-management/user-detail-page"
import { UsersListPage } from "@/features/user-management/users-list-page"
import { AppLayout } from "@/layouts/app-layout"

const guarded = (permission: string, element: React.ReactNode) => <RequirePermission permission={permission}>{element}</RequirePermission>

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/login/mfa", element: <MfaVerifyPage /> },
  { path: "/change-password", element: <RequireAuthenticated><ChangePasswordPage /></RequireAuthenticated> },
  { path: "/setup-mfa", element: <RequireAuthenticated><SetupMfaPage /></RequireAuthenticated> },
  {
    element: <RequireSession />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <DashboardPage /> },
          // User Management: Client users and Client roles.
          { path: "users", element: guarded("users.view", <UsersListPage />) },
          { path: "users/:id", element: guarded("users.view", <UserDetailPage />) },
          { path: "client-roles", element: guarded("client_roles.view", <ClientRolesPage />) },
          { path: "client-roles/:id", element: guarded("client_roles.view", <ClientRoleDetailPage />) },
          // Admin Management: Admin accounts and Admin roles.
          { path: "admins", element: guarded("admins.view", <AdminsListPage />) },
          { path: "admins/:id", element: guarded("admins.view", <AdminDetailPage />) },
          { path: "admin-roles", element: guarded("admin_roles.view", <AdminRolesPage />) },
          { path: "admin-roles/:id", element: guarded("admin_roles.view", <AdminRoleDetailPage />) },
          { path: "permissions", element: <PermissionsPage /> },
          { path: "audit", element: guarded("audit.view", <AuditPage />) },
          { path: "security", element: <SecurityPage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
])

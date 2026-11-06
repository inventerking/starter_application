import { createBrowserRouter, Navigate } from "react-router"

import { ChangePasswordPage } from "@/features/authentication/change-password-page"
import { RequireAuthenticated, RequireSession } from "@/features/authentication/guards"
import { LoginPage } from "@/features/authentication/login-page"
import { MfaVerifyPage } from "@/features/authentication/mfa-verify-page"
import { RegisterPage } from "@/features/authentication/register-page"
import { SetupMfaPage } from "@/features/mfa/setup-mfa-page"
import { ProfilePage } from "@/features/profile/profile-page"
import { SecurityPage } from "@/features/security/security-page"
import { AppLayout } from "@/layouts/app-layout"

const registrationEnabled = import.meta.env.VITE_REGISTRATION_ENABLED === "true"

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/login/mfa", element: <MfaVerifyPage /> },
  ...(registrationEnabled ? [{ path: "/register", element: <RegisterPage /> }] : []),
  { path: "/change-password", element: <RequireAuthenticated><ChangePasswordPage /></RequireAuthenticated> },
  { path: "/setup-mfa", element: <RequireAuthenticated><SetupMfaPage /></RequireAuthenticated> },
  {
    element: <RequireSession />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <ProfilePage /> },
          { path: "security", element: <SecurityPage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
])

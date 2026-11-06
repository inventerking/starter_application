import type { ReactNode } from "react"
import { Navigate, Outlet } from "react-router"

import { useAuth } from "@/features/authentication/auth-context"
import { Skeleton } from "@/components/ui/skeleton"

function FullPageLoading() {
  return (
    <div className="flex min-h-svh items-center justify-center" aria-label="Loading">
      <Skeleton className="h-32 w-80" />
    </div>
  )
}

/** Sends people to the right place. The backend independently rejects restricted sessions. */
export function RequireSession() {
  const { status, user } = useAuth()
  if (status === "loading") return <FullPageLoading />
  if (status === "anonymous" || !user) return <Navigate to="/login" replace />
  if (user.must_change_password) return <Navigate to="/change-password" replace />
  if (user.session_scope !== "full" || user.mfa_enrollment_required) return <Navigate to="/setup-mfa" replace />
  return <Outlet />
}

export function RequireAuthenticated({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === "loading") return <FullPageLoading />
  if (status === "anonymous") return <Navigate to="/login" replace />
  return <>{children}</>
}

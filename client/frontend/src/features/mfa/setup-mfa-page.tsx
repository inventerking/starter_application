import { Navigate, useNavigate } from "react-router"

import { Button } from "@/components/ui/button"
import { AuthCard } from "@/features/authentication/auth-card"
import { useAuth } from "@/features/authentication/auth-context"
import { MfaEnrollment } from "@/features/mfa/mfa-enrollment"

export function SetupMfaPage() {
  const { user, reloadUser, logout } = useAuth()
  const navigate = useNavigate()
  if (user?.must_change_password) return <Navigate to="/change-password" replace />
  return (
    <AuthCard title="Set up two-factor authentication" description="This account must use two-factor authentication.">
      <div className="grid gap-4">
        <MfaEnrollment
          onDone={async () => {
            await reloadUser()
            navigate("/", { replace: true })
          }}
        />
        <Button variant="link" className="w-fit" onClick={() => logout()}>
          Sign out
        </Button>
      </div>
    </AuthCard>
  )
}

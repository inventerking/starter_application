import { useNavigate } from "react-router"

import { AuthCard } from "@/features/authentication/auth-card"
import { useAuth } from "@/features/authentication/auth-context"
import { PasswordForm } from "@/features/authentication/password-form"

export function ChangePasswordPage() {
  const { reloadUser } = useAuth()
  const navigate = useNavigate()
  return (
    <AuthCard title="Choose a new password" description="Your temporary password must be replaced before you can continue.">
      <PasswordForm
        onChanged={async () => {
          await reloadUser()
          navigate("/", { replace: true })
        }}
      />
    </AuthCard>
  )
}

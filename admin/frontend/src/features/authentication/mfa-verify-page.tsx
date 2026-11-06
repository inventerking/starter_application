import { useState } from "react"
import { Link, Navigate, useLocation, useNavigate } from "react-router"

import { AuthCard } from "@/features/authentication/auth-card"
import { useAuth } from "@/features/authentication/auth-context"
import { FormError } from "@/components/form-error"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError } from "@/lib/api"

export function MfaVerifyPage() {
  const { verifyMfa } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const challenge: string | undefined = location.state?.challenge
  const [useRecovery, setUseRecovery] = useState(false)
  const [value, setValue] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  if (!challenge) return <Navigate to="/login" replace />

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await verifyMfa({ challenge_token: challenge, ...(useRecovery ? { recovery_code: value } : { code: value }) })
      navigate("/", { replace: true })
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "invalid_mfa_challenge") {
        navigate("/login", { replace: true })
        return
      }
      setError(caught)
      setValue("")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard
      title="Two-factor authentication"
      description={useRecovery ? "Enter one of your saved recovery codes." : "Enter the 6-digit code from your authenticator app."}
    >
      <form className="grid gap-4" onSubmit={submit}>
        <FormError error={error} />
        <div className="grid gap-1.5">
          <Label htmlFor="mfa-value">{useRecovery ? "Recovery code" : "Verification code"}</Label>
          <Input
            id="mfa-value"
            autoFocus
            autoComplete="one-time-code"
            inputMode={useRecovery ? "text" : "numeric"}
            maxLength={useRecovery ? 16 : 6}
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </div>
        <Button type="submit" disabled={busy || !value}>
          Verify
        </Button>
        <Button
          type="button"
          variant="link"
          onClick={() => {
            setUseRecovery(!useRecovery)
            setValue("")
          }}
        >
          {useRecovery ? "Use an authenticator code" : "Use a recovery code"}
        </Button>
        <Link className="text-muted-foreground text-center text-sm hover:underline" to="/login">
          Back to sign in
        </Link>
      </form>
    </AuthCard>
  )
}

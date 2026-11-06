import { useState } from "react"

import { FormError } from "@/components/form-error"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RecoveryCodesView } from "@/features/mfa/recovery-codes-view"
import { api } from "@/lib/api"
import type { MfaSetup } from "@/lib/types"

/** Setup, then a first code, then recovery codes. MFA is enabled only by the confirmed code. */
export function MfaEnrollment({ onDone }: { onDone: () => void | Promise<void> }) {
  const [password, setPassword] = useState("")
  const [setup, setSetup] = useState<MfaSetup | null>(null)
  const [code, setCode] = useState("")
  const [codes, setCodes] = useState<string[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  if (codes) {
    return (
      <div className="grid gap-4">
        <RecoveryCodesView codes={codes} />
        <Button className="w-fit" onClick={() => onDone()}>
          I have saved my codes
        </Button>
      </div>
    )
  }

  if (!setup) {
    return (
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          run(async () => {
            setSetup(await api.post<MfaSetup>("/auth/mfa/setup", { password }))
            setPassword("")
          })
        }}
      >
        <FormError error={error} />
        <div className="grid gap-1.5">
          <Label htmlFor="mfa-password">Confirm your password to begin</Label>
          <Input id="mfa-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </div>
        <Button type="submit" className="w-fit" disabled={busy || !password}>
          Continue
        </Button>
      </form>
    )
  }

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        run(async () => {
          const result = await api.post<{ recovery_codes: string[] }>("/auth/mfa/confirm", { code })
          setCodes(result.recovery_codes)
          setSetup(null)
        })
      }}
    >
      <FormError error={error} />
      <p className="text-sm">Scan this QR code with Google Authenticator or any TOTP app.</p>
      <img src={setup.qr_code} alt="QR code for your authenticator app" className="size-48 rounded-md border bg-white" />
      <details className="text-sm">
        <summary className="cursor-pointer">Can't scan it? Enter the key manually</summary>
        <code className="bg-muted mt-2 block rounded-md p-2 break-all">{setup.secret}</code>
        <p className="text-muted-foreground mt-1 text-xs">
          Account: {setup.issuer}:{setup.account}. Time-based, 6 digits, 30 seconds.
        </p>
      </details>
      <div className="grid gap-1.5">
        <Label htmlFor="mfa-code">6-digit code</Label>
        <Input id="mfa-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value)} />
      </div>
      <Button type="submit" className="w-fit" disabled={busy || code.length !== 6}>
        Enable two-factor authentication
      </Button>
    </form>
  )
}

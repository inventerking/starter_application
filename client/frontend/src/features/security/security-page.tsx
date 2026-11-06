import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { FormError } from "@/components/form-error"
import { PageHeader } from "@/components/page-header"
import { QueryState } from "@/components/query-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAuth } from "@/features/authentication/auth-context"
import { PasswordForm } from "@/features/authentication/password-form"
import { MfaEnrollment } from "@/features/mfa/mfa-enrollment"
import { RecoveryCodesView } from "@/features/mfa/recovery-codes-view"
import { api } from "@/lib/api"
import { formatDate } from "@/lib/format"
import type { SessionInfo } from "@/lib/types"

interface MfaStatus {
  enabled: boolean
  confirmed_at: string | null
  recovery_codes_remaining: number
}

function MfaCard() {
  const { reloadUser } = useAuth()
  const queryClient = useQueryClient()
  const [enrolling, setEnrolling] = useState(false)
  const [disablePassword, setDisablePassword] = useState("")
  const [disableCode, setDisableCode] = useState("")
  const [regenerateCode, setRegenerateCode] = useState("")
  const [newCodes, setNewCodes] = useState<string[] | null>(null)
  const status = useQuery({ queryKey: ["mfa-status"], queryFn: () => api.get<MfaStatus>("/auth/mfa/status") })
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["mfa-status"] })
    await reloadUser()
  }
  const disable = useMutation({
    mutationFn: () => api.post("/auth/mfa/disable", { password: disablePassword, code: disableCode }),
    onSuccess: async () => {
      setDisablePassword("")
      setDisableCode("")
      toast.success("Two-factor authentication disabled")
      await refresh()
    },
  })
  const regenerate = useMutation({
    mutationFn: () => api.post<{ recovery_codes: string[] }>("/auth/mfa/recovery-codes/regenerate", { code: regenerateCode }),
    onSuccess: async (result) => {
      setRegenerateCode("")
      setNewCodes(result.recovery_codes)
      await refresh()
    },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Two-factor authentication</CardTitle>
        <CardDescription>Protect your account with an authenticator app.</CardDescription>
      </CardHeader>
      <CardContent>
        <QueryState query={status}>
          {(data) =>
            !data.enabled ? (
              enrolling ? (
                <MfaEnrollment
                  onDone={async () => {
                    setEnrolling(false)
                    await refresh()
                  }}
                />
              ) : (
                <div className="grid gap-3">
                  <Badge variant="outline" className="w-fit">
                    Disabled
                  </Badge>
                  <Button className="w-fit" onClick={() => setEnrolling(true)}>
                    Set up
                  </Button>
                </div>
              )
            ) : (
              <div className="grid gap-6">
                <p className="flex items-center gap-2 text-sm">
                  <Badge variant="secondary">Enabled</Badge> {data.recovery_codes_remaining} recovery codes left
                </p>
                {newCodes ? (
                  <div className="grid gap-3">
                    <RecoveryCodesView codes={newCodes} />
                    <Button className="w-fit" onClick={() => setNewCodes(null)}>
                      Done
                    </Button>
                  </div>
                ) : (
                  <form
                    className="grid gap-2"
                    onSubmit={(event) => {
                      event.preventDefault()
                      regenerate.mutate()
                    }}
                  >
                    <FormError error={regenerate.error} />
                    <Label htmlFor="regenerate-code">Generate new recovery codes</Label>
                    <div className="flex gap-2">
                      <Input id="regenerate-code" placeholder="6-digit code" inputMode="numeric" maxLength={6} value={regenerateCode} onChange={(event) => setRegenerateCode(event.target.value)} />
                      <Button type="submit" variant="outline" disabled={regenerateCode.length !== 6 || regenerate.isPending}>
                        Regenerate
                      </Button>
                    </div>
                  </form>
                )}
                <form
                  className="grid gap-2"
                  onSubmit={(event) => {
                    event.preventDefault()
                    disable.mutate()
                  }}
                >
                  <FormError error={disable.error} />
                  <Label htmlFor="disable-password">Disable two-factor authentication</Label>
                  <Input id="disable-password" type="password" placeholder="Current password" autoComplete="current-password" value={disablePassword} onChange={(event) => setDisablePassword(event.target.value)} />
                  <div className="flex gap-2">
                    <Input aria-label="Current code" placeholder="6-digit code" inputMode="numeric" maxLength={6} value={disableCode} onChange={(event) => setDisableCode(event.target.value)} />
                    <Button type="submit" variant="destructive" disabled={!disablePassword || disableCode.length !== 6 || disable.isPending}>
                      Disable
                    </Button>
                  </div>
                </form>
              </div>
            )
          }
        </QueryState>
      </CardContent>
    </Card>
  )
}

function SessionsCard() {
  const queryClient = useQueryClient()
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => api.get<SessionInfo[]>("/auth/sessions") })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["sessions"] })
  const revoke = useMutation({ mutationFn: (id: string) => api.delete(`/auth/sessions/${id}`), onSuccess: refresh })
  const revokeOthers = useMutation({ mutationFn: () => api.post("/auth/sessions/revoke-others"), onSuccess: refresh })
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle>Active sessions</CardTitle>
        <CardDescription>Where you are signed in.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <FormError error={revoke.error ?? revokeOthers.error} />
        <QueryState query={sessions}>
          {(rows) => (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Device</TableHead>
                  <TableHead>IP address</TableHead>
                  <TableHead>Last seen</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((session) => (
                  <TableRow key={session.id}>
                    <TableCell className="max-w-72 truncate" title={session.user_agent ?? ""}>
                      {session.user_agent ?? "Unknown"}
                    </TableCell>
                    <TableCell>{session.ip_address ?? "-"}</TableCell>
                    <TableCell>{formatDate(session.last_seen_at)}</TableCell>
                    <TableCell className="text-right">
                      {session.current ? (
                        <Badge variant="secondary">This device</Badge>
                      ) : (
                        <Button variant="ghost" size="sm" onClick={() => revoke.mutate(session.id)}>
                          Sign out
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryState>
        <Button variant="outline" className="w-fit" onClick={() => revokeOthers.mutate()}>
          Sign out all other sessions
        </Button>
      </CardContent>
    </Card>
  )
}

export function SecurityPage() {
  return (
    <>
      <PageHeader title="Security" description="Manage your own password, two-factor authentication and sessions." />
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Password</CardTitle>
            <CardDescription>Changing it signs out your other sessions.</CardDescription>
          </CardHeader>
          <CardContent>
            <PasswordForm onChanged={() => void toast.success("Password changed")} />
          </CardContent>
        </Card>
        <MfaCard />
        <SessionsCard />
      </div>
    </>
  )
}

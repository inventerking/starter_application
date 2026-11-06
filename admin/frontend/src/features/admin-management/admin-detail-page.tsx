import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { useNavigate, useParams } from "react-router"
import { toast } from "sonner"
import { z } from "zod"

import { ActivityTable } from "@/components/activity-table"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { FormError } from "@/components/form-error"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { PermissionOverrides } from "@/components/permission-overrides"
import { QueryState } from "@/components/query-state"
import { RoleAssignments } from "@/components/role-assignments"
import { SecretRevealDialog } from "@/components/secret-reveal-dialog"
import { ActiveBadge, MfaBadge } from "@/components/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/features/authentication/auth-context"
import { adminApi } from "@/features/admin-management/api"
import { formatDate } from "@/lib/format"
import type { RoleSummary } from "@/lib/types"

const schema = z.object({
  email: z.email("Enter a valid email."),
  username: z.string().regex(/^[A-Za-z0-9_.-]{3,64}$/, "Use 3-64 letters, digits, dots, dashes or underscores."),
  full_name: z.string().max(128),
})
type Values = z.infer<typeof schema>

export function AdminDetailPage() {
  const { id = "" } = useParams()
  const { can } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [temporary, setTemporary] = useState<string | null>(null)
  const admin = useQuery({ queryKey: ["admin-accounts", "detail", id], queryFn: () => adminApi.get(id) })
  const mfa = useQuery({ queryKey: ["admin-accounts", "mfa", id], queryFn: () => adminApi.mfa(id), enabled: can("admins.mfa.view_status") })
  const activity = useQuery({ queryKey: ["admin-accounts", "activity", id], queryFn: () => adminApi.activity(id), enabled: can("admins.activity.view") })
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", username: "", full_name: "" } })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin-accounts"] })
  useEffect(() => {
    if (admin.data) form.reset({ email: admin.data.email, username: admin.data.username, full_name: admin.data.full_name ?? "" })
  }, [admin.data, form])
  const save = useMutation({
    mutationFn: (values: Values) => adminApi.update(id, { ...values, full_name: values.full_name || null }),
    onSuccess: () => {
      toast.success("Admin updated")
      return refresh()
    },
  })
  const { errors } = form.formState
  const canUpdate = can("admins.update")

  return (
    <QueryState query={admin}>
      {(data) => (
        <>
          <PageHeader
            title={data.email}
            description={data.is_superuser ? "Super Admin" : "Admin account"}
            actions={
              <>
                <ActiveBadge active={data.is_active} />
                <MfaBadge enabled={data.mfa_enabled} />
              </>
            }
          />
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Account</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4">
                <form className="grid gap-4" onSubmit={form.handleSubmit((values) => save.mutate(values))}>
                  <FormError error={save.error} />
                  <FormField label="Email" disabled={!canUpdate} registration={form.register("email")} error={errors.email} />
                  <FormField label="Username" disabled={!canUpdate} registration={form.register("username")} error={errors.username} />
                  <FormField label="Full name" disabled={!canUpdate} registration={form.register("full_name")} error={errors.full_name} />
                  {canUpdate && (
                    <Button type="submit" className="w-fit" disabled={save.isPending}>
                      Save
                    </Button>
                  )}
                </form>
                <p className="text-muted-foreground text-sm">
                  Created {formatDate(data.created_at)}. Last sign-in: {formatDate(data.last_login_at)}.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Account actions</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                {can("admins.mfa.view_status") && mfa.data && (
                  <p className="text-sm">
                    MFA is {mfa.data.enabled ? "enabled" : "disabled"}, with {mfa.data.recovery_codes_remaining} recovery codes left.
                    {mfa.data.enrollment_required && " Re-enrollment is required."}
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  {data.is_active
                    ? can("admins.deactivate") && (
                        <ConfirmDialog
                          title="Deactivate this Admin?"
                          description="They are signed out everywhere and cannot sign in."
                          confirmLabel="Deactivate"
                          destructive
                          onConfirm={async () => {
                            await adminApi.deactivate(id)
                            await refresh()
                          }}
                          trigger={(open) => (
                            <Button variant="outline" onClick={open}>
                              Deactivate
                            </Button>
                          )}
                        />
                      )
                    : can("admins.activate") && (
                        <Button
                          variant="outline"
                          onClick={async () => {
                            await adminApi.activate(id)
                            await refresh()
                          }}
                        >
                          Activate
                        </Button>
                      )}
                  {can("admins.password.reset") && (
                    <ConfirmDialog
                      title="Issue a temporary password?"
                      description="Their current password stops working and they are signed out everywhere."
                      confirmLabel="Issue"
                      onConfirm={async () => setTemporary((await adminApi.resetPassword(id)).temporary_password)}
                      trigger={(open) => (
                        <Button variant="outline" onClick={open}>
                          Reset password
                        </Button>
                      )}
                    />
                  )}
                  {can("admins.mfa.reset") && (
                    <ConfirmDialog
                      title="Reset two-factor authentication?"
                      description="Their authenticator and recovery codes stop working, and they must enroll again."
                      confirmLabel="Reset MFA"
                      destructive
                      onConfirm={async () => {
                        await adminApi.resetMfa(id)
                        await refresh()
                      }}
                      trigger={(open) => (
                        <Button variant="outline" onClick={open}>
                          Reset MFA
                        </Button>
                      )}
                    />
                  )}
                  {can("admins.sessions.revoke") && (
                    <Button
                      variant="outline"
                      onClick={async () => {
                        const { revoked } = await adminApi.revokeSessions(id)
                        toast.success(`Revoked ${revoked} session(s)`)
                      }}
                    >
                      Sign out everywhere
                    </Button>
                  )}
                  {can("admins.delete") && !data.is_superuser && (
                    <ConfirmDialog
                      title="Delete this Admin?"
                      description="The account can no longer sign in. Its audit history is kept."
                      confirmLabel="Delete"
                      destructive
                      onConfirm={async () => {
                        await adminApi.remove(id)
                        await refresh()
                        navigate("/admins")
                      }}
                      trigger={(open) => (
                        <Button variant="destructive" onClick={open}>
                          Delete
                        </Button>
                      )}
                    />
                  )}
                </div>
              </CardContent>
            </Card>
            <RoleAssignments
              queryKey={`admin-roles-of-${id}`}
              description="Admin roles. These never apply to Client users."
              canManage={can("admins.roles.manage")}
              loadAssigned={() => adminApi.roles(id)}
              loadAvailable={can("admin_roles.view") ? (adminApi.availableRoles as () => Promise<RoleSummary[]>) : null}
              assign={(roleId) => adminApi.assignRole(id, roleId)}
              remove={(roleId) => adminApi.removeRole(id, roleId)}
            />
            <PermissionOverrides
              queryKey={`admin-overrides-of-${id}`}
              description="Admin permissions for this account."
              canManage={can("admins.permissions.manage")}
              loadOverrides={() => adminApi.overrides(id)}
              loadPermissions={can("admin_permissions.view") ? adminApi.registry : null}
              setOverride={(permissionId, effect) => adminApi.setOverride(id, permissionId, effect)}
              removeOverride={(permissionId) => adminApi.removeOverride(id, permissionId)}
            />
            {can("admins.activity.view") && (
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Activity</CardTitle>
                </CardHeader>
                <CardContent>
                  <QueryState query={activity}>{(page) => <ActivityTable entries={page.items} />}</QueryState>
                </CardContent>
              </Card>
            )}
          </div>
          <SecretRevealDialog title="Temporary password" value={temporary} onClose={() => setTemporary(null)} />
        </>
      )}
    </QueryState>
  )
}

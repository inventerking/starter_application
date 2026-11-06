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
import { userApi } from "@/features/user-management/api"
import { formatDate } from "@/lib/format"
import type { RoleSummary } from "@/lib/types"

const schema = z.object({
  email: z.email("Enter a valid email."),
  username: z.string().regex(/^[A-Za-z0-9_.-]{3,64}$/, "Use 3-64 letters, digits, dots, dashes or underscores."),
  full_name: z.string().max(128),
})
type Values = z.infer<typeof schema>

export function UserDetailPage() {
  const { id = "" } = useParams()
  const { can } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [temporary, setTemporary] = useState<string | null>(null)
  const user = useQuery({ queryKey: ["client-users", "detail", id], queryFn: () => userApi.get(id) })
  const mfa = useQuery({ queryKey: ["client-users", "mfa", id], queryFn: () => userApi.mfa(id), enabled: can("users.mfa.view_status") })
  const activity = useQuery({ queryKey: ["client-users", "activity", id], queryFn: () => userApi.activity(id), enabled: can("users.activity.view") })
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", username: "", full_name: "" } })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["client-users"] })
  useEffect(() => {
    if (user.data) form.reset({ email: user.data.email, username: user.data.username, full_name: user.data.full_name ?? "" })
  }, [user.data, form])
  const save = useMutation({
    mutationFn: (values: Values) => userApi.update(id, { ...values, full_name: values.full_name || null }),
    onSuccess: () => {
      toast.success("User updated")
      return refresh()
    },
  })
  const { errors } = form.formState
  const canUpdate = can("users.update")

  return (
    <QueryState query={user}>
      {(data) => (
        <>
          <PageHeader
            title={data.email}
            description="Client user"
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
                {can("users.mfa.view_status") && mfa.data && (
                  <p className="text-sm">
                    MFA is {mfa.data.enabled ? "enabled" : "disabled"}, with {mfa.data.recovery_codes_remaining} recovery codes left.
                    {mfa.data.enrollment_required && " Re-enrollment is required."}
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  {data.is_active
                    ? can("users.deactivate") && (
                        <ConfirmDialog
                          title="Deactivate this user?"
                          description="They are signed out everywhere and cannot sign in."
                          confirmLabel="Deactivate"
                          destructive
                          onConfirm={async () => {
                            await userApi.deactivate(id)
                            await refresh()
                          }}
                          trigger={(open) => (
                            <Button variant="outline" onClick={open}>
                              Deactivate
                            </Button>
                          )}
                        />
                      )
                    : can("users.activate") && (
                        <Button
                          variant="outline"
                          onClick={async () => {
                            await userApi.activate(id)
                            await refresh()
                          }}
                        >
                          Activate
                        </Button>
                      )}
                  {can("users.password.reset") && (
                    <ConfirmDialog
                      title="Issue a temporary password?"
                      description="Their current password stops working and they are signed out everywhere."
                      confirmLabel="Issue"
                      onConfirm={async () => setTemporary((await userApi.resetPassword(id)).temporary_password)}
                      trigger={(open) => (
                        <Button variant="outline" onClick={open}>
                          Reset password
                        </Button>
                      )}
                    />
                  )}
                  {can("users.mfa.reset") && (
                    <ConfirmDialog
                      title="Reset two-factor authentication?"
                      description="Their authenticator and recovery codes stop working, and they must enroll again."
                      confirmLabel="Reset MFA"
                      destructive
                      onConfirm={async () => {
                        await userApi.resetMfa(id)
                        await refresh()
                      }}
                      trigger={(open) => (
                        <Button variant="outline" onClick={open}>
                          Reset MFA
                        </Button>
                      )}
                    />
                  )}
                  {can("users.sessions.revoke") && (
                    <Button
                      variant="outline"
                      onClick={async () => {
                        const { revoked } = await userApi.revokeSessions(id)
                        toast.success(`Revoked ${revoked} session(s)`)
                      }}
                    >
                      Sign out everywhere
                    </Button>
                  )}
                  {can("users.delete") && (
                    <ConfirmDialog
                      title="Delete this user?"
                      description="The account is removed from the application. Its audit history is kept."
                      confirmLabel="Delete"
                      destructive
                      onConfirm={async () => {
                        await userApi.remove(id)
                        await refresh()
                        navigate("/users")
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
              queryKey={`client-user-roles-${id}`}
              description="Client roles. These never apply to Admin accounts."
              canManage={can("users.roles.manage")}
              loadAssigned={() => userApi.roles(id)}
              loadAvailable={can("client_roles.view") ? (userApi.availableRoles as () => Promise<RoleSummary[]>) : null}
              assign={(roleId) => userApi.assignRole(id, roleId)}
              remove={(roleId) => userApi.removeRole(id, roleId)}
            />
            <PermissionOverrides
              queryKey={`client-user-overrides-${id}`}
              description="Client permissions for this user."
              canManage={can("users.permissions.manage")}
              loadOverrides={() => userApi.overrides(id)}
              loadPermissions={can("client_permissions.view") ? userApi.registry : null}
              setOverride={(permissionId, effect) => userApi.setOverride(id, permissionId, effect)}
              removeOverride={(permissionId) => userApi.removeOverride(id, permissionId)}
            />
            {can("users.activity.view") && (
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

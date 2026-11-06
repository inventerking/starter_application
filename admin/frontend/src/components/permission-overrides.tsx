import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { FormError } from "@/components/form-error"
import { NativeSelect } from "@/components/native-select"
import { QueryState } from "@/components/query-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { Permission, PermissionOverride } from "@/lib/types"

interface PermissionOverridesProps {
  queryKey: string
  description: string
  loadOverrides: () => Promise<PermissionOverride[]>
  loadPermissions: (() => Promise<Permission[]>) | null
  setOverride: (permissionId: string, effect: "ALLOW" | "DENY") => Promise<unknown>
  removeOverride: (permissionId: string) => Promise<unknown>
  canManage: boolean
}

export function PermissionOverrides({ queryKey, description, loadOverrides, loadPermissions, setOverride, removeOverride, canManage }: PermissionOverridesProps) {
  const queryClient = useQueryClient()
  const [permissionId, setPermissionId] = useState("")
  const [effect, setEffect] = useState<"ALLOW" | "DENY">("ALLOW")
  const overrides = useQuery({ queryKey: [queryKey, "overrides"], queryFn: loadOverrides })
  const permissions = useQuery({
    queryKey: [queryKey, "registry"],
    queryFn: () => loadPermissions!(),
    enabled: canManage && loadPermissions !== null,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: [queryKey] })
  const save = useMutation({
    mutationFn: () => setOverride(permissionId, effect),
    onSuccess: () => {
      setPermissionId("")
      toast.success("Override saved")
      return refresh()
    },
  })
  const remove = useMutation({
    mutationFn: removeOverride,
    onSuccess: () => {
      toast.success("Override removed")
      return refresh()
    },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Direct permissions</CardTitle>
        <CardDescription>{description} A direct deny always beats a role.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <FormError error={save.error ?? remove.error} />
        <QueryState query={overrides}>
          {(rows) =>
            rows.length === 0 ? (
              <p className="text-muted-foreground text-sm">No direct overrides.</p>
            ) : (
              <ul className="grid gap-2">
                {rows.map((row) => (
                  <li key={row.permission.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className="flex items-center gap-2">
                      <Badge variant={row.effect === "DENY" ? "destructive" : "secondary"}>{row.effect}</Badge>
                      <code>{row.permission.code}</code>
                    </span>
                    {canManage && (
                      <Button variant="ghost" size="sm" onClick={() => remove.mutate(row.permission.id)}>
                        Remove
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )
          }
        </QueryState>
        {canManage && loadPermissions && (
          <div className="flex flex-wrap gap-2">
            <NativeSelect aria-label="Permission" className="min-w-48 flex-1" value={permissionId} onChange={(event) => setPermissionId(event.target.value)}>
              <option value="">Select a permission</option>
              {permissions.data?.map((permission) => (
                <option key={permission.id} value={permission.id}>
                  {permission.code}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect aria-label="Effect" value={effect} onChange={(event) => setEffect(event.target.value as "ALLOW" | "DENY")}>
              <option value="ALLOW">Allow</option>
              <option value="DENY">Deny</option>
            </NativeSelect>
            <Button disabled={!permissionId || save.isPending} onClick={() => save.mutate()}>
              Save
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

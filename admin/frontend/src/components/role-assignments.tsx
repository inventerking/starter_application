import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { XIcon } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { FormError } from "@/components/form-error"
import { NativeSelect } from "@/components/native-select"
import { QueryState } from "@/components/query-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { RoleSummary } from "@/lib/types"

interface RoleAssignmentsProps {
  queryKey: string
  description: string
  loadAssigned: () => Promise<RoleSummary[]>
  /** Null when the operator may not list roles in this domain. */
  loadAvailable: (() => Promise<RoleSummary[]>) | null
  assign: (roleId: string) => Promise<unknown>
  remove: (roleId: string) => Promise<unknown>
  canManage: boolean
}

/** Layout only. Each domain passes its own API calls, so role records can never cross domains. */
export function RoleAssignments({ queryKey, description, loadAssigned, loadAvailable, assign, remove, canManage }: RoleAssignmentsProps) {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState("")
  const assigned = useQuery({ queryKey: [queryKey, "assigned"], queryFn: loadAssigned })
  const available = useQuery({
    queryKey: [queryKey, "available"],
    queryFn: () => loadAvailable!(),
    enabled: canManage && loadAvailable !== null,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: [queryKey] })
  const add = useMutation({
    mutationFn: () => assign(selected),
    onSuccess: () => {
      setSelected("")
      toast.success("Role assigned")
      return refresh()
    },
  })
  const drop = useMutation({
    mutationFn: remove,
    onSuccess: () => {
      toast.success("Role removed")
      return refresh()
    },
  })
  const assignedIds = new Set(assigned.data?.map((role) => role.id))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Roles</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <FormError error={add.error ?? drop.error} />
        <QueryState query={assigned}>
          {(roles) =>
            roles.length === 0 ? (
              <p className="text-muted-foreground text-sm">No roles assigned.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {roles.map((role) => (
                  <Badge key={role.id} variant="secondary" className="gap-1">
                    {role.name}
                    {canManage && (
                      <button aria-label={`Remove ${role.name}`} onClick={() => drop.mutate(role.id)}>
                        <XIcon className="size-3" />
                      </button>
                    )}
                  </Badge>
                ))}
              </div>
            )
          }
        </QueryState>
        {canManage && loadAvailable && (
          <div className="flex gap-2">
            <NativeSelect aria-label="Role to assign" className="flex-1" value={selected} onChange={(event) => setSelected(event.target.value)}>
              <option value="">Select a role</option>
              {available.data
                ?.filter((role) => !assignedIds.has(role.id))
                .map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
            </NativeSelect>
            <Button disabled={!selected || add.isPending} onClick={() => add.mutate()}>
              Assign
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

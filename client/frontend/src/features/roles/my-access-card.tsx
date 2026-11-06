import { useQuery } from "@tanstack/react-query"

import { QueryState } from "@/components/query-state"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import type { RoleSummary } from "@/lib/types"

export function MyAccessCard() {
  const roles = useQuery({ queryKey: ["my-roles"], queryFn: () => api.get<RoleSummary[]>("/roles/me") })
  const permissions = useQuery({ queryKey: ["my-permissions"], queryFn: () => api.get<string[]>("/permissions/me") })
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your access</CardTitle>
        <CardDescription>Assigned by your administrator.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-2">
          <p className="text-sm font-medium">Roles</p>
          <QueryState query={roles}>
            {(rows) =>
              rows.length === 0 ? (
                <p className="text-muted-foreground text-sm">No roles.</p>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {rows.map((role) => (
                    <Badge key={role.id} variant="secondary">
                      {role.name}
                    </Badge>
                  ))}
                </div>
              )
            }
          </QueryState>
        </div>
        <div className="grid gap-2">
          <p className="text-sm font-medium">Permissions</p>
          <QueryState query={permissions}>
            {(rows) =>
              rows.length === 0 ? (
                <p className="text-muted-foreground text-sm">No permissions.</p>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {rows.map((code) => (
                    <Badge key={code} variant="outline">
                      {code}
                    </Badge>
                  ))}
                </div>
              )
            }
          </QueryState>
        </div>
      </CardContent>
    </Card>
  )
}

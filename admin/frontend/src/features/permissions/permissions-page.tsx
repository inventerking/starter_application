import { useQuery } from "@tanstack/react-query"

import { PageHeader } from "@/components/page-header"
import { QueryState } from "@/components/query-state"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAuth } from "@/features/authentication/auth-context"
import { api } from "@/lib/api"
import type { Permission } from "@/lib/types"

function Registry({ title, description, path }: { title: string; description: string; path: string }) {
  const query = useQuery({ queryKey: ["registry", path], queryFn: () => api.get<Permission[]>(path) })
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <QueryState query={query}>
          {(rows) => (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Description</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <code className="text-xs">{row.code}</code>
                    </TableCell>
                    <TableCell className="text-muted-foreground whitespace-normal">{row.description}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryState>
      </CardContent>
    </Card>
  )
}

export function PermissionsPage() {
  const { can } = useAuth()
  return (
    <>
      <PageHeader title="Permissions" description="Defined in code by each application. Assign them through roles or direct overrides." />
      <div className="grid items-start gap-6 xl:grid-cols-2">
        {can("admin_permissions.view") && <Registry title="Admin permissions" description="What administrators may do." path="/admin-permissions" />}
        {can("client_permissions.view") && <Registry title="Client permissions" description="What Client users may do." path="/client-permissions" />}
      </div>
    </>
  )
}

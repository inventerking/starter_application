import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { PlusIcon, SearchIcon } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link } from "react-router"
import { z } from "zod"

import { FormError } from "@/components/form-error"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { Pagination } from "@/components/pagination"
import { QueryState } from "@/components/query-state"
import { SecretRevealDialog } from "@/components/secret-reveal-dialog"
import { ActiveBadge, MfaBadge } from "@/components/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAuth } from "@/features/authentication/auth-context"
import { adminApi } from "@/features/admin-management/api"
import { formatDate } from "@/lib/format"

const schema = z.object({
  email: z.email("Enter a valid email."),
  username: z.string().regex(/^[A-Za-z0-9_.-]{3,64}$/, "Use 3-64 letters, digits, dots, dashes or underscores."),
  full_name: z.string().max(128),
})
type Values = z.infer<typeof schema>

export function AdminsListPage() {
  const { can } = useAuth()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [creating, setCreating] = useState(false)
  const [temporary, setTemporary] = useState<string | null>(null)
  const admins = useQuery({ queryKey: ["admin-accounts", page, search], queryFn: () => adminApi.list(page, search) })
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", username: "", full_name: "" } })
  const create = useMutation({
    mutationFn: (values: Values) => adminApi.create({ ...values, full_name: values.full_name || null }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-accounts"] })
      setCreating(false)
      form.reset()
      setTemporary(created.temporary_password)
    },
  })
  const { errors } = form.formState

  return (
    <>
      <PageHeader
        title="Admin Management"
        description="Ordinary application admins. These accounts cannot sign in to the Admin application."
        actions={
          can("admins.create") && (
            <Button onClick={() => setCreating(true)}>
              <PlusIcon /> New Admin
            </Button>
          )
        }
      />
      <Card>
        <CardContent className="grid gap-4">
          <div className="relative max-w-sm">
            <SearchIcon className="text-muted-foreground absolute top-2 left-2 size-4" />
            <Input
              aria-label="Search Admins"
              className="pl-8"
              placeholder="Search by name, email or username"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
            />
          </div>
          <QueryState query={admins}>
            {(data) => (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Email</TableHead>
                      <TableHead>Username</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last sign-in</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.map((admin) => (
                      <TableRow key={admin.id}>
                        <TableCell>
                          <Link className="font-medium hover:underline" to={`/admins/${admin.id}`}>
                            {admin.email}
                          </Link>
                        </TableCell>
                        <TableCell>{admin.username}</TableCell>
                        <TableCell className="flex gap-1">
                          {admin.is_superuser && <Badge>Super Admin</Badge>}
                          <ActiveBadge active={admin.is_active} />
                          <MfaBadge enabled={admin.mfa_enabled} />
                        </TableCell>
                        <TableCell className="text-muted-foreground">{formatDate(admin.last_login_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
              </>
            )}
          </QueryState>
        </CardContent>
      </Card>
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Admin</DialogTitle>
            <DialogDescription>They start with no roles or permissions and a temporary password.</DialogDescription>
          </DialogHeader>
          <form className="grid gap-4" onSubmit={form.handleSubmit((values) => create.mutate(values))}>
            <FormError error={create.error} />
            <FormField label="Email" type="email" registration={form.register("email")} error={errors.email} />
            <FormField label="Username" registration={form.register("username")} error={errors.username} />
            <FormField label="Full name" registration={form.register("full_name")} error={errors.full_name} />
            <DialogFooter>
              <Button type="submit" disabled={create.isPending}>
                Create Admin
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <SecretRevealDialog title="Temporary password" value={temporary} onClose={() => setTemporary(null)} />
    </>
  )
}

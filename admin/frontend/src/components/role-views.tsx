import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { PlusIcon, ShieldIcon } from "lucide-react"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { Link, useNavigate, useParams } from "react-router"
import { toast } from "sonner"
import { z } from "zod"

import { ConfirmDialog } from "@/components/confirm-dialog"
import { FormError } from "@/components/form-error"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { QueryState } from "@/components/query-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { Permission, Role, RoleSummary } from "@/lib/types"

/** Everything that differs between the two separate role systems. */
export interface RoleDomain {
  key: string
  title: string
  description: string
  basePath: string
  supportsDefault: boolean
  can: { create: boolean; update: boolean; delete: boolean; viewPermissions: boolean }
  list: () => Promise<RoleSummary[]>
  get: (id: string) => Promise<Role>
  create: (body: { name: string; description: string | null; permission_ids: string[] }) => Promise<Role>
  update: (id: string, body: { name?: string; description?: string | null; is_default?: boolean }) => Promise<Role>
  setPermissions: (id: string, permissionIds: string[]) => Promise<Role>
  remove: (id: string) => Promise<void>
  listPermissions: () => Promise<Permission[]>
}

const roleSchema = z.object({
  name: z.string().min(2, "Enter at least 2 characters.").max(64),
  description: z.string().max(1000),
})
type RoleForm = z.infer<typeof roleSchema>

export function RoleListView({ domain }: { domain: RoleDomain }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const roles = useQuery({ queryKey: [domain.key], queryFn: domain.list })
  const form = useForm<RoleForm>({ resolver: zodResolver(roleSchema), defaultValues: { name: "", description: "" } })
  const create = useMutation({
    mutationFn: (values: RoleForm) => domain.create({ name: values.name, description: values.description || null, permission_ids: [] }),
    onSuccess: async (role) => {
      await queryClient.invalidateQueries({ queryKey: [domain.key] })
      setCreating(false)
      form.reset()
      toast.success("Role created")
      navigate(`${domain.basePath}/${role.id}`)
    },
  })

  return (
    <>
      <PageHeader
        title={domain.title}
        description={domain.description}
        actions={
          domain.can.create && (
            <Button onClick={() => setCreating(true)}>
              <PlusIcon /> New role
            </Button>
          )
        }
      />
      <Card>
        <CardContent>
          <QueryState query={roles}>
            {(rows) =>
              rows.length === 0 ? (
                <p className="text-muted-foreground text-sm">No roles yet.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Type</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((role) => (
                      <TableRow key={role.id}>
                        <TableCell>
                          <Link className="font-medium hover:underline" to={`${domain.basePath}/${role.id}`}>
                            {role.name}
                          </Link>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{role.description ?? "-"}</TableCell>
                        <TableCell className="flex gap-1">
                          {role.is_system && <Badge variant="outline">System</Badge>}
                          {role.is_default && <Badge variant="secondary">Default</Badge>}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )
            }
          </QueryState>
        </CardContent>
      </Card>
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New role</DialogTitle>
          </DialogHeader>
          <form className="grid gap-4" onSubmit={form.handleSubmit((values) => create.mutate(values))}>
            <FormError error={create.error} />
            <FormField label="Name" registration={form.register("name")} error={form.formState.errors.name} />
            <FormField label="Description" registration={form.register("description")} error={form.formState.errors.description} />
            <DialogFooter>
              <Button type="submit" disabled={create.isPending}>
                Create
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}

export function RoleDetailView({ domain }: { domain: RoleDomain }) {
  const { id = "" } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const role = useQuery({ queryKey: [domain.key, id], queryFn: () => domain.get(id) })
  const permissions = useQuery({ queryKey: [domain.key, "registry"], queryFn: domain.listPermissions, enabled: domain.can.viewPermissions })
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const form = useForm<RoleForm>({ resolver: zodResolver(roleSchema), defaultValues: { name: "", description: "" } })

  useEffect(() => {
    if (role.data) {
      setSelected(new Set(role.data.permissions.map((permission) => permission.id)))
      form.reset({ name: role.data.name, description: role.data.description ?? "" })
    }
  }, [role.data, form])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: [domain.key] })
  const saveDetails = useMutation({
    mutationFn: (values: RoleForm) => domain.update(id, { name: values.name, description: values.description || null }),
    onSuccess: () => {
      toast.success("Role updated")
      return invalidate()
    },
  })
  const savePermissions = useMutation({
    mutationFn: () => domain.setPermissions(id, [...selected]),
    onSuccess: () => {
      toast.success("Permissions updated")
      return invalidate()
    },
  })
  const toggleDefault = useMutation({
    mutationFn: (value: boolean) => domain.update(id, { is_default: value }),
    onSuccess: invalidate,
  })
  const toggle = (permissionId: string, checked: boolean) => {
    const next = new Set(selected)
    if (checked) next.add(permissionId)
    else next.delete(permissionId)
    setSelected(next)
  }

  return (
    <QueryState query={role}>
      {(data) => (
        <>
          <PageHeader
            title={data.name}
            description={domain.title}
            actions={
              domain.can.delete && (
                <ConfirmDialog
                  title="Delete this role?"
                  description="Everyone holding it loses the access it grants. This cannot be undone."
                  confirmLabel="Delete"
                  destructive
                  onConfirm={async () => {
                    await domain.remove(id)
                    await invalidate()
                    toast.success("Role deleted")
                    navigate(domain.basePath)
                  }}
                  trigger={(open) => (
                    <Button variant="destructive" onClick={open}>
                      Delete
                    </Button>
                  )}
                />
              )
            }
          />
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Details</CardTitle>
              </CardHeader>
              <CardContent>
                <form className="grid gap-4" onSubmit={form.handleSubmit((values) => saveDetails.mutate(values))}>
                  <FormError error={saveDetails.error ?? toggleDefault.error} />
                  <FormField label="Name" disabled={!domain.can.update} registration={form.register("name")} error={form.formState.errors.name} />
                  <FormField label="Description" disabled={!domain.can.update} registration={form.register("description")} error={form.formState.errors.description} />
                  {domain.supportsDefault && (
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="is-default"
                        disabled={!domain.can.update}
                        checked={Boolean(data.is_default)}
                        onCheckedChange={(value) => toggleDefault.mutate(value === true)}
                      />
                      <Label htmlFor="is-default">Give this role to new users by default</Label>
                    </div>
                  )}
                  {domain.can.update && (
                    <Button type="submit" className="w-fit" disabled={saveDetails.isPending}>
                      Save
                    </Button>
                  )}
                </form>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldIcon className="size-4" /> Permissions
                </CardTitle>
                <CardDescription>What everyone holding this role is allowed to do.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3">
                <FormError error={savePermissions.error} />
                {domain.can.update && domain.can.viewPermissions ? (
                  <QueryState query={permissions}>
                    {(rows) => (
                      <div className="grid max-h-96 gap-2 overflow-y-auto">
                        {rows.map((permission) => (
                          <div key={permission.id} className="flex items-start gap-2">
                            <Checkbox
                              id={permission.id}
                              checked={selected.has(permission.id)}
                              onCheckedChange={(value) => toggle(permission.id, value === true)}
                            />
                            <Label htmlFor={permission.id} className="grid gap-0.5 font-normal">
                              <code className="text-xs">{permission.code}</code>
                              <span className="text-muted-foreground text-xs">{permission.description}</span>
                            </Label>
                          </div>
                        ))}
                      </div>
                    )}
                  </QueryState>
                ) : data.permissions.length === 0 ? (
                  <p className="text-muted-foreground text-sm">No permissions.</p>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {data.permissions.map((permission) => (
                      <Badge key={permission.id} variant="secondary">
                        {permission.code}
                      </Badge>
                    ))}
                  </div>
                )}
                {domain.can.update && domain.can.viewPermissions && (
                  <Button className="w-fit" disabled={savePermissions.isPending} onClick={() => savePermissions.mutate()}>
                    Save permissions
                  </Button>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </QueryState>
  )
}

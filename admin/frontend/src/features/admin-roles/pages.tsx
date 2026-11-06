import { RoleDetailView, RoleListView, type RoleDomain } from "@/components/role-views"
import { useAuth } from "@/features/authentication/auth-context"
import { api } from "@/lib/api"
import type { Permission, Role, RoleSummary } from "@/lib/types"

function useDomain(): RoleDomain {
  const { can } = useAuth()
  return {
    key: "admin-roles",
    title: "Admin roles",
    description: "Roles for administrative accounts. They have no effect on Client users.",
    basePath: "/admin-roles",
    supportsDefault: false,
    can: {
      create: can("admin_roles.create"),
      update: can("admin_roles.update"),
      delete: can("admin_roles.delete"),
      viewPermissions: can("admin_permissions.view"),
    },
    list: () => api.get<RoleSummary[]>("/admin-roles"),
    get: (id) => api.get<Role>(`/admin-roles/${id}`),
    create: (body) => api.post<Role>("/admin-roles", body),
    update: (id, body) => api.patch<Role>(`/admin-roles/${id}`, body),
    setPermissions: (id, permission_ids) => api.put<Role>(`/admin-roles/${id}/permissions`, { permission_ids }),
    remove: (id) => api.delete(`/admin-roles/${id}`),
    listPermissions: () => api.get<Permission[]>("/admin-permissions"),
  }
}

export const AdminRolesPage = () => <RoleListView domain={useDomain()} />
export const AdminRoleDetailPage = () => <RoleDetailView domain={useDomain()} />

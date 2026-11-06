import { RoleDetailView, RoleListView, type RoleDomain } from "@/components/role-views"
import { useAuth } from "@/features/authentication/auth-context"
import { api } from "@/lib/api"
import type { Permission, Role, RoleSummary } from "@/lib/types"

function useDomain(): RoleDomain {
  const { can } = useAuth()
  return {
    key: "client-roles",
    title: "Client roles",
    description: "Roles for ordinary application users. They have no effect on Admin accounts.",
    basePath: "/client-roles",
    supportsDefault: true,
    can: {
      create: can("client_roles.create"),
      update: can("client_roles.update"),
      delete: can("client_roles.delete"),
      viewPermissions: can("client_permissions.view"),
    },
    list: () => api.get<RoleSummary[]>("/client-roles"),
    get: (id) => api.get<Role>(`/client-roles/${id}`),
    create: (body) => api.post<Role>("/client-roles", body),
    update: (id, body) => api.patch<Role>(`/client-roles/${id}`, body),
    setPermissions: (id, permission_ids) => api.put<Role>(`/client-roles/${id}/permissions`, { permission_ids }),
    remove: (id) => api.delete(`/client-roles/${id}`),
    listPermissions: () => api.get<Permission[]>("/client-permissions"),
  }
}

export const ClientRolesPage = () => <RoleListView domain={useDomain()} />
export const ClientRoleDetailPage = () => <RoleDetailView domain={useDomain()} />

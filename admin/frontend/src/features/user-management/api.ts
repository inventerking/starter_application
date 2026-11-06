import { api } from "@/lib/api"
import type { ActivityEntry, ClientUser, ManagedMfaStatus, Page, Permission, PermissionOverride, RoleSummary } from "@/lib/types"

export type CreatedClientUser = ClientUser & { temporary_password: string }

export const userApi = {
  list: (page: number, search: string) => api.get<Page<ClientUser>>("/users", { page, search }),
  get: (id: string) => api.get<ClientUser>(`/users/${id}`),
  create: (body: { email: string; username: string; full_name: string | null }) => api.post<CreatedClientUser>("/users", body),
  update: (id: string, body: Partial<ClientUser>) => api.patch<ClientUser>(`/users/${id}`, body),
  remove: (id: string) => api.delete(`/users/${id}`),
  activate: (id: string) => api.post<ClientUser>(`/users/${id}/activate`),
  deactivate: (id: string) => api.post<ClientUser>(`/users/${id}/deactivate`),
  roles: (id: string) => api.get<RoleSummary[]>(`/users/${id}/roles`),
  assignRole: (id: string, roleId: string) => api.post(`/users/${id}/roles`, { role_id: roleId }),
  removeRole: (id: string, roleId: string) => api.delete(`/users/${id}/roles/${roleId}`),
  overrides: (id: string) => api.get<PermissionOverride[]>(`/users/${id}/permissions`),
  setOverride: (id: string, permissionId: string, effect: string) => api.put(`/users/${id}/permissions/${permissionId}`, { effect }),
  removeOverride: (id: string, permissionId: string) => api.delete(`/users/${id}/permissions/${permissionId}`),
  mfa: (id: string) => api.get<ManagedMfaStatus>(`/users/${id}/mfa`),
  resetMfa: (id: string) => api.post(`/users/${id}/mfa/reset`),
  resetPassword: (id: string) => api.post<{ temporary_password: string }>(`/users/${id}/password/reset`),
  revokeSessions: (id: string) => api.post<{ revoked: number }>(`/users/${id}/sessions/revoke`),
  activity: (id: string) => api.get<Page<ActivityEntry>>(`/users/${id}/activity`),
  availableRoles: () => api.get<RoleSummary[]>("/client-roles"),
  registry: () => api.get<Permission[]>("/client-permissions"),
}

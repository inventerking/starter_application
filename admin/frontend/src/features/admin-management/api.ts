import { api } from "@/lib/api"
import type { ActivityEntry, AdminAccount, ManagedMfaStatus, Page, Permission, PermissionOverride, RoleSummary } from "@/lib/types"

export type CreatedAdmin = AdminAccount & { temporary_password: string }

export const adminApi = {
  list: (page: number, search: string) => api.get<Page<AdminAccount>>("/admins", { page, search }),
  get: (id: string) => api.get<AdminAccount>(`/admins/${id}`),
  create: (body: { email: string; username: string; full_name: string | null }) => api.post<CreatedAdmin>("/admins", body),
  update: (id: string, body: Partial<AdminAccount>) => api.patch<AdminAccount>(`/admins/${id}`, body),
  remove: (id: string) => api.delete(`/admins/${id}`),
  activate: (id: string) => api.post<AdminAccount>(`/admins/${id}/activate`),
  deactivate: (id: string) => api.post<AdminAccount>(`/admins/${id}/deactivate`),
  roles: (id: string) => api.get<RoleSummary[]>(`/admins/${id}/roles`),
  assignRole: (id: string, roleId: string) => api.post(`/admins/${id}/roles`, { role_id: roleId }),
  removeRole: (id: string, roleId: string) => api.delete(`/admins/${id}/roles/${roleId}`),
  overrides: (id: string) => api.get<PermissionOverride[]>(`/admins/${id}/permissions`),
  setOverride: (id: string, permissionId: string, effect: string) => api.put(`/admins/${id}/permissions/${permissionId}`, { effect }),
  removeOverride: (id: string, permissionId: string) => api.delete(`/admins/${id}/permissions/${permissionId}`),
  mfa: (id: string) => api.get<ManagedMfaStatus>(`/admins/${id}/mfa`),
  resetMfa: (id: string) => api.post(`/admins/${id}/mfa/reset`),
  resetPassword: (id: string) => api.post<{ temporary_password: string }>(`/admins/${id}/password/reset`),
  revokeSessions: (id: string) => api.post<{ revoked: number }>(`/admins/${id}/sessions/revoke`),
  activity: (id: string) => api.get<Page<ActivityEntry>>(`/admins/${id}/activity`),
  availableRoles: () => api.get<RoleSummary[]>("/admin-roles"),
  registry: () => api.get<Permission[]>("/admin-permissions"),
}

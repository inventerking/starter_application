export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface AuthResponse {
  status: "authenticated" | "mfa_required" | "mfa_enrollment_required"
  access_token: string | null
  expires_in: number | null
  challenge_token: string | null
  challenge_expires_in: number | null
}

export interface CurrentUser {
  id: string
  email: string
  username: string
  full_name: string | null
  is_superuser: boolean
  mfa_enabled: boolean
  must_change_password: boolean
  mfa_enrollment_required: boolean
  session_scope: string
  permissions: string[]
}

export interface Permission {
  id: string
  resource: string
  action: string
  code: string
  description: string
}

export interface PermissionOverride {
  permission: Permission
  effect: "ALLOW" | "DENY"
  reason: string | null
  created_at: string
}

export interface RoleSummary {
  id: string
  name: string
  description: string | null
  is_system: boolean
  is_default?: boolean
  created_at: string
}

export interface Role extends RoleSummary {
  permissions: Permission[]
}

export interface AccountBase {
  id: string
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  mfa_enabled: boolean
  must_change_password: boolean
  last_login_at: string | null
  created_at: string
}

export interface AdminAccount extends AccountBase {
  is_superuser: boolean
}

export type ClientUser = AccountBase

export interface ManagedMfaStatus {
  enabled: boolean
  enrollment_required: boolean
  confirmed_at: string | null
  recovery_codes_remaining: number
}

export interface ActivityEntry {
  id: string
  action: string
  actor_type: string
  actor_id?: string | null
  target_type?: string | null
  target_id?: string | null
  ip_address: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface SessionInfo {
  id: string
  ip_address: string | null
  user_agent: string | null
  created_at: string
  last_seen_at: string | null
  expires_at: string
  current: boolean
}

export interface MfaSetup {
  secret: string
  provisioning_uri: string
  qr_code: string
  issuer: string
  account: string
}

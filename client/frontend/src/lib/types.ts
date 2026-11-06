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
  mfa_enabled: boolean
  must_change_password: boolean
  mfa_enrollment_required: boolean
  session_scope: string
  permissions: string[]
}

export interface RoleSummary {
  id: string
  name: string
  description: string | null
}

export interface Profile {
  email: string
  username: string
  full_name: string | null
  created_at: string
  last_login_at: string | null
}

export interface ActivityEntry {
  action: string
  actor_type: string
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

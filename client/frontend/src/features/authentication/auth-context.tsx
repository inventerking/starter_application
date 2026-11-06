import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { api, refreshSession, setAccessToken, setSessionExpiredHandler } from "@/lib/api"
import type { AuthResponse, CurrentUser } from "@/lib/types"

interface AuthState {
  status: "loading" | "anonymous" | "authenticated"
  user: CurrentUser | null
  /** For showing or hiding UI only. The backend enforces every permission. */
  can: (permission: string) => boolean
  login: (identifier: string, password: string) => Promise<AuthResponse>
  verifyMfa: (body: { challenge_token: string; code?: string; recovery_code?: string }) => Promise<void>
  reloadUser: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<AuthState["status"]>("loading")
  const [user, setUser] = useState<CurrentUser | null>(null)

  const clear = useCallback(() => {
    setAccessToken(null)
    setUser(null)
    setStatus("anonymous")
    queryClient.clear()
  }, [queryClient])

  const reloadUser = useCallback(async () => {
    setUser(await api.get<CurrentUser>("/auth/me"))
    setStatus("authenticated")
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(clear)
    refreshSession()
      .then((session) => (session ? reloadUser() : clear()))
      .catch(clear)
  }, [clear, reloadUser])

  const value = useMemo<AuthState>(
    () => ({
      status,
      user,
      can: (permission) => Boolean(user?.permissions.includes(permission)),
      reloadUser,
      login: async (identifier, password) => {
        const result = await api.post<AuthResponse>("/auth/login", { identifier, password })
        if (result.access_token) {
          setAccessToken(result.access_token)
          await reloadUser()
        }
        return result
      },
      verifyMfa: async (body) => {
        const result = await api.post<AuthResponse>("/auth/mfa/verify-login", body)
        setAccessToken(result.access_token)
        await reloadUser()
      },
      logout: async () => {
        try {
          await api.post("/auth/logout")
        } finally {
          clear()
        }
      },
    }),
    [status, user, reloadUser, clear],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used inside AuthProvider")
  return context
}

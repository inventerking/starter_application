import { LockIcon, LogOutIcon, UserIcon } from "lucide-react"
import { NavLink, Outlet } from "react-router"

import { Button } from "@/components/ui/button"
import { useAuth } from "@/features/authentication/auth-context"
import { cn } from "@/lib/utils"

const NAV = [
  { to: "/", label: "Profile", icon: UserIcon },
  { to: "/security", label: "Security", icon: LockIcon },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  return (
    <div className="min-h-svh">
      <header className="flex flex-wrap items-center gap-4 border-b px-6 py-3">
        <span className="font-semibold">Starter Application</span>
        <nav aria-label="Main" className="flex flex-1 gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn("hover:bg-accent flex items-center gap-2 rounded-md px-2 py-1.5 text-sm", isActive && "bg-accent font-medium")
              }
            >
              <item.icon className="size-4" /> {item.label}
            </NavLink>
          ))}
        </nav>
        <span className="text-muted-foreground text-sm">{user?.email}</span>
        <Button variant="outline" size="sm" onClick={() => logout()}>
          <LogOutIcon /> Sign out
        </Button>
      </header>
      <main className="mx-auto max-w-5xl p-6">
        <Outlet />
      </main>
    </div>
  )
}

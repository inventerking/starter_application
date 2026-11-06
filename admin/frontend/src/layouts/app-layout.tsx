import {
  ActivityIcon,
  KeyRoundIcon,
  LayoutDashboardIcon,
  LockIcon,
  LogOutIcon,
  ShieldCheckIcon,
  ShieldIcon,
  UserCogIcon,
  UsersIcon,
  type LucideIcon,
} from "lucide-react"
import { NavLink, Outlet } from "react-router"

import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useAuth } from "@/features/authentication/auth-context"
import { cn } from "@/lib/utils"

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  anyOf?: string[]
}

const SECTIONS: { title: string; items: NavItem[] }[] = [
  { title: "Overview", items: [{ to: "/", label: "Dashboard", icon: LayoutDashboardIcon }] },
  {
    title: "User Management",
    items: [
      { to: "/users", label: "Users", icon: UsersIcon, anyOf: ["users.view"] },
      { to: "/client-roles", label: "Client roles", icon: ShieldIcon, anyOf: ["client_roles.view"] },
    ],
  },
  {
    title: "Admin Management",
    items: [
      { to: "/admins", label: "Admins", icon: UserCogIcon, anyOf: ["admins.view"] },
      { to: "/admin-roles", label: "Admin roles", icon: ShieldCheckIcon, anyOf: ["admin_roles.view"] },
    ],
  },
  {
    title: "System",
    items: [
      { to: "/permissions", label: "Permissions", icon: KeyRoundIcon, anyOf: ["admin_permissions.view", "client_permissions.view"] },
      { to: "/audit", label: "Audit log", icon: ActivityIcon, anyOf: ["audit.view"] },
    ],
  },
  { title: "Account", items: [{ to: "/security", label: "Security", icon: LockIcon }] },
]

export function AppLayout() {
  const { user, can, logout } = useAuth()
  return (
    <div className="flex min-h-svh">
      <aside className="bg-sidebar text-sidebar-foreground flex w-60 shrink-0 flex-col border-r">
        <div className="p-4 font-semibold">Starter Admin</div>
        <Separator />
        <nav aria-label="Main" className="flex-1 space-y-4 overflow-y-auto p-3">
          {SECTIONS.map((section) => {
            const visible = section.items.filter((item) => !item.anyOf || item.anyOf.some(can))
            if (visible.length === 0) return null
            return (
              <div key={section.title}>
                <p className="text-muted-foreground mb-1 px-2 text-xs font-medium">{section.title}</p>
                {visible.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      cn(
                        "hover:bg-sidebar-accent flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
                        isActive && "bg-sidebar-accent font-medium",
                      )
                    }
                  >
                    <item.icon className="size-4" /> {item.label}
                  </NavLink>
                ))}
              </div>
            )
          })}
        </nav>
        <Separator />
        <div className="grid gap-2 p-3">
          <div className="truncate text-sm" title={user?.email}>
            {user?.email}
          </div>
          <Button variant="outline" size="sm" onClick={() => logout()}>
            <LogOutIcon /> Sign out
          </Button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6">
        <Outlet />
      </main>
    </div>
  )
}

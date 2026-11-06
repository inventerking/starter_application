import { useQuery } from "@tanstack/react-query"
import { ShieldCheckIcon, UsersIcon } from "lucide-react"
import type { ReactNode } from "react"

import { ActivityTable } from "@/components/activity-table"
import { PageHeader } from "@/components/page-header"
import { QueryState } from "@/components/query-state"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/features/authentication/auth-context"
import { api } from "@/lib/api"
import type { ActivityEntry } from "@/lib/types"

interface Summary {
  environment: string
  version: string
  admin_count: number | null
  user_count: number | null
  recent_activity: ActivityEntry[] | null
}

function Stat({ label, value, icon }: { label: string; value: ReactNode; icon?: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription className="flex items-center gap-2">
          {icon} {label}
        </CardDescription>
        <CardTitle className="text-2xl">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const summary = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<Summary>("/dashboard/summary") })
  return (
    <>
      <PageHeader title="Dashboard" description={`Signed in as ${user?.email}`} />
      <QueryState query={summary}>
        {(data) => (
          <div className="grid gap-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {data.user_count !== null && <Stat label="Client users" value={data.user_count} icon={<UsersIcon className="size-4" />} />}
              {data.admin_count !== null && <Stat label="Admins" value={data.admin_count} icon={<ShieldCheckIcon className="size-4" />} />}
              <Stat label="Environment" value={data.environment} />
              <Stat label="Version" value={data.version} />
            </div>
            {data.recent_activity !== null && (
              <Card>
                <CardHeader>
                  <CardTitle>Recent administrative activity</CardTitle>
                </CardHeader>
                <CardContent>
                  <ActivityTable entries={data.recent_activity} />
                </CardContent>
              </Card>
            )}
            {data.user_count === null && data.admin_count === null && (
              <p className="text-muted-foreground text-sm">Your account has no management permissions yet. Ask a Super Admin for access.</p>
            )}
          </div>
        )}
      </QueryState>
    </>
  )
}

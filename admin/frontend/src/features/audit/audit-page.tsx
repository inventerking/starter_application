import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { ActivityTable } from "@/components/activity-table"
import { PageHeader } from "@/components/page-header"
import { Pagination } from "@/components/pagination"
import { QueryState } from "@/components/query-state"
import { Card, CardContent } from "@/components/ui/card"
import { api } from "@/lib/api"
import type { ActivityEntry, Page } from "@/lib/types"

export function AuditPage() {
  const [page, setPage] = useState(1)
  const logs = useQuery({ queryKey: ["audit", page], queryFn: () => api.get<Page<ActivityEntry>>("/audit-logs", { page }) })
  return (
    <>
      <PageHeader title="Audit log" description="Administrative activity. Entries cannot be changed." />
      <Card>
        <CardContent>
          <QueryState query={logs}>
            {(data) => (
              <>
                <ActivityTable entries={data.items} />
                <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
              </>
            )}
          </QueryState>
        </CardContent>
      </Card>
    </>
  )
}

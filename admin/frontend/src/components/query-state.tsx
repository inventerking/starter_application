import type { UseQueryResult } from "@tanstack/react-query"
import type { ReactNode } from "react"

import { FormError } from "@/components/form-error"
import { Skeleton } from "@/components/ui/skeleton"

export function QueryState<T>({ query, children }: { query: UseQueryResult<T>; children: (data: T) => ReactNode }) {
  if (query.isPending) {
    return (
      <div className="grid gap-2" aria-label="Loading">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-2/3" />
      </div>
    )
  }
  if (query.isError) return <FormError error={query.error} />
  return <>{children(query.data as T)}</>
}

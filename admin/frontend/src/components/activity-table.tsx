import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatDate } from "@/lib/format"
import type { ActivityEntry } from "@/lib/types"

export function ActivityTable({ entries }: { entries: ActivityEntry[] }) {
  if (entries.length === 0) return <p className="text-muted-foreground text-sm">No activity recorded.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Action</TableHead>
          <TableHead>Actor</TableHead>
          <TableHead>IP address</TableHead>
          <TableHead>When</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => (
          <TableRow key={entry.id}>
            <TableCell>
              <Badge variant="outline">{entry.action}</Badge>
            </TableCell>
            <TableCell className="text-muted-foreground">{entry.actor_type}</TableCell>
            <TableCell className="text-muted-foreground">{entry.ip_address ?? "-"}</TableCell>
            <TableCell className="text-muted-foreground">{formatDate(entry.created_at)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

import { Badge } from "@/components/ui/badge"

export function ActiveBadge({ active }: { active: boolean }) {
  return <Badge variant={active ? "secondary" : "destructive"}>{active ? "Active" : "Inactive"}</Badge>
}

export function MfaBadge({ enabled }: { enabled: boolean }) {
  return <Badge variant={enabled ? "secondary" : "outline"}>{enabled ? "MFA on" : "MFA off"}</Badge>
}

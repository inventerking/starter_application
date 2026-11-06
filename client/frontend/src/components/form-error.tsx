import { AlertCircleIcon } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { errorMessage } from "@/lib/api"

export function FormError({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <Alert variant="destructive">
      <AlertCircleIcon />
      <AlertDescription>{errorMessage(error)}</AlertDescription>
    </Alert>
  )
}

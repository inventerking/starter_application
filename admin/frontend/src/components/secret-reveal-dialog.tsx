import { CopyIcon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

/** Shows a one-time value such as a temporary password. It cannot be retrieved again. */
export function SecretRevealDialog({ title, value, onClose }: { title: string; value: string | null; onClose: () => void }) {
  return (
    <Dialog open={value !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            This is shown only once. Share it through a secure channel. It must be changed at the next sign-in.
          </DialogDescription>
        </DialogHeader>
        <code className="bg-muted rounded-md p-3 text-sm break-all">{value}</code>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={async () => {
              await navigator.clipboard.writeText(value ?? "")
              toast.success("Copied")
            }}
          >
            <CopyIcon /> Copy
          </Button>
          <Button onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

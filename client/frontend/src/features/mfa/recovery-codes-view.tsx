import { CopyIcon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"

export function RecoveryCodesView({ codes }: { codes: string[] }) {
  return (
    <div className="grid gap-3">
      <p className="text-sm">
        Save these codes somewhere safe. Each works once if you lose your authenticator. <strong>They will not be shown again.</strong>
      </p>
      <ul className="bg-muted grid grid-cols-2 gap-1 rounded-md p-3 font-mono text-sm">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <Button
        variant="outline"
        className="w-fit"
        onClick={async () => {
          await navigator.clipboard.writeText(codes.join("\n"))
          toast.success("Copied")
        }}
      >
        <CopyIcon /> Copy codes
      </Button>
    </div>
  )
}

import type { ComponentProps } from "react"
import type { FieldError, UseFormRegisterReturn } from "react-hook-form"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface FormFieldProps extends Omit<ComponentProps<typeof Input>, "name"> {
  label: string
  registration: UseFormRegisterReturn
  error?: FieldError
  hint?: string
}

export function FormField({ label, registration, error, hint, id, ...props }: FormFieldProps) {
  const fieldId = id ?? registration.name
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={fieldId}>{label}</Label>
      <Input id={fieldId} aria-invalid={Boolean(error)} {...registration} {...props} />
      {hint && !error && <p className="text-muted-foreground text-xs">{hint}</p>}
      {error && <p className="text-destructive text-xs">{error.message}</p>}
    </div>
  )
}

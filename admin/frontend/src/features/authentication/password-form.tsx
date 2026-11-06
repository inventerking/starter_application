import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { FormError } from "@/components/form-error"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"

const schema = z
  .object({
    current_password: z.string().min(1, "Enter your current password."),
    new_password: z.string().min(12, "Use at least 12 characters.").max(128),
    confirm: z.string(),
  })
  .refine((values) => values.new_password === values.confirm, { path: ["confirm"], message: "The passwords do not match." })
type Values = z.infer<typeof schema>

export function PasswordForm({ onChanged }: { onChanged: () => Promise<void> | void }) {
  const [error, setError] = useState<unknown>(null)
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  })
  const submit = async ({ current_password, new_password }: Values) => {
    setError(null)
    try {
      await api.post("/auth/password/change", { current_password, new_password })
      form.reset()
      await onChanged()
    } catch (caught) {
      setError(caught)
    }
  }
  const { errors } = form.formState
  return (
    <form className="grid gap-4" onSubmit={form.handleSubmit(submit)}>
      <FormError error={error} />
      <FormField label="Current password" type="password" autoComplete="current-password" registration={form.register("current_password")} error={errors.current_password} />
      <FormField label="New password" type="password" autoComplete="new-password" hint="At least 12 characters." registration={form.register("new_password")} error={errors.new_password} />
      <FormField label="Confirm new password" type="password" autoComplete="new-password" registration={form.register("confirm")} error={errors.confirm} />
      <Button type="submit" className="w-fit" disabled={form.formState.isSubmitting}>
        Change password
      </Button>
    </form>
  )
}

import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"
import { z } from "zod"

import { FormError } from "@/components/form-error"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"
import { AuthCard } from "@/features/authentication/auth-card"
import { api } from "@/lib/api"

const schema = z.object({
  email: z.email("Enter a valid email."),
  username: z.string().regex(/^[A-Za-z0-9_.-]{3,64}$/, "Use 3-64 letters, digits, dots, dashes or underscores."),
  full_name: z.string().max(128),
  password: z.string().min(12, "Use at least 12 characters.").max(128),
})
type Values = z.infer<typeof schema>

/** Reachable only when enabled in this app's config. The backend independently refuses otherwise. */
export function RegisterPage() {
  const navigate = useNavigate()
  const [error, setError] = useState<unknown>(null)
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", username: "", full_name: "", password: "" },
  })
  const submit = async (values: Values) => {
    setError(null)
    try {
      await api.post("/auth/register", { ...values, full_name: values.full_name || null })
      toast.success("Account created. Please sign in.")
      navigate("/login")
    } catch (caught) {
      setError(caught)
    }
  }
  const { errors } = form.formState
  return (
    <AuthCard title="Create an account">
      <form className="grid gap-4" onSubmit={form.handleSubmit(submit)}>
        <FormError error={error} />
        <FormField label="Email" type="email" autoComplete="email" registration={form.register("email")} error={errors.email} />
        <FormField label="Username" autoComplete="username" registration={form.register("username")} error={errors.username} />
        <FormField label="Full name" autoComplete="name" registration={form.register("full_name")} error={errors.full_name} />
        <FormField label="Password" type="password" autoComplete="new-password" hint="At least 12 characters." registration={form.register("password")} error={errors.password} />
        <Button type="submit" disabled={form.formState.isSubmitting}>
          Create account
        </Button>
        <Link className="text-muted-foreground text-center text-sm hover:underline" to="/login">
          Back to sign in
        </Link>
      </form>
    </AuthCard>
  )
}

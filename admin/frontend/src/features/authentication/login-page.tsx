import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Navigate, useNavigate } from "react-router"
import { z } from "zod"

import { AuthCard } from "@/features/authentication/auth-card"
import { useAuth } from "@/features/authentication/auth-context"
import { FormError } from "@/components/form-error"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"

const schema = z.object({
  identifier: z.string().min(1, "Enter your email or username."),
  password: z.string().min(1, "Enter your password."),
})
type Values = z.infer<typeof schema>

export function LoginPage() {
  const { status, login } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<unknown>(null)
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { identifier: "", password: "" } })

  if (status === "authenticated") return <Navigate to="/" replace />

  const submit = async (values: Values) => {
    setError(null)
    try {
      const result = await login(values.identifier, values.password)
      if (result.status === "mfa_required") {
        navigate("/login/mfa", { state: { challenge: result.challenge_token } })
      } else {
        navigate("/")
      }
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <AuthCard title="Admin sign in" description="Administrative access only.">
      <form className="grid gap-4" onSubmit={form.handleSubmit(submit)}>
        <FormError error={error} />
        <FormField label="Email or username" autoComplete="username" autoFocus registration={form.register("identifier")} error={form.formState.errors.identifier} />
        <FormField label="Password" type="password" autoComplete="current-password" registration={form.register("password")} error={form.formState.errors.password} />
        <Button type="submit" disabled={form.formState.isSubmitting}>
          Sign in
        </Button>
      </form>
    </AuthCard>
  )
}

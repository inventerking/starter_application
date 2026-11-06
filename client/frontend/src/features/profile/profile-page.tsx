import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { ActivityTable } from "@/components/activity-table"
import { FormError } from "@/components/form-error"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { QueryState } from "@/components/query-state"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/features/authentication/auth-context"
import { MyAccessCard } from "@/features/roles/my-access-card"
import { api } from "@/lib/api"
import { formatDate } from "@/lib/format"
import type { ActivityEntry, Page, Profile } from "@/lib/types"

const schema = z.object({ full_name: z.string().max(128) })
type Values = z.infer<typeof schema>

export function ProfilePage() {
  const { can, user, reloadUser } = useAuth()
  const queryClient = useQueryClient()
  const profile = useQuery({ queryKey: ["profile"], queryFn: () => api.get<Profile>("/users/me"), enabled: can("profile.view") })
  const activity = useQuery({ queryKey: ["activity"], queryFn: () => api.get<Page<ActivityEntry>>("/users/me/activity"), enabled: can("activity.view") })
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { full_name: "" } })
  useEffect(() => {
    if (profile.data) form.reset({ full_name: profile.data.full_name ?? "" })
  }, [profile.data, form])
  const save = useMutation({
    mutationFn: (values: Values) => api.patch("/users/me", { full_name: values.full_name || null }),
    onSuccess: async () => {
      toast.success("Profile updated")
      await queryClient.invalidateQueries({ queryKey: ["profile"] })
      await reloadUser()
    },
  })
  return (
    <>
      <PageHeader title="Profile" description={user?.email} />
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Your details</CardTitle>
          </CardHeader>
          <CardContent>
            {can("profile.view") ? (
              <QueryState query={profile}>
                {(data) => (
                  <form className="grid gap-4" onSubmit={form.handleSubmit((values) => save.mutate(values))}>
                    <FormError error={save.error} />
                    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                      <dt className="text-muted-foreground">Email</dt>
                      <dd>{data.email}</dd>
                      <dt className="text-muted-foreground">Username</dt>
                      <dd>{data.username}</dd>
                      <dt className="text-muted-foreground">Member since</dt>
                      <dd>{formatDate(data.created_at)}</dd>
                    </dl>
                    <FormField label="Full name" disabled={!can("profile.update")} registration={form.register("full_name")} error={form.formState.errors.full_name} />
                    {can("profile.update") && (
                      <Button type="submit" className="w-fit" disabled={save.isPending}>
                        Save
                      </Button>
                    )}
                  </form>
                )}
              </QueryState>
            ) : (
              <p className="text-muted-foreground text-sm">Your account does not have access to profile details.</p>
            )}
          </CardContent>
        </Card>
        <MyAccessCard />
        {can("activity.view") && (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Recent activity</CardTitle>
              <CardDescription>Security events on your account.</CardDescription>
            </CardHeader>
            <CardContent>
              <QueryState query={activity}>{(page) => <ActivityTable entries={page.items} />}</QueryState>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}

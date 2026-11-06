# Admin Management

Manages `admin.users` only, through `app/modules/admins`. It has no access to Client data.

| Endpoint | Permission |
|---|---|
| `GET /api/v1/admins`, `GET /{id}`, `GET /{id}/roles`, `GET /{id}/permissions`, `GET /{id}/permissions/effective` | `admins.view` |
| `POST /api/v1/admins` | `admins.create` |
| `PATCH /{id}` | `admins.update` |
| `DELETE /{id}` (soft delete) | `admins.delete` |
| `POST /{id}/activate`, `POST /{id}/deactivate` | `admins.activate`, `admins.deactivate` |
| `POST /{id}/roles`, `DELETE /{id}/roles/{role_id}` | `admins.roles.manage` |
| `PUT` and `DELETE /{id}/permissions/{permission_id}` | `admins.permissions.manage` |
| `GET /{id}/mfa`, `POST /{id}/mfa/reset` | `admins.mfa.view_status`, `admins.mfa.reset` |
| `POST /{id}/password/reset` | `admins.password.reset` |
| `POST /{id}/sessions/revoke` | `admins.sessions.revoke` |
| `GET /{id}/activity` | `admins.activity.view` |

## Behavior

- **Creation:** the backend generates a temporary password, returned once, and sets
  `must_change_password`. The new account has no roles or permissions.
- **Deactivation and deletion:** revoke all sessions in the same transaction.
- **Deletion:** soft, so audit history keeps its meaning and the email and username become reusable.

See [authorization-model.md](authorization-model.md) for the safeguards.

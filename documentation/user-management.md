# User Management

Admin operators manage ordinary Client users (`client.users`) through the Admin application.

```text
Admin -> Admin authentication -> Admin permission check (users.*)
      -> ClientUserManagementService -> client_domain repository -> client.*
```

The acting Admin is authorized only by `admin.*` data. The roles and permissions being handled exist
only in `client.*`. Authorization of Client users themselves stays with the Client backend.

## Endpoints

| Endpoint | Admin permission |
|---|---|
| `GET /api/v1/users`, `GET /{id}`, `GET /{id}/roles`, `GET /{id}/permissions` | `users.view` |
| `POST /api/v1/users` | `users.create` |
| `PATCH /{id}` | `users.update` |
| `DELETE /{id}` (soft delete) | `users.delete` |
| `POST /{id}/activate`, `POST /{id}/deactivate` | `users.activate`, `users.deactivate` |
| `POST /{id}/roles`, `DELETE /{id}/roles/{role_id}` | `users.roles.manage` |
| `PUT` and `DELETE /{id}/permissions/{permission_id}` | `users.permissions.manage` |
| `GET /{id}/mfa`, `POST /{id}/mfa/reset` | `users.mfa.view_status`, `users.mfa.reset` |
| `POST /{id}/password/reset` | `users.password.reset` |
| `POST /{id}/sessions/revoke` | `users.sessions.revoke` |
| `GET /{id}/activity` | `users.activity.view` |
| `GET`, `POST`, `PATCH`, `DELETE /api/v1/client-roles`, `PUT /{id}/permissions` | `client_roles.*` |
| `GET /api/v1/client-permissions` | `client_permissions.view` |

## Cross-domain contract

- All Client access lives in `app/modules/client_domain`, with its own `MetaData` that Alembic never
  sees. `test_mapping_matches_real_client_migrations` fails if a Client migration breaks the mapping.
- The Client backend owns the permission definitions. Run its `sync_permissions` before managing
  Client roles. The Admin backend only reads them.
- An Admin operation and its Client changes are one database transaction.
- New users get a temporary password, returned once. Without explicit `role_ids`, they get the
  Client roles marked `is_default`. An empty list means no roles.
- The Client backend rehashes the password at the next login if its Argon2id parameters differ.
- MFA reset only clears Client MFA data. The Admin backend doesn't hold the Client MFA key.

## Data ownership

- `client.audit_logs` records `actor_type = administrator`, no actor ID, and a correlation ID.
- `admin.audit_logs` records the Admin and the Client record's UUID. It stores no names or emails
  of Client users.
- An email address may exist in both domains. They are unrelated accounts.

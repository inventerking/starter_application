# Permission Resolution

```text
1. Super Admin (Admin domain only)  -> ALLOW
2. Direct user DENY                 -> DENY
3. Direct user ALLOW                -> ALLOW
4. Any assigned role allows         -> ALLOW
5. Otherwise                        -> DENY
```

The Client domain has no Super Admin, so it starts at step 2.

- There is one implementation per domain: `is_allowed` in `app/modules/permissions/service.py`.
- Deprecated permissions are ignored at every step.
- `user_permissions` has one row per user and permission, so a user can't hold both ALLOW and DENY.
- Sessions restricted by MFA enrollment or a required password change hold no effective permissions.
- Each behavior is covered in `tests/test_authorization.py`.

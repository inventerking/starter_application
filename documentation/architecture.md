# Architecture

**Modular monolith, two independent applications, two independent security domains, one PostgreSQL
database with schema isolation.**

```text
Admin frontend :5173 -> Admin backend :8000 -> admin.*  (read/write)
                                            -> client.* (only via client_domain, for User Management)
Client frontend :5174 -> Client backend :8001 -> client.*
```

## Decisions

| Decision | Reasoning |
|---|---|
| No shared Python or frontend package | Either application can change or ship alone. Security code is intentionally duplicated. |
| The Admin backend accesses `client.*` directly and never calls the Client API | Specified by the control-plane design; neither backend needs the other running. |
| Synchronous SQLAlchemy with psycopg 3 | Route handlers run in a thread pool, so Argon2id hashing never blocks an event loop. |
| Schema name from configuration (`DATABASE_SCHEMA`) | Tests run real migrations in throwaway schemas without creating a database. |
| Business logic in services, explicit commits | Every multi-step sensitive operation is one transaction. |

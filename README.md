# Starter Application

A reusable, secure foundation for new software projects: two independently runnable applications
(Admin and Client) with independent security domains, sharing one PostgreSQL database through
strict schema isolation.

| Application | Frontend | Backend | API docs (development) | Schema |
|---|---|---|---|---|
| Admin | http://localhost:5173 | http://localhost:8000 | http://localhost:8000/docs | `admin` |
| Client | http://localhost:5174 | http://localhost:8001 | http://localhost:8001/docs | `client` |

Start with [documentation/development-setup.md](documentation/development-setup.md).
Architecture and security decisions are in [documentation/](documentation/).

"""User Management, the separation from Admin Management, and the cross-domain contract."""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.database import SCHEMA, Base, engine
from app.modules.admins.models import AdminUser
from app.modules.audit.models import AuditLog
from app.modules.client_domain.models import (
    CLIENT_SCHEMA,
    ClientAuditLog,
    ClientBase,
    ClientRecoveryCode,
    ClientSession,
    ClientUser,
    ClientUserRole,
)
from app.modules.roles.models import Role, UserRole
from tests.conftest import CLIENT_BACKEND_DIR, auth_headers

USERS = "/api/v1/users"
ADMINS = "/api/v1/admins"
CLIENT_ROLES = "/api/v1/client-roles"
ADMIN_ROLES = "/api/v1/admin-roles"


def _count(db, model):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


@pytest.fixture
def root(client, make_admin, permissions):
    return auth_headers(client, make_admin(is_superuser=True))


class TestUserManagement:
    def test_create_writes_client_only(self, client, root, db):
        admin_count = _count(db, AdminUser)
        response = client.post(USERS, headers=root, json={"email": "u@example.com", "username": "uuser"})
        assert response.status_code == 201
        body = response.json()
        assert body["must_change_password"] is True and body["temporary_password"]
        assert "password_hash" not in body and "is_superuser" not in body
        assert _count(db, AdminUser) == admin_count
        stored = db.get(ClientUser, uuid.UUID(body["id"]))
        assert stored.password_hash.startswith("$argon2id$")

    def test_default_and_explicit_roles(self, client, root, make_client_role, db):
        default = make_client_role(is_default=True)
        make_client_role()
        explicit = make_client_role()
        first = client.post(USERS, headers=root, json={"email": "a@example.com", "username": "aaa"}).json()
        assert [r["id"] for r in client.get(f"{USERS}/{first['id']}/roles", headers=root).json()] == [str(default.id)]
        second = client.post(USERS, headers=root, json={"email": "b@example.com", "username": "bbb", "role_ids": [str(explicit.id)]}).json()
        assert [r["id"] for r in client.get(f"{USERS}/{second['id']}/roles", headers=root).json()] == [str(explicit.id)]
        third = client.post(USERS, headers=root, json={"email": "c@example.com", "username": "ccc", "role_ids": []}).json()
        assert client.get(f"{USERS}/{third['id']}/roles", headers=root).json() == []

    def test_same_email_may_exist_in_both_domains(self, client, root, make_admin):
        admin = make_admin()
        assert client.post(USERS, headers=root, json={"email": admin.email, "username": admin.username}).status_code == 201

    def test_duplicate_rejected(self, client, root, make_client_user):
        user = make_client_user()
        assert client.post(USERS, headers=root, json={"email": user.email.upper(), "username": "fresh"}).status_code == 409

    def test_crud_and_search(self, client, root, make_client_user):
        user = make_client_user(email="findme@example.com", username="findme")
        make_client_user()
        assert client.get(USERS, headers=root, params={"search": "findme"}).json()["total"] == 1
        assert client.get(f"{USERS}/{user.id}", headers=root).json()["email"] == "findme@example.com"
        assert client.patch(f"{USERS}/{user.id}", headers=root, json={"full_name": "F"}).json()["full_name"] == "F"
        assert client.delete(f"{USERS}/{user.id}", headers=root).status_code == 204
        assert client.get(f"{USERS}/{user.id}", headers=root).status_code == 404
        assert "argon2" not in client.get(USERS, headers=root).text

    def test_deactivation_revokes_client_sessions_in_one_transaction(self, client, root, make_client_user, db):
        user = make_client_user()
        db.execute(text(f"""INSERT INTO "{CLIENT_SCHEMA}".sessions
            (id, user_id, scope, access_token_hash, access_expires_at, expires_at)
            VALUES (gen_random_uuid(), :u, 'full', 'x', now(), now() + interval '1 day')"""), {"u": user.id})
        db.commit()
        assert client.post(f"{USERS}/{user.id}/deactivate", headers=root).json()["is_active"] is False
        db.expire_all()
        assert db.scalar(select(ClientSession.revoked_at).where(ClientSession.user_id == user.id)) is not None
        assert client.post(f"{USERS}/{user.id}/activate", headers=root).json()["is_active"] is True

    def test_role_assignment_and_overrides(self, client, root, make_client_user, make_client_role, client_permissions):
        user, role = make_client_user(), make_client_role()
        roles = f"{USERS}/{user.id}/roles"
        assert client.post(roles, headers=root, json={"role_id": str(role.id)}).status_code == 204
        assert client.post(roles, headers=root, json={"role_id": str(role.id)}).status_code == 204
        assert len(client.get(roles, headers=root).json()) == 1
        assert client.delete(f"{roles}/{role.id}", headers=root).status_code == 204
        assert client.delete(f"{roles}/{role.id}", headers=root).status_code == 404
        permission = client_permissions["profile.view"]
        path = f"{USERS}/{user.id}/permissions/{permission.id}"
        assert client.put(path, headers=root, json={"effect": "DENY"}).status_code == 204
        assert client.put(path, headers=root, json={"effect": "ALLOW", "reason": "ok"}).status_code == 204
        listed = client.get(f"{USERS}/{user.id}/permissions", headers=root).json()
        assert listed[0]["effect"] == "ALLOW" and listed[0]["permission"]["code"] == "profile.view"
        assert client.delete(path, headers=root).status_code == 204
        assert client.get(f"{USERS}/{user.id}/permissions", headers=root).json() == []
        assert client.put(f"{USERS}/{user.id}/permissions/{uuid.uuid4()}", headers=root, json={"effect": "ALLOW"}).status_code == 422

    def test_mfa_reset_clears_without_reading_secret(self, client, root, make_client_user, db):
        user = make_client_user(mfa_enabled=True, mfa_secret_encrypted="v1.other-key.a.b", mfa_key_id="x")
        db.execute(text(f"""INSERT INTO "{CLIENT_SCHEMA}".mfa_recovery_codes (id, user_id, code_hash)
            VALUES (gen_random_uuid(), :u, 'hash')"""), {"u": user.id})
        db.commit()
        status = client.get(f"{USERS}/{user.id}/mfa", headers=root).json()
        assert status["enabled"] is True and status["recovery_codes_remaining"] == 1
        assert "v1.other-key" not in str(status)
        assert client.post(f"{USERS}/{user.id}/mfa/reset", headers=root).status_code == 204
        db.expire_all()
        stored = db.get(ClientUser, user.id)
        assert not stored.mfa_enabled and stored.mfa_secret_encrypted is None and stored.mfa_enrollment_required
        assert _count(db, ClientRecoveryCode) == 0

    def test_temporary_password(self, client, root, make_client_user, db):
        user = make_client_user()
        old = user.password_hash
        response = client.post(f"{USERS}/{user.id}/password/reset", headers=root)
        assert response.status_code == 200 and response.json()["temporary_password"]
        db.expire_all()
        stored = db.get(ClientUser, user.id)
        assert stored.password_hash != old and stored.must_change_password


class TestAuditAcrossDomains:
    def test_both_trails_written_and_client_trail_has_no_admin_identity(self, client, make_admin, permissions, db):
        actor = make_admin(is_superuser=True)
        headers = auth_headers(client, actor)
        body = client.post(USERS, headers=headers, json={"email": "u@example.com", "username": "uuser"}).json()
        db.expire_all()
        admin_entry = db.scalar(select(AuditLog).where(AuditLog.action == "USER_CREATED"))
        client_entry = db.scalar(select(ClientAuditLog).where(ClientAuditLog.action == "USER_CREATED"))
        assert admin_entry.actor_id == actor.id and str(admin_entry.target_id) == body["id"]
        assert admin_entry.target_type == "client_user"
        assert client_entry.actor_type == "administrator" and client_entry.actor_id is None
        assert client_entry.details["correlation_id"] == admin_entry.details["request_id"]
        assert str(actor.id) not in str(client_entry.details) and actor.email not in str(client_entry.details)
        assert client_entry.ip_address is None
        assert "u@example.com" not in str(admin_entry.details)

    def test_activity_view_reads_client_trail(self, client, root, make_client_user):
        user = make_client_user()
        client.post(f"{USERS}/{user.id}/deactivate", headers=root)
        activity = client.get(f"{USERS}/{user.id}/activity", headers=root).json()
        assert [item["action"] for item in activity["items"]] == ["USER_DEACTIVATED"]
        assert activity["items"][0]["actor_type"] == "administrator"


class TestClientRoles:
    def test_lifecycle_stays_in_client_schema(self, client, root, client_permissions, db):
        admin_roles = _count(db, Role)
        created = client.post(CLIENT_ROLES, headers=root, json={
            "name": "Subscriber", "permission_ids": [str(client_permissions["profile.view"].id)]})
        assert created.status_code == 201
        assert [p["code"] for p in created.json()["permissions"]] == ["profile.view"]
        role_id = created.json()["id"]
        assert _count(db, Role) == admin_roles
        assert client.get(ADMIN_ROLES, headers=root).json() == []
        assert client.patch(f"{CLIENT_ROLES}/{role_id}", headers=root, json={"is_default": True}).json()["is_default"] is True
        assert client.put(f"{CLIENT_ROLES}/{role_id}/permissions", headers=root, json={"permission_ids": []}).json()["permissions"] == []
        assert client.delete(f"{CLIENT_ROLES}/{role_id}", headers=root).status_code == 204

    def test_system_role_requires_super_admin(self, client, make_admin, grant, make_client_role):
        role = make_client_role(is_system=True)
        actor = make_admin()
        grant(actor, "client_roles.update")
        assert client.patch(f"{CLIENT_ROLES}/{role.id}", headers=auth_headers(client, actor), json={"description": "x"}).status_code == 403

    def test_admin_permission_ids_rejected_for_client_roles(self, client, root, permissions):
        response = client.post(CLIENT_ROLES, headers=root, json={
            "name": "Mixed", "permission_ids": [str(permissions["admins.view"].id)]})
        assert response.status_code == 422


class TestManagementSeparation:
    def test_admin_management_cannot_create_client_users(self, client, root, db):
        before = _count(db, ClientUser)
        assert client.post(ADMINS, headers=root, json={"email": "a@example.com", "username": "aaa"}).status_code == 201
        assert _count(db, ClientUser) == before

    def test_users_view_does_not_grant_admins_view(self, client, make_admin, grant):
        actor = make_admin()
        grant(actor, "users.view")
        headers = auth_headers(client, actor)
        assert client.get(USERS, headers=headers).status_code == 200
        assert client.get(ADMINS, headers=headers).status_code == 403

    def test_admins_view_does_not_grant_users_view(self, client, make_admin, grant):
        actor = make_admin()
        grant(actor, "admins.view")
        headers = auth_headers(client, actor)
        assert client.get(ADMINS, headers=headers).status_code == 200
        assert client.get(USERS, headers=headers).status_code == 403

    def test_both_groups_can_use_both(self, client, make_admin, grant):
        actor = make_admin()
        grant(actor, "users.view", "admins.view")
        headers = auth_headers(client, actor)
        assert client.get(USERS, headers=headers).status_code == 200
        assert client.get(ADMINS, headers=headers).status_code == 200

    def test_admin_with_no_permissions_can_use_neither(self, client, make_admin, permissions):
        headers = auth_headers(client, make_admin())
        assert client.get(USERS, headers=headers).status_code == 403
        assert client.get(ADMINS, headers=headers).status_code == 403
        assert client.get(CLIENT_ROLES, headers=headers).status_code == 403

    def test_super_admin_can_use_both(self, client, root):
        assert client.get(USERS, headers=root).status_code == 200
        assert client.get(ADMINS, headers=root).status_code == 200

    @pytest.mark.parametrize("method,suffix,permission", [
        ("post", "", "users.create"),
        ("patch", "/{id}", "users.update"),
        ("delete", "/{id}", "users.delete"),
        ("post", "/{id}/activate", "users.activate"),
        ("post", "/{id}/deactivate", "users.deactivate"),
        ("post", "/{id}/mfa/reset", "users.mfa.reset"),
        ("get", "/{id}/mfa", "users.mfa.view_status"),
        ("post", "/{id}/password/reset", "users.password.reset"),
        ("post", "/{id}/sessions/revoke", "users.sessions.revoke"),
        ("get", "/{id}/activity", "users.activity.view"),
    ])
    def test_each_operation_needs_its_own_permission(
        self, client, make_admin, grant, make_client_user, method, suffix, permission
    ):
        user = make_client_user()
        actor = make_admin()
        grant(actor, "users.view")
        headers = auth_headers(client, actor)
        url = USERS + suffix.format(id=user.id)
        kwargs = {"json": {"email": "n@example.com", "username": "nnn"}} if method == "post" and not suffix else {}
        kwargs = {"json": {"full_name": "x"}} if method == "patch" else kwargs
        assert getattr(client, method)(url, headers=headers, **kwargs).status_code == 403
        grant(actor, permission)
        assert getattr(client, method)(url, headers=headers, **kwargs).status_code < 300


class TestRoleRecordsNeverCross:
    def test_admin_role_id_rejected_for_client_assignment(self, client, root, make_client_user, db):
        admin_role = Role(name="Admin Only")
        db.add(admin_role)
        db.commit()
        user = make_client_user()
        response = client.post(f"{USERS}/{user.id}/roles", headers=root, json={"role_id": str(admin_role.id)})
        assert response.status_code == 404
        assert _count(db, ClientUserRole) == 0

    def test_client_role_id_rejected_for_admin_assignment(self, client, root, make_admin, make_client_role, db):
        role = make_client_role()
        target = make_admin()
        response = client.post(f"{ADMINS}/{target.id}/roles", headers=root, json={"role_id": str(role.id)})
        assert response.status_code == 404
        assert _count(db, UserRole) == 0

    def test_client_role_cannot_be_used_to_create_user_with_admin_role(self, client, root, db):
        admin_role = Role(name="Admin Only")
        db.add(admin_role)
        db.commit()
        response = client.post(USERS, headers=root, json={
            "email": "x@example.com", "username": "xxx", "role_ids": [str(admin_role.id)]})
        assert response.status_code == 404

    def test_database_rejects_admin_role_in_client_table(self, db, make_client_user):
        admin_role = Role(name="Admin Only")
        db.add(admin_role)
        db.commit()
        db.add(ClientUserRole(user_id=make_client_user().id, role_id=admin_role.id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestCrossDomainContract:
    def test_admin_alembic_cannot_see_client_tables(self):
        assert all(table.schema == SCHEMA for table in Base.metadata.tables.values())
        assert all(table.schema == CLIENT_SCHEMA for table in ClientBase.metadata.tables.values())
        assert not set(Base.metadata.tables) & set(ClientBase.metadata.tables)

    def test_mapping_matches_real_client_migrations(self):
        """Fails if a Client migration renames or drops a column the Admin backend depends on."""
        with engine.connect() as connection:
            inspector = inspect(connection)
            for table in ClientBase.metadata.tables.values():
                actual = {c["name"]: c for c in inspector.get_columns(table.name, schema=CLIENT_SCHEMA)}
                for column in table.columns:
                    assert column.name in actual, f"{table.name}.{column.name} missing"
                    assert column.type.as_generic().__class__ == actual[column.name]["type"].as_generic().__class__, \
                        f"{table.name}.{column.name} type differs"

    def test_admin_tables_are_not_in_client_schema_mapping_namespace(self):
        assert "password_reset_tokens" not in ClientBase.metadata.tables

    def test_client_registry_sync_feeds_the_admin_view(self, client, root):
        """The Client backend owns its registry. The Admin backend only reads the result."""
        env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
        env["DATABASE_SCHEMA"] = get_settings().client_database_schema
        subprocess.run(["uv", "run", "-q", "python", "-m", "app.cli.sync_permissions"],
                       cwd=CLIENT_BACKEND_DIR, env=env, check=True, capture_output=True)
        codes = [row["code"] for row in client.get("/api/v1/client-permissions", headers=root).json()]
        assert "profile.update" in codes and "admins.view" not in codes
        roles = client.get(CLIENT_ROLES, headers=root).json()
        assert [role["name"] for role in roles] == ["Member"] and roles[0]["is_default"]

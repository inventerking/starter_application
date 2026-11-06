import pytest
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import require_permission
from app.modules.admins.permissions import ADMINS_VIEW
from app.modules.permissions.models import Permission, UserPermission
from app.modules.permissions.registry import PermissionRegistry
from app.modules.permissions.service import PermissionService, is_allowed
from app.modules.roles.models import Role, RolePermission, UserRole
from tests.conftest import auth_headers

CODE = "admins.view"


def _resolve(**overrides):
    values = {"is_superuser": False, "direct_deny": set(), "direct_allow": set(), "role_allow": set()}
    return is_allowed(CODE, **(values | overrides))


class TestResolutionPrecedence:
    def test_default_deny(self):
        assert _resolve() is False

    def test_role_allows(self):
        assert _resolve(role_allow={CODE}) is True

    def test_direct_allow_without_role(self):
        assert _resolve(direct_allow={CODE}) is True

    def test_direct_deny_overrides_role(self):
        assert _resolve(direct_deny={CODE}, role_allow={CODE}) is False

    def test_direct_deny_overrides_direct_allow(self):
        assert _resolve(direct_deny={CODE}, direct_allow={CODE}) is False

    def test_super_admin_overrides_direct_deny(self):
        assert _resolve(is_superuser=True, direct_deny={CODE}) is True

    def test_other_permission_does_not_leak(self):
        assert _resolve(role_allow={"users.view"}) is False


class TestRegistry:
    def test_rejects_invalid_and_duplicate_names(self):
        registry = PermissionRegistry()
        registry.register("things", "view", "x")
        for resource, action in (("Bad", "view"), ("a b", "view"), ("things", "Bad!")):
            with pytest.raises(ValueError):
                registry.register(resource, action, "x")
        with pytest.raises(ValueError):
            registry.register("things", "view", "x")

    def test_guard_rejects_arbitrary_strings(self):
        with pytest.raises(TypeError):
            require_permission("admins.view")

    def test_sync_adds_updates_and_deprecates_but_never_deletes(self, db):
        service = PermissionService(db)
        first = service.sync_registry()
        assert first.added > 0
        db.commit()
        assert service.sync_registry().added == 0
        ghost = Permission(resource="ghost", action="view", code="ghost.view", description="old")
        db.add(ghost)
        db.flush()
        result = service.sync_registry()
        db.commit()
        assert result.deprecated == 1
        db.refresh(ghost)
        assert ghost.deprecated_at is not None

    def test_structured_fields(self, permissions):
        row = permissions["admins.roles.manage"]
        assert (row.resource, row.action, row.code) == ("admins.roles", "manage", "admins.roles.manage")


class TestEffectivePermissions:
    def test_role_grant_and_multiple_roles(self, db, make_admin, permissions):
        user = make_admin()
        for name, code in (("One", "admins.view"), ("Two", "admins.create")):
            role = Role(name=name)
            db.add(role)
            db.flush()
            db.add(RolePermission(role_id=role.id, permission_id=permissions[code].id))
            db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        assert PermissionService(db).effective_codes(user) == {"admins.view", "admins.create"}

    def test_direct_deny_removes_role_permission(self, db, make_admin, permissions):
        user = make_admin()
        role = Role(name="One")
        db.add(role)
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permissions[CODE].id))
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.add(UserPermission(user_id=user.id, permission_id=permissions[CODE].id, effect="DENY"))
        db.commit()
        assert not PermissionService(db).has(user, ADMINS_VIEW)

    def test_super_admin_has_everything(self, db, make_admin, permissions):
        assert PermissionService(db).effective_codes(make_admin(is_superuser=True)) == set(permissions)

    def test_deprecated_permission_is_never_effective(self, db, make_admin, grant, permissions):
        from app.core.database import utcnow

        user = make_admin()
        grant(user, CODE)
        permissions[CODE].deprecated_at = utcnow()
        db.commit()
        assert CODE not in PermissionService(db).effective_codes(user)

    def test_one_override_per_user_and_permission(self, db, make_admin, permissions):
        user = make_admin()
        db.add(UserPermission(user_id=user.id, permission_id=permissions[CODE].id, effect="ALLOW"))
        db.commit()
        db.add(UserPermission(user_id=user.id, permission_id=permissions[CODE].id, effect="DENY"))
        with pytest.raises(Exception):  # noqa: B017 - identity conflict or IntegrityError
            db.commit()
        db.rollback()

    def test_invalid_effect_rejected_by_database(self, db, make_admin, permissions):
        db.add(UserPermission(user_id=make_admin().id, permission_id=permissions[CODE].id, effect="MAYBE"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestMeReflectsAuthorization:
    def test_me_lists_effective_permissions(self, client, make_admin, grant):
        user = make_admin()
        grant(user, CODE)
        assert client.get("/api/v1/auth/me", headers=auth_headers(client, user)).json()["permissions"] == [CODE]

    def test_restricted_session_lists_nothing(self, client, make_admin, grant):
        user = make_admin(must_change_password=True)
        grant(user, CODE)
        assert client.get("/api/v1/auth/me", headers=auth_headers(client, user)).json()["permissions"] == []


class TestAdminRolesApi:
    PATH = "/api/v1/admin-roles"

    def test_requires_permission(self, client, make_admin, permissions):
        headers = auth_headers(client, make_admin())
        assert client.get(self.PATH, headers=headers).status_code == 403
        assert client.post(self.PATH, headers=headers, json={"name": "X1"}).status_code == 403

    def test_super_admin_full_lifecycle(self, client, make_admin, permissions, db):
        headers = auth_headers(client, make_admin(is_superuser=True))
        created = client.post(self.PATH, headers=headers, json={
            "name": "Support", "permission_ids": [str(permissions[CODE].id)]})
        assert created.status_code == 201
        assert [p["code"] for p in created.json()["permissions"]] == [CODE]
        role_id = created.json()["id"]
        assert client.post(self.PATH, headers=headers, json={"name": "support"}).status_code == 409
        assert client.patch(f"{self.PATH}/{role_id}", headers=headers, json={"description": "d"}).json()["description"] == "d"
        replaced = client.put(f"{self.PATH}/{role_id}/permissions", headers=headers, json={"permission_ids": []})
        assert replaced.json()["permissions"] == []
        assert client.delete(f"{self.PATH}/{role_id}", headers=headers).status_code == 204
        assert client.get(f"{self.PATH}/{role_id}", headers=headers).status_code == 404

    def test_cannot_create_role_beyond_own_access(self, client, make_admin, grant, permissions):
        user = make_admin()
        grant(user, "admin_roles.create")
        headers = auth_headers(client, user)
        response = client.post(self.PATH, headers=headers, json={
            "name": "Escalate", "permission_ids": [str(permissions["admins.mfa.reset"].id)]})
        assert response.status_code == 403 and response.json()["error"]["code"] == "privilege_escalation"
        assert client.post(self.PATH, headers=headers, json={
            "name": "Own", "permission_ids": [str(permissions["admin_roles.create"].id)]}).status_code == 201

    def test_cannot_add_permissions_beyond_own_access(self, client, make_admin, grant, permissions, db):
        user = make_admin()
        grant(user, "admin_roles.update")
        role = Role(name="Mine")
        db.add(role)
        db.commit()
        response = client.put(f"{self.PATH}/{role.id}/permissions", headers=auth_headers(client, user),
                              json={"permission_ids": [str(permissions["admins.delete"].id)]})
        assert response.status_code == 403

    def test_cannot_edit_role_stronger_than_actor(self, client, make_admin, grant, permissions, db):
        user = make_admin()
        grant(user, "admin_roles.delete")
        role = Role(name="Strong")
        db.add(role)
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permissions["admins.delete"].id))
        db.commit()
        response = client.delete(f"{self.PATH}/{role.id}", headers=auth_headers(client, user))
        assert response.status_code == 403 and response.json()["error"]["code"] == "role_exceeds_actor"

    def test_system_role_only_super_admin(self, client, make_admin, grant, db, permissions):
        role = Role(name="Sys", is_system=True)
        db.add(role)
        db.commit()
        user = make_admin()
        grant(user, "admin_roles.update")
        path = f"{self.PATH}/{role.id}"
        assert client.patch(path, headers=auth_headers(client, user), json={"description": "x"}).status_code == 403
        root = make_admin(is_superuser=True)
        assert client.patch(path, headers=auth_headers(client, root), json={"description": "x"}).status_code == 200

    def test_unknown_permission_id_rejected(self, client, make_admin, permissions):
        import uuid

        headers = auth_headers(client, make_admin(is_superuser=True))
        assert client.post(self.PATH, headers=headers, json={"name": "R1", "permission_ids": [str(uuid.uuid4())]}).status_code == 422


def test_permission_registry_endpoint(client, make_admin, grant, permissions):
    user = make_admin()
    assert client.get("/api/v1/admin-permissions", headers=auth_headers(client, user)).status_code == 403
    grant(user, "admin_permissions.view")
    body = client.get("/api/v1/admin-permissions", headers=auth_headers(client, user)).json()
    assert {"resource", "action", "code", "description"} <= set(body[0])

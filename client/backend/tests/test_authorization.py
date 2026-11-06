import pytest
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import require_permission
from app.modules.audit.models import AuditLog
from app.modules.permissions.models import UserPermission
from app.modules.permissions.registry import registry
from app.modules.permissions.service import PermissionService, is_allowed
from app.modules.roles.models import Role, RolePermission, UserRole
from app.modules.users.permissions import PROFILE_VIEW
from tests.conftest import auth_headers

CODE = "profile.view"
PROFILE = "/api/v1/users/me"


def _resolve(**overrides):
    values = {"direct_deny": set(), "direct_allow": set(), "role_allow": set()}
    return is_allowed(CODE, **(values | overrides))


class TestResolutionPrecedence:
    def test_default_deny(self):
        assert _resolve() is False

    def test_role_allows(self):
        assert _resolve(role_allow={CODE}) is True

    def test_direct_allow(self):
        assert _resolve(direct_allow={CODE}) is True

    def test_direct_deny_overrides_role(self):
        assert _resolve(direct_deny={CODE}, role_allow={CODE}) is False

    def test_direct_deny_overrides_direct_allow(self):
        assert _resolve(direct_deny={CODE}, direct_allow={CODE}) is False


@pytest.fixture
def member_role(db, permissions):
    role = Role(name="Member")
    db.add(role)
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=permissions[CODE].id))
    db.commit()
    return role


class TestEnforcement:
    def test_unauthenticated_rejected(self, client):
        assert client.get(PROFILE).status_code == 401

    def test_no_role_is_denied(self, client, make_user, permissions):
        assert client.get(PROFILE, headers=auth_headers(client, make_user())).status_code == 403

    def test_role_grants_only_its_permissions(self, client, make_user, member_role, db):
        user = make_user()
        db.add(UserRole(user_id=user.id, role_id=member_role.id))
        db.commit()
        headers = auth_headers(client, user)
        assert client.get(PROFILE, headers=headers).status_code == 200
        assert client.patch(PROFILE, headers=headers, json={"full_name": "X"}).status_code == 403

    def test_direct_allow_works_without_role(self, client, make_user, permissions, db):
        user = make_user()
        db.add(UserPermission(user_id=user.id, permission_id=permissions["profile.update"].id, effect="ALLOW"))
        db.commit()
        response = client.patch(PROFILE, headers=auth_headers(client, user), json={"full_name": "X"})
        assert response.status_code == 200 and response.json()["full_name"] == "X"
        assert "password" not in response.text

    def test_direct_deny_beats_role(self, client, make_user, member_role, permissions, db):
        user = make_user()
        db.add(UserRole(user_id=user.id, role_id=member_role.id))
        db.add(UserPermission(user_id=user.id, permission_id=permissions[CODE].id, effect="DENY"))
        db.commit()
        assert client.get(PROFILE, headers=auth_headers(client, user)).status_code == 403
        assert not PermissionService(db).has(user, PROFILE_VIEW)

    def test_deprecated_permission_is_never_effective(self, make_user, permissions, db):
        from app.core.database import utcnow

        user = make_user()
        db.add(UserPermission(user_id=user.id, permission_id=permissions[CODE].id, effect="ALLOW"))
        permissions[CODE].deprecated_at = utcnow()
        db.commit()
        assert CODE not in PermissionService(db).effective_codes(user)

    def test_self_service_endpoints_list_own_access(self, client, make_user, member_role, db):
        user = make_user()
        db.add(UserRole(user_id=user.id, role_id=member_role.id))
        db.commit()
        headers = auth_headers(client, user)
        assert client.get("/api/v1/permissions/me", headers=headers).json() == [CODE]
        assert [r["name"] for r in client.get("/api/v1/roles/me", headers=headers).json()] == ["Member"]
        assert client.get("/api/v1/auth/me", headers=headers).json()["permissions"] == [CODE]

    def test_activity_requires_permission_and_shows_only_own(self, client, make_user, permissions, db):
        user, other = make_user(), make_user()
        db.add(UserPermission(user_id=user.id, permission_id=permissions["activity.view"].id, effect="ALLOW"))
        db.commit()
        auth_headers(client, other)
        headers = auth_headers(client, user)
        items = client.get(f"{PROFILE}/activity", headers=headers).json()["items"]
        assert items and all(item["action"] == "LOGIN_SUCCESS" for item in items) and len(items) == 1
        assert db.query(AuditLog).count() == 2
        assert client.get(f"{PROFILE}/activity", headers=auth_headers(client, other)).status_code == 403


class TestRegistryAndSeeding:
    def test_guard_rejects_arbitrary_strings(self):
        with pytest.raises(TypeError):
            require_permission("profile.view")

    def test_sync_is_idempotent_and_seeds_default_role_once(self, db):
        service = PermissionService(db)
        assert service.sync_registry().added == len(registry.all())
        service.ensure_default_role()
        db.commit()
        assert service.sync_registry().added == 0
        service.ensure_default_role()
        db.commit()
        role = db.query(Role).one()
        assert role.is_default and role.name == "Member" and not role.is_system

    def test_seed_does_not_return_after_administrators_change_roles(self, db):
        service = PermissionService(db)
        service.sync_registry()
        db.add(Role(name="Subscriber"))
        db.commit()
        service.ensure_default_role()
        db.commit()
        assert [role.name for role in db.query(Role).all()] == ["Subscriber"]

    def test_invalid_effect_rejected_by_database(self, db, make_user, permissions):
        db.add(UserPermission(user_id=make_user().id, permission_id=permissions[CODE].id, effect="MAYBE"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_client_domain_knows_nothing_about_admin():
    """No Client model or service may reference an Admin concept."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    forbidden = ("is_superuser", "super_admin", "AdminUser", "admin_mfa_required", "admin_refresh")
    for path in root.rglob("*.py"):
        text = path.read_text()
        for word in forbidden:
            assert word not in text, f"{word} in {path}"
    from sqlalchemy import inspect as _inspect

    from app.core.database import SCHEMA, engine

    with engine.connect() as connection:
        columns = {c["name"] for c in _inspect(connection).get_columns("users", schema=SCHEMA)}
    assert "is_superuser" not in columns and "created_by" not in columns

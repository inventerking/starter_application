import uuid

import pytest
from sqlalchemy import select, text

from app.core.database import SCHEMA
from app.core.request_context import RequestContext
from app.modules.admins.exceptions import LastSuperAdmin
from app.modules.admins.models import AdminUser
from app.modules.admins.service import AdminManagementService
from app.modules.audit.models import AuditLog
from app.modules.roles.models import Role, RolePermission
from tests.conftest import PASSWORD, auth_headers, enroll_mfa, login

PATH = "/api/v1/admins"
ME = "/api/v1/auth/me"


def _actions(db):
    db.expire_all()
    return [row.action for row in db.scalars(select(AuditLog)).all()]


def _root(client, make_admin, permissions):
    user = make_admin(is_superuser=True)
    return user, auth_headers(client, user)


class TestCrud:
    def test_create_with_temporary_password(self, client, make_admin, permissions, db):
        _, headers = _root(client, make_admin, permissions)
        response = client.post(PATH, headers=headers, json={"email": "new@example.com", "username": "newbie"})
        assert response.status_code == 201
        body = response.json()
        assert body["is_superuser"] is False and body["must_change_password"] is True
        assert "password_hash" not in body
        stored = db.get(AdminUser, uuid.UUID(body["id"]))
        assert stored.password_hash.startswith("$argon2id$")
        fresh = client.post("/api/v1/auth/login", json={"identifier": "newbie", "password": body["temporary_password"]})
        assert fresh.status_code == 200
        assert "ADMIN_CREATED" in _actions(db)
        logged = db.execute(text(f'SELECT details::text FROM "{SCHEMA}".audit_logs')).scalars().all()
        assert body["temporary_password"] not in " ".join(logged)

    def test_cannot_set_superuser_through_api(self, client, make_admin, permissions, db):
        _, headers = _root(client, make_admin, permissions)
        created = client.post(PATH, headers=headers, json={"email": "n@example.com", "username": "nnn", "is_superuser": True}).json()
        assert created["is_superuser"] is False
        patched = client.patch(f"{PATH}/{created['id']}", headers=headers, json={"is_superuser": True}).json()
        assert patched["is_superuser"] is False

    def test_duplicates_rejected_case_insensitively(self, client, make_admin, permissions):
        user, headers = _root(client, make_admin, permissions)
        assert client.post(PATH, headers=headers, json={"email": user.email.upper(), "username": "other"}).status_code == 409
        assert client.post(PATH, headers=headers, json={"email": "x@example.com", "username": user.username.upper()}).status_code == 409

    def test_list_search_pagination_and_no_hash(self, client, make_admin, permissions):
        _, headers = _root(client, make_admin, permissions)
        make_admin(email="findme@example.com", username="findme")
        make_admin()
        body = client.get(PATH, headers=headers, params={"search": "findme"}).json()
        assert body["total"] == 1 and body["items"][0]["username"] == "findme"
        page = client.get(PATH, headers=headers, params={"page_size": 1}).json()
        assert page["total"] == 3 and len(page["items"]) == 1
        assert "argon2" not in client.get(PATH, headers=headers).text
        assert client.get(PATH, headers=headers, params={"search": "%"}).json()["total"] == 0

    def test_update(self, client, make_admin, permissions, db):
        target = make_admin()
        _, headers = _root(client, make_admin, permissions)
        response = client.patch(f"{PATH}/{target.id}", headers=headers, json={"full_name": "New Name"})
        assert response.json()["full_name"] == "New Name"
        assert "ADMIN_UPDATED" in _actions(db)

    def test_soft_delete_frees_identity_and_blocks_login(self, client, make_admin, permissions, db):
        target = make_admin(email="gone@example.com", username="gone")
        token = auth_headers(client, target)
        _, headers = _root(client, make_admin, permissions)
        assert client.delete(f"{PATH}/{target.id}", headers=headers).status_code == 204
        assert client.get(f"{PATH}/{target.id}", headers=headers).status_code == 404
        assert client.get(ME, headers=token).status_code == 401
        assert login(client, target).status_code == 401
        db.expire_all()
        assert db.get(AdminUser, target.id).deleted_at is not None
        assert client.post(PATH, headers=headers, json={"email": "gone@example.com", "username": "gone"}).status_code == 201


class TestActivation:
    def test_deactivate_revokes_sessions_and_activate_restores_login(self, client, make_admin, permissions, db):
        target = make_admin()
        token = auth_headers(client, target)
        _, headers = _root(client, make_admin, permissions)
        assert client.post(f"{PATH}/{target.id}/deactivate", headers=headers).json()["is_active"] is False
        assert client.get(ME, headers=token).status_code == 401
        assert login(client, target).status_code == 401
        assert client.post(f"{PATH}/{target.id}/activate", headers=headers).json()["is_active"] is True
        assert login(client, target).status_code == 200
        assert client.get(ME, headers=token).status_code == 401  # Old sessions stay revoked.
        assert {"ADMIN_ACTIVATED", "ADMIN_DEACTIVATED"} <= set(_actions(db))


class TestSuperAdminSafeguards:
    def test_no_self_deactivation_or_deletion(self, client, make_admin, permissions):
        user, headers = _root(client, make_admin, permissions)
        make_admin(is_superuser=True)
        for call in (client.post(f"{PATH}/{user.id}/deactivate", headers=headers),
                     client.delete(f"{PATH}/{user.id}", headers=headers)):
            assert call.status_code == 403 and call.json()["error"]["code"] == "self_action_forbidden"

    def test_super_admin_cannot_be_deleted_via_api(self, client, make_admin, permissions):
        _, headers = _root(client, make_admin, permissions)
        other = make_admin(is_superuser=True)
        response = client.delete(f"{PATH}/{other.id}", headers=headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "super_admin_deletion_forbidden"

    def test_last_super_admin_cannot_be_deactivated(self, client, make_admin, permissions, db):
        user, headers = _root(client, make_admin, permissions)
        other = make_admin(is_superuser=True)
        assert client.post(f"{PATH}/{other.id}/deactivate", headers=headers).status_code == 200
        # `user` is now the last active one, so even another Super Admin's request must fail.
        db.expire_all()
        service = AdminManagementService(db, RequestContext(), db.get(AdminUser, other.id))
        with pytest.raises(LastSuperAdmin):
            service.deactivate(user.id)
        db.rollback()

    def test_ordinary_admin_cannot_touch_super_admin(self, client, make_admin, grant, permissions):
        root = make_admin(is_superuser=True)
        actor = make_admin()
        grant(actor, "admins.update", "admins.deactivate", "admins.delete", "admins.mfa.reset",
              "admins.password.reset", "admins.sessions.revoke", "admins.roles.manage",
              "admins.permissions.manage")
        headers = auth_headers(client, actor)
        base = f"{PATH}/{root.id}"
        calls = [
            client.patch(base, headers=headers, json={"full_name": "x"}),
            client.post(f"{base}/deactivate", headers=headers),
            client.delete(base, headers=headers),
            client.post(f"{base}/mfa/reset", headers=headers),
            client.post(f"{base}/password/reset", headers=headers),
            client.post(f"{base}/sessions/revoke", headers=headers),
        ]
        assert [call.status_code for call in calls] == [403] * 6


class TestEscalationGuards:
    def _strong_role(self, db, permissions, code):
        role = Role(name=f"R-{uuid.uuid4().hex[:6]}")
        db.add(role)
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permissions[code].id))
        db.commit()
        return role

    def test_cannot_assign_role_beyond_own_access(self, client, make_admin, grant, permissions, db):
        actor, target = make_admin(), make_admin()
        grant(actor, "admins.roles.manage")
        role = self._strong_role(db, permissions, "admins.delete")
        response = client.post(f"{PATH}/{target.id}/roles", headers=auth_headers(client, actor), json={"role_id": str(role.id)})
        assert response.status_code == 403 and response.json()["error"]["code"] == "privilege_escalation"

    def test_cannot_change_own_access(self, client, make_admin, grant, permissions, db):
        actor = make_admin()
        grant(actor, "admins.roles.manage", "admins.permissions.manage")
        headers = auth_headers(client, actor)
        role = self._strong_role(db, permissions, "admins.roles.manage")
        assert client.post(f"{PATH}/{actor.id}/roles", headers=headers, json={"role_id": str(role.id)}).status_code == 403
        assert client.put(f"{PATH}/{actor.id}/permissions/{permissions['admins.view'].id}", headers=headers, json={"effect": "ALLOW"}).status_code == 403

    def test_cannot_grant_override_beyond_own_access(self, client, make_admin, grant, permissions):
        actor, target = make_admin(), make_admin()
        grant(actor, "admins.permissions.manage")
        path = f"{PATH}/{target.id}/permissions"
        headers = auth_headers(client, actor)
        assert client.put(f"{path}/{permissions['admins.delete'].id}", headers=headers, json={"effect": "ALLOW"}).status_code == 403
        assert client.put(f"{path}/{permissions['admins.permissions.manage'].id}", headers=headers, json={"effect": "ALLOW"}).status_code == 204

    def test_cannot_take_over_stronger_peer(self, client, make_admin, grant, permissions):
        actor, stronger = make_admin(), make_admin()
        grant(actor, "admins.password.reset", "admins.update")
        grant(stronger, "admins.delete")
        headers = auth_headers(client, actor)
        response = client.post(f"{PATH}/{stronger.id}/password/reset", headers=headers)
        assert response.status_code == 403 and response.json()["error"]["code"] == "target_more_privileged"
        assert client.patch(f"{PATH}/{stronger.id}", headers=headers, json={"email": "mine@example.com"}).status_code == 403

    def test_can_manage_peer_with_subset_of_access(self, client, make_admin, grant, permissions):
        actor, weaker = make_admin(), make_admin()
        grant(actor, "admins.password.reset", "admins.view")
        grant(weaker, "admins.view")
        response = client.post(f"{PATH}/{weaker.id}/password/reset", headers=auth_headers(client, actor))
        assert response.status_code == 200 and response.json()["temporary_password"]


class TestRolesAndOverrides:
    def test_role_assignment_grants_and_removal_revokes(self, client, make_admin, permissions, db):
        target = make_admin()
        _, headers = _root(client, make_admin, permissions)
        role = client.post("/api/v1/admin-roles", headers=headers, json={
            "name": "Viewers", "permission_ids": [str(permissions["admins.view"].id)]}).json()
        assert client.post(f"{PATH}/{target.id}/roles", headers=headers, json={"role_id": role["id"]}).status_code == 204
        assert [r["name"] for r in client.get(f"{PATH}/{target.id}/roles", headers=headers).json()] == ["Viewers"]
        target_headers = auth_headers(client, target)
        assert client.get(PATH, headers=target_headers).status_code == 200
        assert client.delete(f"{PATH}/{target.id}/roles/{role['id']}", headers=headers).status_code == 204
        assert client.get(PATH, headers=target_headers).status_code == 403
        assert {"ROLE_ASSIGNED", "ROLE_REMOVED"} <= set(_actions(db))

    def test_direct_deny_beats_role_end_to_end(self, client, make_admin, permissions, db):
        target = make_admin()
        _, headers = _root(client, make_admin, permissions)
        permission_id = permissions["admins.view"].id
        role = client.post("/api/v1/admin-roles", headers=headers, json={
            "name": "Viewers", "permission_ids": [str(permission_id)]}).json()
        client.post(f"{PATH}/{target.id}/roles", headers=headers, json={"role_id": role["id"]})
        path = f"{PATH}/{target.id}/permissions/{permission_id}"
        target_headers = auth_headers(client, target)
        assert client.put(path, headers=headers, json={"effect": "DENY", "reason": "test"}).status_code == 204
        assert client.get(PATH, headers=target_headers).status_code == 403
        listed = client.get(f"{PATH}/{target.id}/permissions", headers=headers).json()
        assert listed[0]["effect"] == "DENY" and listed[0]["permission"]["code"] == "admins.view"
        assert client.delete(path, headers=headers).status_code == 204
        assert client.get(PATH, headers=target_headers).status_code == 200
        assert client.get(f"{PATH}/{target.id}/permissions/effective", headers=headers).json() == ["admins.view"]
        assert {"PERMISSION_DENIED", "PERMISSION_OVERRIDE_REMOVED"} <= set(_actions(db))

    def test_unknown_role_is_not_found(self, client, make_admin, permissions):
        target = make_admin()
        _, headers = _root(client, make_admin, permissions)
        assert client.post(f"{PATH}/{target.id}/roles", headers=headers, json={"role_id": str(uuid.uuid4())}).status_code == 404


class TestMfaManagement:
    def test_status_and_authorized_reset(self, client, make_admin, grant, permissions, db):
        target = make_admin()
        target_headers = auth_headers(client, target)
        enroll_mfa(client, target_headers)
        actor = make_admin()
        grant(actor, "admins.mfa.view_status", "admins.mfa.reset")
        headers = auth_headers(client, actor)
        status = client.get(f"{PATH}/{target.id}/mfa", headers=headers).json()
        assert status["enabled"] is True and status["recovery_codes_remaining"] == 10
        assert "secret" not in str(status)
        assert client.post(f"{PATH}/{target.id}/mfa/reset", headers=headers).status_code == 204
        db.expire_all()
        stored = db.get(AdminUser, target.id)
        assert not stored.mfa_enabled and stored.mfa_secret_encrypted is None
        assert stored.mfa_enrollment_required is True
        assert client.get(ME, headers=target_headers).status_code == 401
        assert client.get(f"{PATH}/{target.id}/mfa", headers=headers).json()["recovery_codes_remaining"] == 0
        assert "MFA_RESET" in _actions(db)
        body = login(client, target).json()
        assert body["status"] == "mfa_enrollment_required"
        fresh = {"Authorization": f"Bearer {body['access_token']}"}
        assert client.get("/api/v1/auth/sessions", headers=fresh).status_code == 403
        enroll_mfa(client, fresh, PASSWORD)
        assert client.get("/api/v1/auth/sessions", headers=fresh).status_code == 200

    def test_reset_requires_permission(self, client, make_admin, grant, permissions):
        target = make_admin()
        actor = make_admin()
        grant(actor, "admins.mfa.view_status")
        assert client.post(f"{PATH}/{target.id}/mfa/reset", headers=auth_headers(client, actor)).status_code == 403

    def test_super_admin_can_reset_without_explicit_permission(self, client, make_admin, permissions):
        target = make_admin()
        _, headers = _root(client, make_admin, permissions)
        enroll_mfa(client, auth_headers(client, target))
        assert client.post(f"{PATH}/{target.id}/mfa/reset", headers=headers).status_code == 204


class TestAdminSessionsAndActivity:
    def test_revoke_sessions_and_activity(self, client, make_admin, grant, permissions):
        target = make_admin()
        target_headers = auth_headers(client, target)
        _, headers = _root(client, make_admin, permissions)
        assert client.post(f"{PATH}/{target.id}/sessions/revoke", headers=headers).json() == {"revoked": 1}
        assert client.get(ME, headers=target_headers).status_code == 401
        activity = client.get(f"{PATH}/{target.id}/activity", headers=headers).json()
        assert activity["total"] >= 2
        assert {"LOGIN_SUCCESS", "SESSION_REVOKED"} <= {item["action"] for item in activity["items"]}

    def test_audit_log_endpoint_is_read_only_and_guarded(self, client, make_admin, grant, permissions):
        actor = make_admin()
        headers = auth_headers(client, actor)
        assert client.get("/api/v1/audit-logs", headers=headers).status_code == 403
        grant(actor, "audit.view")
        assert client.get("/api/v1/audit-logs", headers=headers).json()["total"] >= 1
        assert client.delete("/api/v1/audit-logs", headers=headers).status_code == 405

from tests.conftest import auth_headers

PATH = "/api/v1/dashboard/summary"


def test_requires_authentication(client):
    assert client.get(PATH).status_code == 401


def test_sections_follow_permissions(client, make_admin, grant, make_client_user):
    make_client_user()
    actor = make_admin()
    grant(actor)
    headers = auth_headers(client, actor)
    body = client.get(PATH, headers=headers).json()
    assert body["admin_count"] is None and body["user_count"] is None
    assert body["recent_activity"] is None
    grant(actor, "users.view")
    body = client.get(PATH, headers=headers).json()
    assert body["user_count"] == 1 and body["admin_count"] is None
    grant(actor, "admins.view", "audit.view")
    body = client.get(PATH, headers=headers).json()
    assert body["admin_count"] == 1 and len(body["recent_activity"]) >= 1

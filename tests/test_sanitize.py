"""Tests for HTML sanitization on input schemas."""

import uuid

BASE = "/api/v1"
AUTH = f"{BASE}/auth"
TENANTS = f"{BASE}/tenants"
PROPS = f"{BASE}/properties"


def _unique():
    return uuid.uuid4().hex[:8]


async def _register_and_token(client):
    u = _unique()
    resp = await client.post(
        f"{AUTH}/register",
        json={"email": f"s-{u}@example.com", "password": "securepass123", "full_name": "Owner", "org_name": f"Org {u}"},
    )
    assert resp.status_code == 201
    return resp.cookies.get("access_token")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestPropertySanitization:
    async def test_html_stripped_from_property_name(self, client):
        token = await _register_and_token(client)
        resp = await client.post(
            PROPS,
            json={
                "name": "<script>alert('xss')</script>My Property",
                "address_line1": "<b>123 Main St</b>",
                "city": "<em>NYC</em>",
                "type": "single_family",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "<script>" not in data["name"]
        assert data["name"] == "alert('xss')My Property"
        assert data["address_line1"] == "123 Main St"
        assert data["city"] == "NYC"


class TestTenantSanitization:
    async def test_html_stripped_from_tenant_name(self, client):
        token = await _register_and_token(client)
        resp = await client.post(
            f"{TENANTS}/invite",
            json={"email": f"t-{_unique()}@example.com", "full_name": "<img src=x>Jane Doe"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["full_name"] == "Jane Doe"


class TestAuthSanitization:
    async def test_html_stripped_from_register(self, client):
        u = _unique()
        resp = await client.post(
            f"{AUTH}/register",
            json={
                "email": f"r-{u}@example.com",
                "password": "securepass123",
                "full_name": "<script>alert(1)</script>Bob",
                "org_name": "<b>Evil Org</b>",
            },
        )
        assert resp.status_code == 201
        data = resp.json()["user"]
        assert data["full_name"] == "alert(1)Bob"

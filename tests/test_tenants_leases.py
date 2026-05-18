"""Sprint 3 — Tenants + Leases endpoint tests."""

import uuid
from datetime import date, timedelta

BASE = "/api/v1"
AUTH = f"{BASE}/auth"
TENANTS = f"{BASE}/tenants"
LEASES = f"{BASE}/leases"
PROPS = f"{BASE}/properties"


def _unique():
    return uuid.uuid4().hex[:8]


async def _register_and_token(client):
    u = _unique()
    resp = await client.post(
        f"{AUTH}/register",
        json={"email": f"t-{u}@example.com", "password": "securepass123", "full_name": "Owner", "org_name": f"Org {u}"},
    )
    assert resp.status_code == 201
    return resp.cookies.get("access_token")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _create_property(client, token):
    resp = await client.post(
        PROPS,
        json={"name": "Test Prop", "address_line1": "1 Main St", "city": "NYC", "type": "multi_unit"},
        headers=_auth(token),
    )
    return resp.json()["id"]


async def _create_unit(client, token, prop_id):
    resp = await client.post(
        f"{PROPS}/{prop_id}/units",
        json={"label": f"U-{_unique()}", "monthly_rent": 1000, "status": "vacant"},
        headers=_auth(token),
    )
    return resp.json()["id"]


async def _invite_tenant(client, token):
    u = _unique()
    resp = await client.post(
        f"{TENANTS}/invite",
        json={"email": f"tenant-{u}@example.com", "full_name": f"Tenant {u}"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _lease_data(unit_id, tenant_id):
    today = date.today()
    return {
        "unit_id": unit_id,
        "tenant_ids": [tenant_id],
        "primary_tenant_id": tenant_id,
        "start_date": str(today),
        "end_date": str(today + timedelta(days=365)),
        "monthly_rent": 1200,
        "security_deposit": 1200,
        "payment_due_day": 1,
    }


# -- Tenants --


class TestInviteTenant:
    async def test_invite_success(self, client):
        token = await _register_and_token(client)
        u = _unique()
        resp = await client.post(
            f"{TENANTS}/invite",
            json={"email": f"t-{u}@example.com", "full_name": "Jane Doe"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "tenant"
        assert data["is_active"] is True

    async def test_invite_duplicate_email(self, client):
        token = await _register_and_token(client)
        email = f"dup-{_unique()}@example.com"
        await client.post(f"{TENANTS}/invite", json={"email": email, "full_name": "A"}, headers=_auth(token))
        resp = await client.post(f"{TENANTS}/invite", json={"email": email, "full_name": "B"}, headers=_auth(token))
        assert resp.status_code == 409

    async def test_invite_no_auth(self, client):
        resp = await client.post(f"{TENANTS}/invite", json={"email": "x@x.com", "full_name": "X"})
        assert resp.status_code == 403


class TestListTenants:
    async def test_list_empty(self, client):
        token = await _register_and_token(client)
        resp = await client.get(TENANTS, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 0

    async def test_list_with_tenants(self, client):
        token = await _register_and_token(client)
        await _invite_tenant(client, token)
        await _invite_tenant(client, token)
        resp = await client.get(TENANTS, headers=_auth(token))
        assert resp.json()["meta"]["total"] == 2

    async def test_list_search(self, client):
        token = await _register_and_token(client)
        u = _unique()
        payload = {"email": f"findme-{u}@example.com", "full_name": "Findable"}
        await client.post(f"{TENANTS}/invite", json=payload, headers=_auth(token))
        resp = await client.get(TENANTS, params={"search": "Findable"}, headers=_auth(token))
        assert resp.json()["meta"]["total"] == 1


class TestGetTenant:
    async def test_get_success(self, client):
        token = await _register_and_token(client)
        tid = await _invite_tenant(client, token)
        resp = await client.get(f"{TENANTS}/{tid}", headers=_auth(token))
        assert resp.status_code == 200
        assert "lease_history" in resp.json()

    async def test_get_not_found(self, client):
        token = await _register_and_token(client)
        resp = await client.get(f"{TENANTS}/{uuid.uuid4()}", headers=_auth(token))
        assert resp.status_code == 404


class TestUpdateTenant:
    async def test_update_name(self, client):
        token = await _register_and_token(client)
        tid = await _invite_tenant(client, token)
        resp = await client.put(f"{TENANTS}/{tid}", json={"full_name": "Updated Name"}, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"


class TestDeactivateTenant:
    async def test_deactivate(self, client):
        token = await _register_and_token(client)
        tid = await _invite_tenant(client, token)
        resp = await client.patch(f"{TENANTS}/{tid}/deactivate", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


# -- Leases --


class TestCreateLease:
    async def test_create_success(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        resp = await client.post(LEASES, json=_lease_data(unit_id, tenant_id), headers=_auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["unit_id"] == unit_id

    async def test_create_end_before_start(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        data = _lease_data(unit_id, tenant_id)
        data["end_date"] = str(date.today() - timedelta(days=1))
        resp = await client.post(LEASES, json=data, headers=_auth(token))
        assert resp.status_code == 422

    async def test_create_bad_unit(self, client):
        token = await _register_and_token(client)
        tenant_id = await _invite_tenant(client, token)
        data = _lease_data(str(uuid.uuid4()), tenant_id)
        resp = await client.post(LEASES, json=data, headers=_auth(token))
        assert resp.status_code == 404


class TestListLeases:
    async def test_list_empty(self, client):
        token = await _register_and_token(client)
        resp = await client.get(LEASES, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 0

    async def test_list_with_leases(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        await client.post(LEASES, json=_lease_data(unit_id, tenant_id), headers=_auth(token))
        resp = await client.get(LEASES, headers=_auth(token))
        assert resp.json()["meta"]["total"] == 1


class TestGetLease:
    async def test_get_detail(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        create_resp = await client.post(LEASES, json=_lease_data(unit_id, tenant_id), headers=_auth(token))
        lease_id = create_resp.json()["id"]
        resp = await client.get(f"{LEASES}/{lease_id}", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tenants"]) == 1
        assert data["tenants"][0]["is_primary"] is True
        assert data["unit_label"] is not None
        assert data["property_name"] == "Test Prop"


class TestUpdateLease:
    async def test_update_draft(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        create_resp = await client.post(LEASES, json=_lease_data(unit_id, tenant_id), headers=_auth(token))
        lease_id = create_resp.json()["id"]
        resp = await client.put(f"{LEASES}/{lease_id}", json={"monthly_rent": 1500}, headers=_auth(token))
        assert resp.status_code == 200
        assert float(resp.json()["monthly_rent"]) == 1500.0

    async def test_update_active_fails(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        create_resp = await client.post(LEASES, json=_lease_data(unit_id, tenant_id), headers=_auth(token))
        lease_id = create_resp.json()["id"]
        await client.patch(f"{LEASES}/{lease_id}/activate", headers=_auth(token))
        resp = await client.put(f"{LEASES}/{lease_id}", json={"monthly_rent": 9999}, headers=_auth(token))
        assert resp.status_code == 400


class TestActivateLease:
    async def test_activate_success(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        create_resp = await client.post(LEASES, json=_lease_data(unit_id, tenant_id), headers=_auth(token))
        lease_id = create_resp.json()["id"]
        resp = await client.patch(f"{LEASES}/{lease_id}/activate", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        # Unit should now be occupied
        unit_resp = await client.get(f"{BASE}/units/{unit_id}", headers=_auth(token))
        assert unit_resp.json()["status"] == "occupied"

    async def test_activate_non_draft_fails(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        create_resp = await client.post(LEASES, json=_lease_data(unit_id, tenant_id), headers=_auth(token))
        lease_id = create_resp.json()["id"]
        await client.patch(f"{LEASES}/{lease_id}/activate", headers=_auth(token))
        resp = await client.patch(f"{LEASES}/{lease_id}/activate", headers=_auth(token))
        assert resp.status_code == 400


class TestTerminateLease:
    async def test_terminate_success(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        create_resp = await client.post(LEASES, json=_lease_data(unit_id, tenant_id), headers=_auth(token))
        lease_id = create_resp.json()["id"]
        await client.patch(f"{LEASES}/{lease_id}/activate", headers=_auth(token))
        resp = await client.patch(
            f"{LEASES}/{lease_id}/terminate",
            json={"termination_date": str(date.today()), "reason": "Early move-out"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "terminated"
        # Unit should now be vacant
        unit_resp = await client.get(f"{BASE}/units/{unit_id}", headers=_auth(token))
        assert unit_resp.json()["status"] == "vacant"


class TestRenewLease:
    async def test_renew_success(self, client):
        token = await _register_and_token(client)
        prop_id = await _create_property(client, token)
        unit_id = await _create_unit(client, token, prop_id)
        tenant_id = await _invite_tenant(client, token)
        create_resp = await client.post(LEASES, json=_lease_data(unit_id, tenant_id), headers=_auth(token))
        lease_id = create_resp.json()["id"]
        await client.patch(f"{LEASES}/{lease_id}/activate", headers=_auth(token))
        today = date.today()
        resp = await client.post(
            f"{LEASES}/{lease_id}/renew",
            json={
                "start_date": str(today + timedelta(days=365)),
                "end_date": str(today + timedelta(days=730)),
                "monthly_rent": 1300,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["renewed_from_lease_id"] == lease_id
        assert float(data["monthly_rent"]) == 1300.0

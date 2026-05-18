"""Sprint 2 — Properties + Units endpoint tests."""

import uuid

BASE = "/api/v1"
AUTH = f"{BASE}/auth"
PROPS = f"{BASE}/properties"


def _unique_payload():
    u = uuid.uuid4().hex[:8]
    return {
        "email": f"test-{u}@example.com",
        "password": "securepass123",
        "full_name": "Test User",
        "org_name": f"Test Org {u}",
    }


async def _register_and_token(client):
    payload = _unique_payload()
    resp = await client.post(f"{AUTH}/register", json=payload)
    assert resp.status_code == 201
    return resp.cookies.get("access_token")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


PROP_DATA = {
    "name": "Sunset Apartments",
    "type": "multi_unit",
    "address_line1": "123 Sunset Blvd",
    "city": "Los Angeles",
    "state": "CA",
    "postal_code": "90028",
    "year_built": 2005,
}

UNIT_DATA = {
    "label": "Unit A",
    "bedrooms": 2,
    "bathrooms": 1,
    "sqft": 850,
    "monthly_rent": 1200,
    "security_deposit": 1200,
    "status": "vacant",
}


# -- Properties CRUD --


class TestCreateProperty:
    async def test_create_success(self, client):
        token = await _register_and_token(client)
        resp = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == PROP_DATA["name"]
        assert data["type"] == "multi_unit"
        assert data["city"] == "Los Angeles"
        assert data["is_archived"] is False

    async def test_create_missing_name(self, client):
        token = await _register_and_token(client)
        resp = await client.post(PROPS, json={"city": "X", "address_line1": "Y"}, headers=_auth(token))
        assert resp.status_code == 422

    async def test_create_no_auth(self, client):
        resp = await client.post(PROPS, json=PROP_DATA)
        assert resp.status_code == 403


class TestListProperties:
    async def test_list_empty(self, client):
        token = await _register_and_token(client)
        resp = await client.get(PROPS, headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["meta"]["total"] == 0

    async def test_list_with_properties(self, client):
        token = await _register_and_token(client)
        await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        await client.post(PROPS, json={**PROP_DATA, "name": "Another Place"}, headers=_auth(token))
        resp = await client.get(PROPS, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 2

    async def test_list_search(self, client):
        token = await _register_and_token(client)
        await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        await client.post(PROPS, json={**PROP_DATA, "name": "Ocean View"}, headers=_auth(token))
        resp = await client.get(PROPS, params={"search": "Ocean"}, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 1

    async def test_list_filter_by_type(self, client):
        token = await _register_and_token(client)
        await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        await client.post(PROPS, json={**PROP_DATA, "name": "House", "type": "single_family"}, headers=_auth(token))
        resp = await client.get(PROPS, params={"type": "single_family"}, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 1
        assert resp.json()["items"][0]["name"] == "House"


class TestGetProperty:
    async def test_get_success(self, client):
        token = await _register_and_token(client)
        create_resp = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = create_resp.json()["id"]
        resp = await client.get(f"{PROPS}/{prop_id}", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == PROP_DATA["name"]
        assert "units_summary" in data
        assert data["units_summary"]["total"] == 0

    async def test_get_not_found(self, client):
        token = await _register_and_token(client)
        fake_id = uuid.uuid4()
        resp = await client.get(f"{PROPS}/{fake_id}", headers=_auth(token))
        assert resp.status_code == 404


class TestUpdateProperty:
    async def test_update_success(self, client):
        token = await _register_and_token(client)
        create_resp = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = create_resp.json()["id"]
        resp = await client.put(f"{PROPS}/{prop_id}", json={"name": "New Name"}, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    async def test_update_not_found(self, client):
        token = await _register_and_token(client)
        fake_id = uuid.uuid4()
        resp = await client.put(f"{PROPS}/{fake_id}", json={"name": "X"}, headers=_auth(token))
        assert resp.status_code == 404


class TestArchiveProperty:
    async def test_archive_success(self, client):
        token = await _register_and_token(client)
        create_resp = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = create_resp.json()["id"]
        resp = await client.delete(f"{PROPS}/{prop_id}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["is_archived"] is True

    async def test_archived_hidden_from_list(self, client):
        token = await _register_and_token(client)
        create_resp = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = create_resp.json()["id"]
        await client.delete(f"{PROPS}/{prop_id}", headers=_auth(token))
        resp = await client.get(PROPS, headers=_auth(token))
        assert resp.json()["meta"]["total"] == 0


# -- Units CRUD --


class TestCreateUnit:
    async def test_create_success(self, client):
        token = await _register_and_token(client)
        prop = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = prop.json()["id"]
        resp = await client.post(f"{PROPS}/{prop_id}/units", json=UNIT_DATA, headers=_auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["label"] == "Unit A"
        assert data["property_id"] == prop_id
        assert float(data["monthly_rent"]) == 1200.0

    async def test_create_unit_bad_property(self, client):
        token = await _register_and_token(client)
        fake_id = uuid.uuid4()
        resp = await client.post(f"{PROPS}/{fake_id}/units", json=UNIT_DATA, headers=_auth(token))
        assert resp.status_code == 404


class TestListUnits:
    async def test_list_units(self, client):
        token = await _register_and_token(client)
        prop = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = prop.json()["id"]
        await client.post(f"{PROPS}/{prop_id}/units", json=UNIT_DATA, headers=_auth(token))
        await client.post(f"{PROPS}/{prop_id}/units", json={**UNIT_DATA, "label": "Unit B"}, headers=_auth(token))
        resp = await client.get(f"{PROPS}/{prop_id}/units", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 2


class TestGetUnit:
    async def test_get_unit(self, client):
        token = await _register_and_token(client)
        prop = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = prop.json()["id"]
        unit = await client.post(f"{PROPS}/{prop_id}/units", json=UNIT_DATA, headers=_auth(token))
        unit_id = unit.json()["id"]
        resp = await client.get(f"{BASE}/units/{unit_id}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["label"] == "Unit A"

    async def test_get_unit_not_found(self, client):
        token = await _register_and_token(client)
        fake_id = uuid.uuid4()
        resp = await client.get(f"{BASE}/units/{fake_id}", headers=_auth(token))
        assert resp.status_code == 404


class TestUpdateUnit:
    async def test_update_unit(self, client):
        token = await _register_and_token(client)
        prop = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = prop.json()["id"]
        unit = await client.post(f"{PROPS}/{prop_id}/units", json=UNIT_DATA, headers=_auth(token))
        unit_id = unit.json()["id"]
        resp = await client.put(f"{BASE}/units/{unit_id}", json={"label": "Unit Z"}, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["label"] == "Unit Z"


class TestArchiveUnit:
    async def test_archive_unit(self, client):
        token = await _register_and_token(client)
        prop = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = prop.json()["id"]
        unit = await client.post(f"{PROPS}/{prop_id}/units", json=UNIT_DATA, headers=_auth(token))
        unit_id = unit.json()["id"]
        resp = await client.delete(f"{BASE}/units/{unit_id}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["is_archived"] is True


class TestUnitsSummary:
    async def test_property_detail_shows_summary(self, client):
        token = await _register_and_token(client)
        prop = await client.post(PROPS, json=PROP_DATA, headers=_auth(token))
        prop_id = prop.json()["id"]
        await client.post(f"{PROPS}/{prop_id}/units", json=UNIT_DATA, headers=_auth(token))
        await client.post(
            f"{PROPS}/{prop_id}/units",
            json={**UNIT_DATA, "label": "Unit B", "status": "occupied", "monthly_rent": 1500},
            headers=_auth(token),
        )
        resp = await client.get(f"{PROPS}/{prop_id}", headers=_auth(token))
        assert resp.status_code == 200
        summary = resp.json()["units_summary"]
        assert summary["total"] == 2
        assert summary["occupied"] == 1
        assert summary["vacant"] == 1
        assert float(summary["monthly_rent_roll"]) == 2700.0

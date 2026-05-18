"""Sprint 1 — Auth endpoint tests."""

BASE = "/api/v1/auth"


# -- Register --


class TestRegister:
    async def test_register_success(self, client, register_payload):
        resp = await client.post(f"{BASE}/register", json=register_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["email"] == register_payload["email"]
        assert data["user"]["role"] == "landlord"
        assert data["user"]["full_name"] == register_payload["full_name"]
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_register_creates_org(self, client, register_payload):
        resp = await client.post(f"{BASE}/register", json=register_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["org_id"] is not None

    async def test_register_missing_fields(self, client):
        resp = await client.post(f"{BASE}/register", json={"email": "a@b.com"})
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client):
        resp = await client.post(
            f"{BASE}/register",
            json={"email": "not-an-email", "password": "12345678", "full_name": "X", "org_name": "Y"},
        )
        assert resp.status_code == 422

    async def test_register_short_password(self, client):
        resp = await client.post(
            f"{BASE}/register",
            json={"email": "ok@ok.com", "password": "short", "full_name": "X", "org_name": "Y"},
        )
        assert resp.status_code == 422


# -- Login --


class TestLogin:
    async def test_login_success(self, client, register_payload):
        await client.post(f"{BASE}/register", json=register_payload)
        resp = await client.post(
            f"{BASE}/login",
            json={"email": register_payload["email"], "password": register_payload["password"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == register_payload["email"]
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password(self, client, register_payload):
        await client.post(f"{BASE}/register", json=register_payload)
        resp = await client.post(
            f"{BASE}/login",
            json={"email": register_payload["email"], "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    async def test_login_nonexistent_user(self, client):
        resp = await client.post(
            f"{BASE}/login",
            json={"email": "noone@nowhere.com", "password": "whatever123"},
        )
        assert resp.status_code == 401

    async def test_login_missing_fields(self, client):
        resp = await client.post(f"{BASE}/login", json={"email": "a@b.com"})
        assert resp.status_code == 422


# -- Me --


class TestMe:
    async def test_me_authenticated(self, client, register_payload):
        reg = await client.post(f"{BASE}/register", json=register_payload)
        token = reg.json()["access_token"]
        resp = await client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == register_payload["email"]
        assert data["role"] == "landlord"

    async def test_me_no_token(self, client):
        resp = await client.get(f"{BASE}/me")
        assert resp.status_code == 403

    async def test_me_invalid_token(self, client):
        resp = await client.get(f"{BASE}/me", headers={"Authorization": "Bearer garbage.token.here"})
        assert resp.status_code == 401


# -- Refresh --


class TestRefresh:
    async def test_refresh_success(self, client, register_payload):
        reg = await client.post(f"{BASE}/register", json=register_payload)
        refresh_token = reg.json()["refresh_token"]
        resp = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # New refresh token should differ (rotation)
        assert data["refresh_token"] != refresh_token

    async def test_refresh_reuse_revoked(self, client, register_payload):
        """Using a refresh token twice should fail (it's revoked after first use)."""
        reg = await client.post(f"{BASE}/register", json=register_payload)
        refresh_token = reg.json()["refresh_token"]
        # First use — works
        await client.post(f"{BASE}/refresh", json={"refresh_token": refresh_token})
        # Second use — should fail
        resp = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    async def test_refresh_invalid_token(self, client):
        resp = await client.post(f"{BASE}/refresh", json={"refresh_token": "not.a.real.token"})
        assert resp.status_code == 401


# -- Logout --


class TestLogout:
    async def test_logout_success(self, client, register_payload):
        reg = await client.post(f"{BASE}/register", json=register_payload)
        token = reg.json()["access_token"]
        resp = await client.post(f"{BASE}/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out successfully"

    async def test_logout_revokes_refresh_tokens(self, client, register_payload):
        reg = await client.post(f"{BASE}/register", json=register_payload)
        access = reg.json()["access_token"]
        refresh = reg.json()["refresh_token"]
        # Logout
        await client.post(f"{BASE}/logout", headers={"Authorization": f"Bearer {access}"})
        # Refresh should fail now
        resp = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 401

    async def test_logout_no_auth(self, client):
        resp = await client.post(f"{BASE}/logout")
        assert resp.status_code == 403


# -- Magic Link --


class TestMagicLink:
    async def test_magic_link_request_returns_success(self, client, register_payload):
        """Should always return success (even for non-existent emails) to prevent enumeration."""
        await client.post(f"{BASE}/register", json=register_payload)
        resp = await client.post(f"{BASE}/magic-link", json={"email": register_payload["email"]})
        assert resp.status_code == 200
        assert "magic link" in resp.json()["message"].lower()

    async def test_magic_link_nonexistent_email(self, client):
        resp = await client.post(f"{BASE}/magic-link", json={"email": "ghost@nowhere.com"})
        assert resp.status_code == 200  # No enumeration

    async def test_magic_link_verify_invalid_token(self, client):
        resp = await client.post(f"{BASE}/magic-link/verify", json={"token": "bogus-token"})
        assert resp.status_code == 401


# -- Forgot Password --


class TestForgotPassword:
    async def test_forgot_password_returns_success(self, client, register_payload):
        await client.post(f"{BASE}/register", json=register_payload)
        resp = await client.post(f"{BASE}/forgot-password", json={"email": register_payload["email"]})
        assert resp.status_code == 200
        assert "reset link" in resp.json()["message"].lower()

    async def test_forgot_password_nonexistent_email(self, client):
        resp = await client.post(f"{BASE}/forgot-password", json={"email": "ghost@nowhere.com"})
        assert resp.status_code == 200  # No enumeration


# -- Reset Password --


class TestResetPassword:
    async def test_reset_password_invalid_token(self, client):
        resp = await client.post(
            f"{BASE}/reset-password",
            json={"token": "fake-token", "new_password": "newpass1234"},
        )
        assert resp.status_code == 401

    async def test_reset_password_short_password(self, client):
        resp = await client.post(
            f"{BASE}/reset-password",
            json={"token": "fake-token", "new_password": "short"},
        )
        assert resp.status_code == 422


# -- Health / Ready --


class TestHealth:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_ready(self, client):
        resp = await client.get("/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready"}

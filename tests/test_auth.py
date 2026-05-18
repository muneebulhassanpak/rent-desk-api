"""Sprint 1 — Auth endpoint tests (cookie-based auth)."""

BASE = "/api/v1/auth"


def _get_access_token(resp):
    """Extract access token from response cookies."""
    return resp.cookies.get("access_token")


def _get_refresh_token(resp):
    """Extract refresh token from response cookies."""
    return resp.cookies.get("refresh_token")


# -- Register --


class TestRegister:
    async def test_register_success(self, client, register_payload):
        resp = await client.post(f"{BASE}/register", json=register_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["email"] == register_payload["email"]
        assert data["user"]["role"] == "landlord"
        assert data["user"]["full_name"] == register_payload["full_name"]
        # Tokens in JSON body (backward compat)
        assert "access_token" in data
        assert "refresh_token" in data
        # Tokens also set as httpOnly cookies
        assert _get_access_token(resp) is not None
        assert _get_refresh_token(resp) is not None

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
        assert _get_access_token(resp) is not None
        assert _get_refresh_token(resp) is not None

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
    async def test_me_via_cookie(self, client, register_payload):
        """Auth via httpOnly cookie (browser flow)."""
        reg = await client.post(f"{BASE}/register", json=register_payload)
        token = _get_access_token(reg)
        resp = await client.get(f"{BASE}/me", cookies={"access_token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == register_payload["email"]
        assert data["role"] == "landlord"

    async def test_me_via_header(self, client, register_payload):
        """Auth via Authorization header (API/mobile flow)."""
        reg = await client.post(f"{BASE}/register", json=register_payload)
        token = reg.json()["access_token"]
        resp = await client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == register_payload["email"]

    async def test_me_no_token(self, client):
        resp = await client.get(f"{BASE}/me")
        assert resp.status_code == 403

    async def test_me_invalid_token(self, client):
        resp = await client.get(f"{BASE}/me", headers={"Authorization": "Bearer garbage.token.here"})
        assert resp.status_code == 401


# -- Refresh --


class TestRefresh:
    async def test_refresh_via_cookie(self, client, register_payload):
        reg = await client.post(f"{BASE}/register", json=register_payload)
        refresh = _get_refresh_token(reg)
        resp = await client.post(f"{BASE}/refresh", cookies={"refresh_token": refresh})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # New cookies set
        assert _get_access_token(resp) is not None
        assert _get_refresh_token(resp) is not None

    async def test_refresh_reuse_revoked(self, client, register_payload):
        """Using a refresh token twice should fail (it's revoked after first use)."""
        reg = await client.post(f"{BASE}/register", json=register_payload)
        refresh = _get_refresh_token(reg)
        # First use — works
        await client.post(f"{BASE}/refresh", cookies={"refresh_token": refresh})
        # Second use — should fail
        resp = await client.post(f"{BASE}/refresh", cookies={"refresh_token": refresh})
        assert resp.status_code == 401

    async def test_refresh_no_token(self, client):
        resp = await client.post(f"{BASE}/refresh")
        assert resp.status_code == 401


# -- Logout --


class TestLogout:
    async def test_logout_success(self, client, register_payload):
        reg = await client.post(f"{BASE}/register", json=register_payload)
        token = _get_access_token(reg)
        resp = await client.post(f"{BASE}/logout", cookies={"access_token": token})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out successfully"

    async def test_logout_clears_cookies(self, client, register_payload):
        reg = await client.post(f"{BASE}/register", json=register_payload)
        token = _get_access_token(reg)
        resp = await client.post(f"{BASE}/logout", cookies={"access_token": token})
        # Cookies should be cleared (max-age=0)
        for cookie_header in resp.headers.get_list("set-cookie"):
            if "access_token" in cookie_header or "refresh_token" in cookie_header:
                assert "Max-Age=0" in cookie_header or "max-age=0" in cookie_header

    async def test_logout_revokes_refresh_tokens(self, client, register_payload):
        reg = await client.post(f"{BASE}/register", json=register_payload)
        access = _get_access_token(reg)
        refresh = _get_refresh_token(reg)
        # Logout
        await client.post(f"{BASE}/logout", cookies={"access_token": access})
        # Refresh should fail now
        resp = await client.post(f"{BASE}/refresh", cookies={"refresh_token": refresh})
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

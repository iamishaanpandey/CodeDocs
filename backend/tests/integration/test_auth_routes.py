import pytest

@pytest.mark.asyncio
class TestRegister:
    async def test_successful_registration(self, client):
        response = await client.post("/api/auth/register", json={
            "email": "new@example.com", "name": "New User", "password": "password123"
        })
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "new@example.com"
        assert "hashed_password" not in data["user"]

    async def test_duplicate_email_returns_409(self, client, test_user):
        response = await client.post("/api/auth/register", json={
            "email": test_user.email, "name": "Duplicate", "password": "password123"
        })
        assert response.status_code == 409

    async def test_short_password_returns_422(self, client):
        response = await client.post("/api/auth/register", json={
            "email": "test2@example.com", "name": "User", "password": "short"
        })
        assert response.status_code == 422

    async def test_invalid_email_returns_422(self, client):
        response = await client.post("/api/auth/register", json={
            "email": "notanemail", "name": "User", "password": "password123"
        })
        assert response.status_code == 422

@pytest.mark.asyncio
class TestLogin:
    async def test_correct_credentials_return_tokens(self, client, test_user):
        response = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "testpassword123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_wrong_password_returns_401(self, client, test_user):
        response = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "wrongpassword"
        })
        assert response.status_code == 401

    async def test_unknown_email_returns_401(self, client):
        response = await client.post("/api/auth/login", json={
            "email": "nobody@example.com", "password": "password123"
        })
        assert response.status_code == 401

    async def test_error_message_does_not_reveal_which_field_wrong(self, client, test_user):
        wrong_pw = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "wrong"
        })
        wrong_email = await client.post("/api/auth/login", json={
            "email": "nobody@example.com", "password": "testpassword123"
        })
        assert wrong_pw.json()["detail"] == wrong_email.json()["detail"]

@pytest.mark.asyncio
class TestRefreshToken:
    async def test_valid_refresh_returns_new_access_token(self, client, test_user):
        login = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "testpassword123"
        })
        refresh_token = login.json()["refresh_token"]
        response = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_access_token_rejected_as_refresh(self, client, test_user):
        login = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "testpassword123"
        })
        access_token = login.json()["access_token"]
        response = await client.post("/api/auth/refresh", json={"refresh_token": access_token})
        assert response.status_code == 401

@pytest.mark.asyncio
class TestGetMe:
    async def test_valid_token_returns_user(self, client, test_user, auth_headers):
        response = await client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == test_user.email

    async def test_missing_token_returns_401(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_invalid_token_returns_401(self, client):
        response = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        assert response.status_code == 401

@pytest.mark.asyncio
class TestLogout:
    async def test_logout_succeeds(self, client, test_user):
        login = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "testpassword123"
        })
        refresh_token = login.json()["refresh_token"]
        response = await client.post("/api/auth/logout", json={"refresh_token": refresh_token})
        assert response.status_code == 200

    async def test_blacklisted_token_cannot_refresh(self, client, test_user):
        login = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "testpassword123"
        })
        refresh_token = login.json()["refresh_token"]
        await client.post("/api/auth/logout", json={"refresh_token": refresh_token})
        refresh = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh.status_code == 401

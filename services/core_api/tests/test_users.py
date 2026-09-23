import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_register_returns_jwt_pair(api_client):
    url = reverse("user-register")
    response = api_client.post(
        url,
        {
            "email": "new.user@example.com",
            "password": "StrongPassw0rd!",
            "first_name": "New",
            "last_name": "User",
        },
    )

    assert response.status_code == 201
    assert "access" in response.data
    assert "refresh" in response.data
    assert response.data["user"]["email"] == "new.user@example.com"


def test_register_rejects_weak_password(api_client):
    url = reverse("user-register")
    response = api_client.post(url, {"email": "weak@example.com", "password": "123"})

    assert response.status_code == 400


def test_me_requires_authentication(api_client):
    response = api_client.get(reverse("user-me"))
    assert response.status_code == 401


def test_me_returns_current_user(auth_client, user):
    response = auth_client.get(reverse("user-me"))
    assert response.status_code == 200
    assert response.data["email"] == user.email

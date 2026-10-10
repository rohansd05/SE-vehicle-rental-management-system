"""Shared helpers for API tests."""

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

REGISTRATION = {
    "email": "asha@example.com",
    "password": "Str0ng!Passw0rd",
    "name": "Asha Rao",
    "mobile_no": "+919812345678",
    "address": "14 Hill Road, Bandra (W), Mumbai 400050",
    "date_of_birth": "1996-04-12",
    "emergency_contact_name": "Ravi Rao",
    "emergency_contact_mobile": "+919812300000",
}


def authenticated_client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client

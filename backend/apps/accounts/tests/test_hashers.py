"""SE-2 / D4: passwords are hashed with bcrypt, work factor >= 12."""

import pytest
from django.conf import settings
from django.contrib.auth.hashers import BCryptSHA256PasswordHasher, get_hashers, identify_hasher

from apps.accounts.tests.factories import UserFactory


def test_first_hasher_is_bcrypt_with_at_least_12_rounds():
    first = get_hashers()[0]
    assert settings.PASSWORD_HASHERS[0] == (
        "apps.accounts.hashers.BCryptSHA256Rounds12PasswordHasher"
    )
    assert isinstance(first, BCryptSHA256PasswordHasher)
    assert first.rounds >= 12


@pytest.mark.django_db
def test_stored_password_is_bcrypt_hash_with_at_least_12_rounds():
    user = UserFactory(password="Str0ng!Passw0rd")
    hasher = identify_hasher(user.password)
    assert hasher.algorithm == "bcrypt_sha256"
    assert hasher.decode(user.password)["work_factor"] >= 12
    assert "Str0ng!Passw0rd" not in user.password
    assert user.check_password("Str0ng!Passw0rd")

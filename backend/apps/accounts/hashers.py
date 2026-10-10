"""Password hashing (SE-2, D4)."""

from django.contrib.auth.hashers import BCryptSHA256PasswordHasher


class BCryptSHA256Rounds12PasswordHasher(BCryptSHA256PasswordHasher):
    """bcrypt (SHA-256 pre-hashed) with a work factor of 12.

    SE-2: passwords are stored only as salted bcrypt hashes with a work factor
    of at least 12. The value is pinned here so a Django upgrade can never
    silently change it. The algorithm name is inherited ("bcrypt_sha256"), so
    hashes stay interchangeable with Django's own hasher.
    """

    rounds = 12

"""pytest settings (DJANGO_SETTINGS_MODULE=config.settings.test).

Tests use the Docker PostgreSQL, because the booking ExclusionConstraint
cannot be exercised on SQLite. External services are always the mocks.
"""

from .base import *  # noqa: F403

DEBUG = False

PAYMENT_GATEWAY_BACKEND = "mock"
NOTIFICATION_BACKEND = "mock"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Per-process cache in tests; conftest clears it between tests.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

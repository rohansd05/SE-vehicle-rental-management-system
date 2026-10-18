"""Production: one Azure VM, docker-compose, gunicorn behind Caddy (D1).

Caddy terminates TLS (CO-1), redirects HTTP to HTTPS, serves the React
build and Django's collected static files, and reverse-proxies /api and
/admin to gunicorn. Every value below that varies per deployment comes from
backend/.env (docker-compose.prod.yml passes it to Django, the Celery worker
and Celery Beat alike); deploy/README-deploy.md lists them.
"""

from .base import *  # noqa: F403
from .base import env

DEBUG = False
# D12: the schema and Swagger UI stay administrators only (base.py's default).
API_DOCS_PUBLIC = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
# The browser sees one origin (https://SITE_HOSTNAME), so CORS stays closed:
# django-cors-headers is not installed (D1) and Django sends no
# Access-Control-Allow-Origin, so no other origin can read an API response.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# Caddy sets X-Forwarded-Proto and X-Forwarded-Host itself (it drops what the
# client sent), and gunicorn is reachable only from Caddy on the compose
# network, so both headers are trusted. Signed file links
# (build_absolute_uri, SI-3) then read https://SITE_HOSTNAME.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
# Caddy already redirects HTTP to HTTPS. Leaving this off lets container
# health checks reach gunicorn over plain HTTP on the internal network.
SECURE_SSL_REDIRECT = False

# SE-1, CO-1: cookies travel over HTTPS only; the refresh cookie (D21) is
# Secure through base.py's AUTH_REFRESH_COOKIE_SECURE.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False  # a borrowed sslip.io name must never enter the preload list
# `manage.py check --deploy`: W008 (Caddy redirects to HTTPS) and W021 (no preload) are by design.
SILENCED_SYSTEM_CHECKS = ["security.W008", "security.W021"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

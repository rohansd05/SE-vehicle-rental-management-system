"""Celery application.

Broker and result backend both come from REDIS_URL (Valkey, D2), exposed in
settings as CELERY_BROKER_URL and CELERY_RESULT_BACKEND.

On Windows the worker needs the solo pool:
    celery -A config worker -l info --pool=solo
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("vrms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

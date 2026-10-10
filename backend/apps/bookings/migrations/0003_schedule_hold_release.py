"""Book.Hold.Expire: schedule apps.bookings.tasks.release_expired_holds every minute.

Celery Beat uses the database scheduler (CELERY_BEAT_SCHEDULER), so the
schedule is data. Bookings also release expired holds when they are touched,
so the sweep only keeps search results current between bookings.
"""

from django.db import migrations

TASK_NAME = "Release expired booking holds (Book.Hold.Expire)"
TASK = "apps.bookings.tasks.release_expired_holds"


def schedule(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    every_minute, _ = IntervalSchedule.objects.get_or_create(every=1, period="minutes")
    PeriodicTask.objects.update_or_create(
        name=TASK_NAME, defaults={"task": TASK, "interval": every_minute, "enabled": True}
    )


def unschedule(apps, schema_editor):
    apps.get_model("django_celery_beat", "PeriodicTask").objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0002_rating_and_discount"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(schedule, unschedule)]

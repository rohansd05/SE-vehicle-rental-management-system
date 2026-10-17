"""Appendix B No-show: schedule apps.bookings.tasks.declare_no_shows every minute.

Like 0003 (Book.Hold.Expire), the schedule is data for the database
scheduler (CELERY_BEAT_SCHEDULER). Every minute keeps an unpaid cash
booking's vehicle (R1-P1, R2-P1) from staying blocked after its hold ends.
"""

from django.db import migrations

TASK_NAME = "Declare no-shows (Appendix B, BR-8)"
TASK = "apps.bookings.tasks.declare_no_shows"


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
        ("bookings", "0004_booking_cash_on_collection"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(schedule, unschedule)]

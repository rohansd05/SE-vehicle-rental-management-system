"""Notify.Remind: schedule apps.notifications.tasks.send_pickup_reminders every 5 minutes.

Like bookings 0003 and 0005, the schedule is data for the database scheduler
(CELERY_BEAT_SCHEDULER). Every 5 minutes (proposed R3-P4) sends each reminder
within 5 minutes of the 24-hour mark; the task itself never sends one twice.
"""

from django.db import migrations

TASK_NAME = "Send pickup reminders (Notify.Remind)"
TASK = "apps.notifications.tasks.send_pickup_reminders"


def schedule(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    every_5_minutes, _ = IntervalSchedule.objects.get_or_create(every=5, period="minutes")
    PeriodicTask.objects.update_or_create(
        name=TASK_NAME, defaults={"task": TASK, "interval": every_5_minutes, "enabled": True}
    )


def unschedule(apps, schema_editor):
    apps.get_model("django_celery_beat", "PeriodicTask").objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(schedule, unschedule)]

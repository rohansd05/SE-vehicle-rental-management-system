"""Maint.Auto.Time and the document expiry alert: two daily Celery Beat tasks.

Like bookings 0003 and 0005, the schedule is data for the database scheduler
(CELERY_BEAT_SCHEDULER).

- apps.maintenance.tasks.raise_preventive_jobs: BR-15, a Preventive job for
  every vehicle whose service is due by distance or time, with the
  service-due alert (Send Maintenance Alert, DFD 7.2 and 7.3).
- apps.maintenance.tasks.alert_expiring_documents: the context diagram's
  document expiry alert to the Administrators (SA-3).
"""

from django.db import migrations

TASKS = {
    "Raise due preventive jobs (BR-15, Maint.Auto.Time)": (
        "apps.maintenance.tasks.raise_preventive_jobs"
    ),
    "Alert expiring vehicle documents (SA-3)": "apps.maintenance.tasks.alert_expiring_documents",
}


def schedule(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    daily, _ = IntervalSchedule.objects.get_or_create(every=1, period="days")
    for name, task in TASKS.items():
        PeriodicTask.objects.update_or_create(
            name=name, defaults={"task": task, "interval": daily, "enabled": True}
        )


def unschedule(apps, schema_editor):
    apps.get_model("django_celery_beat", "PeriodicTask").objects.filter(name__in=TASKS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("maintenance", "0003_n3_auto_jobs_cancel_record_br16"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(schedule, unschedule)]

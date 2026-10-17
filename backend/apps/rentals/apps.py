from django.apps import AppConfig


class RentalsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rentals"
    label = "rentals"
    verbose_name = "Rentals"

    def ready(self) -> None:
        from .notification_templates import register

        register()

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self) -> None:
        from axes.signals import user_locked_out

        from .lockout import on_locked_out

        user_locked_out.connect(on_locked_out, dispatch_uid="accounts.on_locked_out")

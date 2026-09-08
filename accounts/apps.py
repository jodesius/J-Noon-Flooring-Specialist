from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        from . import signals  # noqa: F401
        from .roles import sync_site_admin_group

        # Keep the "Site Administrators" permission group in sync after every
        # migrate (dispatch_uid stops it connecting more than once).
        post_migrate.connect(
            sync_site_admin_group,
            dispatch_uid="accounts.sync_site_admin_group",
        )

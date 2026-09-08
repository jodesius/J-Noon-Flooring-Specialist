from django.core.management.base import BaseCommand

from accounts.roles import SITE_ADMIN_GROUP, sync_site_admin_group


class Command(BaseCommand):
    help = "Create/refresh the 'Site Administrators' permission group."

    def handle(self, *args, **options):
        group = sync_site_admin_group()
        self.stdout.write(
            self.style.SUCCESS(
                f"'{SITE_ADMIN_GROUP}' group synced - "
                f"{group.permissions.count()} permissions."
            )
        )

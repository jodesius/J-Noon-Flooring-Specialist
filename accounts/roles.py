"""Role / permission-group setup for the project.

Three tiers:

* superuser (`is_superuser`)  - jodesius only; bypasses all checks.
* Site Administrators (group) - staff users who manage all project content
  and customer accounts, but cannot grant superuser, edit raw permissions,
  or manage groups.
* regular user               - no staff access at all.

`sync_site_admin_group()` (re)builds the group's permission set from the
project's own apps. It runs after every `migrate` and via
`manage.py sync_roles`, so the group stays current as models are added.
"""

SITE_ADMIN_GROUP = "Site Administrators"

# The project's own apps. The Site Administrators group gets every
# add/change/delete/view permission for models in these apps. Django's
# `auth` app is deliberately excluded, so group members cannot create
# groups or edit permissions (no privilege escalation).
MANAGED_APP_LABELS = (
    "accounts",
    "core",
    "gallery",
    "bookings",
    "reviews",
    "quotes",
    "rewards",
)

# Permission codenames the group must never receive, even for managed apps.
DENIED_CODENAMES = set()


def sync_site_admin_group(**kwargs):
    from django.contrib.auth.models import Group, Permission

    group, _ = Group.objects.get_or_create(name=SITE_ADMIN_GROUP)

    perms = Permission.objects.filter(
        content_type__app_label__in=MANAGED_APP_LABELS
    ).exclude(codename__in=DENIED_CODENAMES)

    group.permissions.set(perms)
    return group

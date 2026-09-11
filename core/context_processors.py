from bookings.models import Job

# Statuses that still count as a "live" project for the nav/home shortcut -
# once a job is complete or cancelled the shortcut goes away again.
_ACTIVE_JOB_STATUSES = [
    Job.Status.REQUESTED,
    Job.Status.AWAITING_DEPOSIT,
    Job.Status.NOT_STARTED,
    Job.Status.UNDERWAY,
]


def active_job(request):
    """Powers the "Your projects" shortcut in the nav bar and home hero."""
    if not request.user.is_authenticated:
        return {"has_active_job": False}
    has_active_job = Job.objects.filter(
        user=request.user, status__in=_ACTIVE_JOB_STATUSES
    ).exists()
    return {"has_active_job": has_active_job}

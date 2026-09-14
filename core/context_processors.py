from bookings.models import Job, JobMessage, RefundRequest

# Statuses that still count as a "live" project for the nav/home shortcut -
# once a job is complete or cancelled the shortcut goes away again.
_ACTIVE_JOB_STATUSES = [
    Job.Status.REQUESTED,
    Job.Status.AWAITING_DEPOSIT,
    Job.Status.NOT_STARTED,
    Job.Status.UNDERWAY,
]


def active_job(request):
    """Powers the "Your projects" shortcut in the nav bar and home hero, and
    the unread-messages / open-refund-request pills next to an admin's name
    (every page, so staff never have to go looking for these)."""
    if not request.user.is_authenticated:
        return {
            "has_active_job": False,
            "unread_message_count": 0,
            "open_refund_count": 0,
        }

    has_active_job = Job.objects.filter(
        user=request.user, status__in=_ACTIVE_JOB_STATUSES
    ).exists()

    unread_message_count = 0
    open_refund_count = 0
    if request.user.is_site_admin:
        unread_message_count = JobMessage.objects.filter(
            is_staff_message=False, read_by_staff=False
        ).count()
        open_refund_count = RefundRequest.objects.filter(
            status=RefundRequest.Status.REQUESTED
        ).count()

    return {
        "has_active_job": has_active_job,
        "unread_message_count": unread_message_count,
        "open_refund_count": open_refund_count,
    }

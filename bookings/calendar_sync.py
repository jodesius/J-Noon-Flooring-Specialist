"""Push a "book a call" request onto the fitter's Google Calendar.

Uses a Google service account (no OAuth dance). `create_call_event(call)`
returns the new event's id, or raises `CalendarUnavailable` - the caller
then just relies on the saved `CallRequest` and the notification email.

Set-up (one-off):
  1. Google Cloud console -> new project -> enable "Google Calendar API".
  2. Create a service account, add a JSON key, download it.
  3. In Google Calendar settings, share your calendar with the service
     account's email address, permission "Make changes to events".
  4. Put the calendar id (your Google email) in GOOGLE_CALENDAR_ID and the
     key file (JSON text, or a path to it) in GOOGLE_SERVICE_ACCOUNT_JSON.
"""

import json
import logging
import pathlib
from urllib.parse import quote

from django.conf import settings

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_API = "https://www.googleapis.com/calendar/v3/calendars/{cal}/events"


class CalendarUnavailable(Exception):
    """Raised when a calendar event can't be created."""


def calendar_configured():
    return bool(settings.GOOGLE_CALENDAR_ID and settings.GOOGLE_SERVICE_ACCOUNT_JSON)


def _load_key_info():
    raw = settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    path = pathlib.Path(raw)
    if not path.is_file():
        raise CalendarUnavailable(f"service account file not found: {raw}")
    return json.loads(path.read_text())


def _session():
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        _load_key_info(), scopes=SCOPES
    )
    return AuthorizedSession(creds)


def _tz():
    name = settings.BOOKINGS_TIMEZONE
    return ZoneInfo(name) if ZoneInfo else None


def create_call_event(call):
    if not calendar_configured():
        raise CalendarUnavailable("not configured")

    tz = _tz()
    start, end = call.window()
    if tz:
        start, end = start.replace(tzinfo=tz), end.replace(tzinfo=tz)

    body = {
        "summary": f"Call {call.name} — {call.phone}",
        "description": (
            "Call-back requested via the website.\n\n"
            f"Name:  {call.name}\n"
            f"Phone: {call.phone}\n"
            f"They asked for: {call.preferred_date:%A %d %B} at {call.when_label}\n"
            + (f"\nMessage:\n{call.message}\n" if call.message else "")
        ),
        "start": {"dateTime": start.isoformat(), "timeZone": settings.BOOKINGS_TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": settings.BOOKINGS_TIMEZONE},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},
                {"method": "popup", "minutes": 12 * 60},
            ],
        },
    }

    try:
        resp = _session().post(
            _API.format(cal=quote(settings.GOOGLE_CALENDAR_ID, safe="")),
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
    except CalendarUnavailable:
        raise
    except Exception as exc:  # network, auth, google errors - fall back cleanly
        logger.warning("Calendar event failed for CallRequest %s: %s", call.pk, exc)
        raise CalendarUnavailable("api error") from exc

    return resp.json().get("id", "")

import json
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from backend.auth import refresh_google_token, SCOPES


def _get_service(token_json: str, email: str | None = None):
    try:
        token = refresh_google_token(token_json, email)
    except Exception as e:
        raise RuntimeError(f"Failed to refresh Google token: {e}")
    creds = Credentials.from_authorized_user_info(json.loads(token), SCOPES)
    return build("calendar", "v3", credentials=creds)


def _handle_google_error(e: HttpError, action: str):
    if e.resp.status == 403:
        raise RuntimeError(f"Insufficient permissions to {action}. Re-authentication may be required.")
    if e.resp.status == 404:
        raise RuntimeError(f"Resource not found while trying to {action}.")
    if e.resp.status == 429:
        raise RuntimeError(f"Google API rate limit exceeded. Try again later.")
    raise RuntimeError(f"Google API error while {action}: {e.resp.status} {e.reason}")


def _format_event(event: dict) -> dict:
    return {
        "id": event["id"],
        "summary": event.get("summary", "(no title)"),
        "description": event.get("description"),
        "start": event["start"].get("dateTime", event["start"].get("date")),
        "end": event["end"].get("dateTime", event["end"].get("date")),
        "location": event.get("location"),
        "attendees": [a.get("email") for a in event.get("attendees", [])],
        "status": event.get("status", "confirmed"),
        "recurring_event_id": event.get("recurringEventId"),
        "html_link": event.get("htmlLink"),
    }


# ── Multi-calendar ───────────────────────────────────────────────────────

def list_calendars(token_json: str, email: str | None = None) -> list[dict]:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    try:
        result = service.calendarList().list().execute()
    except HttpError as e:
        _handle_google_error(e, "listing calendars")

    calendars = []
    for cal in result.get("items", []):
        calendars.append({
            "id": cal["id"],
            "summary": cal.get("summary", ""),
            "description": cal.get("description"),
            "primary": cal.get("primary", False),
            "access_role": cal.get("accessRole", "reader"),
            "timezone": cal.get("timeZone", "UTC"),
        })
    return calendars


# ── List events ──────────────────────────────────────────────────────────

def list_events(token_json: str, start: str, end: str,
                calendar_id: str = "primary", max_results: int = 50,
                email: str | None = None) -> list[dict]:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    try:
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start,
            timeMax=end,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except HttpError as e:
        _handle_google_error(e, "listing calendar events")

    return [_format_event(event) for event in events.get("items", [])]


# ── Create event ─────────────────────────────────────────────────────────

def create_event(token_json: str, summary: str, start: str, end: str,
                 timezone: str = "UTC", description: str | None = None,
                 location: str | None = None, attendees: list[str] | None = None,
                 calendar_id: str = "primary",
                 email: str | None = None) -> dict:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    event_body = {
        "summary": summary,
        "start": {"dateTime": start, "timeZone": timezone},
        "end": {"dateTime": end, "timeZone": timezone},
    }
    if description:
        event_body["description"] = description
    if location:
        event_body["location"] = location
    if attendees:
        event_body["attendees"] = [{"email": a} for a in attendees]

    try:
        created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
    except HttpError as e:
        _handle_google_error(e, "creating calendar event")

    return _format_event(created)


# ── Update event ─────────────────────────────────────────────────────────

def update_event(token_json: str, event_id: str,
                 summary: str | None = None,
                 start: str | None = None, end: str | None = None,
                 timezone: str | None = None,
                 description: str | None = None,
                 location: str | None = None,
                 attendees: list[str] | None = None,
                 calendar_id: str = "primary",
                 email: str | None = None) -> dict:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    try:
        existing = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    except HttpError as e:
        _handle_google_error(e, f"fetching event {event_id}")

    if summary is not None:
        existing["summary"] = summary
    if start is not None:
        existing["start"] = {"dateTime": start, "timeZone": timezone or existing["start"].get("timeZone", "UTC")}
    if end is not None:
        existing["end"] = {"dateTime": end, "timeZone": timezone or existing["end"].get("timeZone", "UTC")}
    if description is not None:
        existing["description"] = description
    if location is not None:
        existing["location"] = location
    if attendees is not None:
        existing["attendees"] = [{"email": a} for a in attendees]

    try:
        updated = service.events().update(
            calendarId=calendar_id, eventId=event_id, body=existing
        ).execute()
    except HttpError as e:
        _handle_google_error(e, f"updating event {event_id}")

    return _format_event(updated)


# ── Delete event ─────────────────────────────────────────────────────────

def delete_event(token_json: str, event_id: str,
                 calendar_id: str = "primary",
                 email: str | None = None) -> None:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    except HttpError as e:
        _handle_google_error(e, f"deleting event {event_id}")


# ── Availability ─────────────────────────────────────────────────────────

def get_availability(token_json: str, start: str, end: str,
                     duration_minutes: int = 30, timezone: str = "UTC",
                     calendar_id: str = "primary",
                     email: str | None = None) -> list[dict]:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    body = {
        "timeMin": start,
        "timeMax": end,
        "timeZone": timezone,
        "items": [{"id": calendar_id}],
    }

    try:
        result = service.freebusy().query(body=body).execute()
    except HttpError as e:
        _handle_google_error(e, "checking availability")

    busy = result["calendars"].get(calendar_id, {}).get("busy", [])

    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    slot_duration = timedelta(minutes=duration_minutes)

    slots = []
    current = start_dt
    while current + slot_duration <= end_dt:
        slot_end = current + slot_duration
        conflict = False
        for busy_slot in busy:
            busy_start = datetime.fromisoformat(busy_slot["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy_slot["end"].replace("Z", "+00:00"))
            if current < busy_end and slot_end > busy_start:
                conflict = True
                break
        if not conflict:
            slots.append({
                "start": current.isoformat(),
                "end": slot_end.isoformat(),
            })
        current += slot_duration

    return slots

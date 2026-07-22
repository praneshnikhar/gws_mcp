import json
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from backend.auth import refresh_google_token, SCOPES


def _get_service(token_json: str):
    token = refresh_google_token(token_json)
    creds = Credentials.from_authorized_user_info(json.loads(token), SCOPES)
    return build("calendar", "v3", credentials=creds)


def list_events(token_json: str, start: str, end: str, max_results: int = 50) -> list[dict]:
    service = _get_service(token_json)
    events = service.events().list(
        calendarId="primary",
        timeMin=start,
        timeMax=end,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    result = []
    for event in events.get("items", []):
        result.append({
            "id": event["id"],
            "summary": event.get("summary", "(no title)"),
            "description": event.get("description"),
            "start": event["start"].get("dateTime", event["start"].get("date")),
            "end": event["end"].get("dateTime", event["end"].get("date")),
            "location": event.get("location"),
            "attendees": [a.get("email") for a in event.get("attendees", [])],
        })

    return result


def create_event(token_json: str, summary: str, start: str, end: str,
                 timezone: str = "UTC", description: str = None,
                 location: str = None, attendees: list[str] = None,
                 reminders_minutes: list[int] = None) -> dict:
    service = _get_service(token_json)

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
    if reminders_minutes:
        event_body["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": m} for m in reminders_minutes],
        }

    created = service.events().insert(calendarId="primary", body=event_body).execute()
    return {
        "id": created["id"],
        "summary": created.get("summary"),
        "start": created["start"].get("dateTime", created["start"].get("date")),
        "end": created["end"].get("dateTime", created["end"].get("date")),
        "html_link": created.get("htmlLink"),
    }


def get_availability(token_json: str, start: str, end: str,
                     duration_minutes: int = 30, timezone: str = "UTC") -> list[dict]:
    service = _get_service(token_json)

    body = {
        "timeMin": start,
        "timeMax": end,
        "timeZone": timezone,
        "items": [{"id": "primary"}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = result["calendars"].get("primary", {}).get("busy", [])

    from datetime import datetime, timedelta
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

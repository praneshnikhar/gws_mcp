"""HTTP client for connectors.ai backend API."""

import os
import httpx

BASE_URL = os.environ.get("CONNECTORS_API_URL", "http://localhost:8321")
API_KEY = os.environ.get("CONNECTORS_API_KEY", "")


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


def _get(api_key: str, path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    resp = httpx.get(url, params=params, headers=_headers(api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(api_key: str, path: str, body: dict, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    if params is None:
        params = {}
    resp = httpx.post(url, json=body, params=params, headers=_headers(api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _patch(api_key: str, path: str, body: dict, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    if params is None:
        params = {}
    resp = httpx.request("PATCH", url, json=body, params=params, headers=_headers(api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _delete(api_key: str, path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    if params is None:
        params = {}
    resp = httpx.request("DELETE", url, params=params, headers=_headers(api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── Email ────────────────────────────────────────────────────────────────

def list_emails(api_key: str, max_results: int = 20, query: str = "",
                page_token: str | None = None) -> dict:
    params = {"max_results": max_results, "query": query}
    if page_token:
        params["page_token"] = page_token
    return _get(api_key, "/api/email/list", params)


def send_email(api_key: str, to: list[str], subject: str, body: str,
               cc: list[str] = None, bcc: list[str] = None,
               attachments: list[dict] = None) -> dict:
    return _post(api_key, "/api/email/send", {
        "to": to, "subject": subject, "body": body,
        "cc": cc or [], "bcc": bcc or [],
        "attachments": attachments or [],
    })


def reply_email(api_key: str, thread_id: str, message_id: str, body: str,
                cc: list[str] = None) -> dict:
    return _post(api_key, "/api/email/reply", {
        "thread_id": thread_id, "message_id": message_id, "body": body,
        "cc": cc or [],
    })


def forward_email(api_key: str, thread_id: str, message_id: str,
                  to: list[str], body: str, cc: list[str] = None) -> dict:
    return _post(api_key, "/api/email/forward", {
        "thread_id": thread_id, "message_id": message_id,
        "to": to, "body": body, "cc": cc or [],
    })


def get_thread(api_key: str, thread_id: str,
               include_attachments: bool = False) -> dict:
    return _get(api_key, f"/api/email/thread/{thread_id}",
                {"include_attachments": str(include_attachments).lower()})


def mark_read(api_key: str, message_id: str) -> dict:
    return _post(api_key, "/api/email/mark-read", {"message_id": message_id})


def mark_unread(api_key: str, message_id: str) -> dict:
    return _post(api_key, "/api/email/mark-unread", {"message_id": message_id})


def get_attachment(api_key: str, message_id: str, attachment_id: str) -> dict:
    return _get(api_key, "/api/email/attachment",
                {"message_id": message_id, "attachment_id": attachment_id})


# ── Calendar ─────────────────────────────────────────────────────────────

def list_calendars(api_key: str) -> dict:
    return _get(api_key, "/api/calendar/list")


def list_calendar_events(api_key: str, start: str, end: str,
                         calendar_id: str = "primary",
                         max_results: int = 50) -> dict:
    return _get(api_key, "/api/calendar/events", {
        "start": start, "end": end,
        "calendar_id": calendar_id, "max_results": max_results,
    })


def create_calendar_event(api_key: str, summary: str, start: str, end: str,
                          timezone: str = "UTC", description: str = None,
                          location: str = None, attendees: list[str] = None,
                          recurrence: list[str] = None,
                          calendar_id: str = "primary") -> dict:
    return _post(api_key, "/api/calendar/events", {
        "summary": summary, "start": start, "end": end,
        "timezone": timezone, "description": description,
        "location": location, "attendees": attendees or [],
        "recurrence": recurrence or [],
        "calendar_id": calendar_id,
    })


def update_calendar_event(api_key: str, event_id: str,
                          summary: str = None, start: str = None, end: str = None,
                          timezone: str = None, description: str = None,
                          location: str = None, attendees: list[str] = None,
                          recurrence: list[str] = None,
                          calendar_id: str = "primary") -> dict:
    return _patch(api_key, f"/api/calendar/events/{event_id}", {
        k: v for k, v in {
            "summary": summary, "start": start, "end": end,
            "timezone": timezone, "description": description,
            "location": location, "attendees": attendees,
            "recurrence": recurrence,
            "calendar_id": calendar_id,
        }.items() if v is not None
    })


def delete_calendar_event(api_key: str, event_id: str,
                          calendar_id: str = "primary") -> dict:
    return _delete(api_key, f"/api/calendar/events/{event_id}",
                   {"calendar_id": calendar_id})


def get_calendar_event(api_key: str, event_id: str,
                       calendar_id: str = "primary") -> dict:
    return _get(api_key, f"/api/calendar/events/{event_id}",
                {"calendar_id": calendar_id})


def get_availability(api_key: str, start: str, end: str,
                     duration_minutes: int = 30,
                     calendar_id: str = "primary",
                     working_hours_only: bool = False) -> dict:
    return _get(api_key, "/api/calendar/availability", {
        "start": start, "end": end,
        "duration_minutes": duration_minutes,
        "calendar_id": calendar_id,
        "working_hours_only": str(working_hours_only).lower(),
    })


# ── Working hours ────────────────────────────────────────────────────────

def get_working_hours(api_key: str) -> dict:
    return _get(api_key, "/api/working-hours")


def set_working_hours(api_key: str, day_of_week: int,
                      start_time: str, end_time: str,
                      timezone: str = "UTC") -> dict:
    return _post(api_key, "/api/working-hours", {
        "day_of_week": day_of_week,
        "start_time": start_time,
        "end_time": end_time,
        "timezone": timezone,
    })


def delete_working_hours(api_key: str, day_of_week: int = None) -> dict:
    params = {}
    if day_of_week is not None:
        params["day_of_week"] = day_of_week
    return _delete(api_key, "/api/working-hours", params=params)

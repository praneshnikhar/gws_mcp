"""HTTP client for connectors.ai backend API."""

import os
import httpx

BASE_URL = os.environ.get("CONNECTORS_API_URL", "http://localhost:8321")
API_KEY = os.environ.get("CONNECTORS_API_KEY", "")


def _get(api_key: str, path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    if params is None:
        params = {}
    params["api_key"] = api_key
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(api_key: str, path: str, body: dict, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    if params is None:
        params = {}
    params["api_key"] = api_key
    resp = httpx.post(url, json=body, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def list_emails(api_key: str, max_results: int = 20, query: str = "") -> list[dict]:
    data = _get(api_key, "/api/email/list", {"max_results": max_results, "query": query})
    return data["messages"]


def send_email(api_key: str, to: list[str], subject: str, body: str,
               cc: list[str] = None, bcc: list[str] = None) -> dict:
    return _post(api_key, "/api/email/send", {
        "to": to, "subject": subject, "body": body,
        "cc": cc or [], "bcc": bcc or [],
    })


def get_thread(api_key: str, thread_id: str) -> list[dict]:
    data = _get(api_key, f"/api/email/thread/{thread_id}")
    return data["messages"]


def list_calendar_events(api_key: str, start: str, end: str) -> list[dict]:
    data = _get(api_key, "/api/calendar/events", {"start": start, "end": end})
    return data["events"]


def create_calendar_event(api_key: str, summary: str, start: str, end: str,
                          timezone: str = "UTC", description: str = None,
                          location: str = None, attendees: list[str] = None) -> dict:
    return _post(api_key, "/api/calendar/events", {
        "summary": summary, "start": start, "end": end,
        "timezone": timezone, "description": description,
        "location": location, "attendees": attendees or [],
    })


def get_availability(api_key: str, start: str, end: str, duration_minutes: int = 30) -> list[dict]:
    data = _get(api_key, "/api/calendar/availability", {
        "start": start, "end": end, "duration_minutes": duration_minutes,
    })
    return data["slots"]

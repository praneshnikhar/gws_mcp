"""
connectors.ai backend

Start:  uvicorn backend.main:app --reload --port 8321
"""

import os
import secrets
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.db import init_db, save_user, get_user_by_api_key
from backend.auth import get_auth_url, exchange_code
from backend.api import gmail, calendar

app = FastAPI(title="connectors.ai", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()


# ── Auth ────────────────────────────────────────────────────────────────

@app.get("/auth/login")
async def login():
    auth_url, state = get_auth_url()
    return JSONResponse({"auth_url": auth_url, "state": state})


@app.get("/auth/callback")
async def callback(code: str = Query(...), state: str = Query(...)):
    user_info = exchange_code(code, state)
    api_key = "cnx_" + secrets.token_urlsafe(32)
    save_user(
        email=user_info["email"],
        name=user_info["name"],
        google_token=user_info["token"],
        api_key=api_key,
    )
    return JSONResponse({
        "message": "Connected! Save this API key — it's shown once.",
        "api_key": api_key,
        "user_email": user_info["email"],
    })


# ── Auth middleware ─────────────────────────────────────────────────────

def _require_user(api_key: str) -> dict:
    user = get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


# ── Email ───────────────────────────────────────────────────────────────

@app.get("/api/email/list")
async def email_list(
    max_results: int = Query(20, ge=1, le=100),
    query: str = Query(""),
    api_key: str = Query(...),
):
    user = _require_user(api_key)
    messages = gmail.list_messages(user["google_token"], max_results, query)
    return {"messages": messages}


@app.post("/api/email/send")
async def email_send(body: dict, api_key: str = Query(...)):
    user = _require_user(api_key)
    result = gmail.send_message(
        user["google_token"],
        to=body["to"],
        subject=body["subject"],
        body=body["body"],
        cc=body.get("cc"),
        bcc=body.get("bcc"),
    )
    return result


@app.get("/api/email/thread/{thread_id}")
async def email_thread(thread_id: str, api_key: str = Query(...)):
    user = _require_user(api_key)
    messages = gmail.get_thread(user["google_token"], thread_id)
    return {"messages": messages}


# ── Calendar ────────────────────────────────────────────────────────────

@app.get("/api/calendar/events")
async def calendar_events(
    start: str = Query(...),
    end: str = Query(...),
    api_key: str = Query(...),
):
    user = _require_user(api_key)
    events = calendar.list_events(user["google_token"], start, end)
    return {"events": events}


@app.post("/api/calendar/events")
async def calendar_create_event(body: dict, api_key: str = Query(...)):
    user = _require_user(api_key)
    event = calendar.create_event(
        user["google_token"],
        summary=body["summary"],
        start=body["start"],
        end=body["end"],
        timezone=body.get("timezone", "UTC"),
        description=body.get("description"),
        location=body.get("location"),
        attendees=body.get("attendees"),
    )
    return event


@app.get("/api/calendar/availability")
async def calendar_availability(
    start: str = Query(...),
    end: str = Query(...),
    duration_minutes: int = Query(30),
    api_key: str = Query(...),
):
    user = _require_user(api_key)
    slots = calendar.get_availability(
        user["google_token"], start, end, duration_minutes
    )
    return {"slots": slots}


# ── Health ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

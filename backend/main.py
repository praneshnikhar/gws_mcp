"""
connectors.ai backend

Start:  uvicorn backend.main:app --reload --port 8321
"""

import os
import secrets
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.db import (
    init_db, save_user, get_user_by_api_key,
    set_working_hours, get_working_hours, delete_working_hours,
)
from backend.auth import get_auth_url, exchange_code
from backend.api import gmail, calendar


# ── Logging ──────────────────────────────────────────────────────────────

class JSONFormatter:
    def format(self, record: logging.LogRecord) -> str:
        import json as _json
        log = {
            "t": record.created,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "req_id"):
            log["req_id"] = record.req_id
        if record.exc_info and record.exc_info[0]:
            log["exc"] = self._format_exc(record.exc_info)
        return _json.dumps(log, default=str)

    def _format_exc(self, exc_info):
        import traceback
        return "".join(traceback.format_exception(*exc_info))


_handler = logging.StreamHandler()
_handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger("gws_mcp")


# ── App setup ────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("db_initialized")
    yield


app = FastAPI(title="gws_mcp", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID middleware ────────────────────────────────────────────────

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    req_id = request.headers.get("X-Request-Id", uuid.uuid4().hex[:12])
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    response.headers["X-Request-Id"] = req_id
    log.info("request", extra={"req_id": req_id, "method": request.method, "path": request.url.path, "status": response.status_code, "elapsed_ms": round(elapsed * 1000)})
    return response


# ── Auth dependency ──────────────────────────────────────────────────────

async def require_user(authorization: str | None = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must use Bearer scheme")
    api_key = authorization.removeprefix("Bearer ").strip()
    user = get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


# ── Auth routes ──────────────────────────────────────────────────────────

@app.get("/auth/login")
async def login():
    auth_url, state = get_auth_url()
    return JSONResponse({"auth_url": auth_url, "state": state})


@app.get("/auth/callback")
async def callback(code: str, state: str):
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


# ── Email routes ─────────────────────────────────────────────────────────

@app.get("/api/email/list")
@limiter.limit("60/minute")
async def email_list(
    request: Request,
    max_results: int = 20,
    query: str = "",
    page_token: str | None = None,
    user: dict = Depends(require_user),
):
    try:
        messages, next_page_token = gmail.list_messages(
            user["google_token"], max_results, query, page_token, email=user["email"],
        )
        result = {"messages": messages}
        if next_page_token:
            result["next_page_token"] = next_page_token
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/email/send")
@limiter.limit("30/minute")
async def email_send(
    request: Request,
    body: dict,
    user: dict = Depends(require_user),
):
    errors = []
    if not body.get("to"):
        errors.append("Field 'to' is required")
    if not body.get("subject"):
        errors.append("Field 'subject' is required")
    if not body.get("body"):
        errors.append("Field 'body' is required")
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    try:
        result = gmail.send_message(
            user["google_token"],
            to=body["to"],
            subject=body["subject"],
            body=body["body"],
            cc=body.get("cc"),
            bcc=body.get("bcc"),
            attachments=body.get("attachments"),
            email=user["email"],
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/email/reply")
@limiter.limit("30/minute")
async def email_reply(
    request: Request,
    body: dict,
    user: dict = Depends(require_user),
):
    errors = []
    if not body.get("thread_id"):
        errors.append("Field 'thread_id' is required")
    if not body.get("message_id"):
        errors.append("Field 'message_id' is required")
    if not body.get("body"):
        errors.append("Field 'body' is required")
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    try:
        result = gmail.reply_message(
            user["google_token"],
            thread_id=body["thread_id"],
            message_id=body["message_id"],
            body=body["body"],
            cc=body.get("cc"),
            email=user["email"],
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/email/forward")
@limiter.limit("30/minute")
async def email_forward(
    request: Request,
    body: dict,
    user: dict = Depends(require_user),
):
    errors = []
    if not body.get("thread_id"):
        errors.append("Field 'thread_id' is required")
    if not body.get("message_id"):
        errors.append("Field 'message_id' is required")
    if not body.get("to"):
        errors.append("Field 'to' is required")
    if not body.get("body"):
        errors.append("Field 'body' is required")
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    try:
        result = gmail.forward_message(
            user["google_token"],
            thread_id=body["thread_id"],
            message_id=body["message_id"],
            to=body["to"],
            body=body["body"],
            cc=body.get("cc"),
            email=user["email"],
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/email/thread/{thread_id}")
async def email_thread(
    request: Request,
    thread_id: str,
    include_attachments: bool = False,
    user: dict = Depends(require_user),
):
    try:
        messages = gmail.get_thread(
            user["google_token"], thread_id, include_attachments, email=user["email"],
        )
        return {"messages": messages}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/email/mark-read")
@limiter.limit("60/minute")
async def email_mark_read(
    request: Request,
    body: dict,
    user: dict = Depends(require_user),
):
    if not body.get("message_id"):
        raise HTTPException(status_code=422, detail="Field 'message_id' is required")
    try:
        result = gmail.mark_read(user["google_token"], body["message_id"], email=user["email"])
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/email/mark-unread")
@limiter.limit("60/minute")
async def email_mark_unread(
    request: Request,
    body: dict,
    user: dict = Depends(require_user),
):
    if not body.get("message_id"):
        raise HTTPException(status_code=422, detail="Field 'message_id' is required")
    try:
        result = gmail.mark_unread(user["google_token"], body["message_id"], email=user["email"])
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/email/attachment")
@limiter.limit("60/minute")
async def email_attachment(
    request: Request,
    message_id: str,
    attachment_id: str,
    user: dict = Depends(require_user),
):
    try:
        result = gmail.get_attachment(
            user["google_token"], message_id, attachment_id, email=user["email"],
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Calendar routes ──────────────────────────────────────────────────────

@app.get("/api/calendar/list")
@limiter.limit("30/minute")
async def calendar_list(
    request: Request,
    user: dict = Depends(require_user),
):
    try:
        calendars = calendar.list_calendars(user["google_token"], email=user["email"])
        return {"calendars": calendars}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/calendar/events")
@limiter.limit("60/minute")
async def calendar_events(
    request: Request,
    start: str,
    end: str,
    calendar_id: str = "primary",
    max_results: int = 50,
    single_events: bool = True,
    user: dict = Depends(require_user),
):
    try:
        events = calendar.list_events(
            user["google_token"], start, end, calendar_id=calendar_id,
            max_results=max_results, single_events=single_events,
            email=user["email"],
        )
        return {"events": events}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/calendar/events/{event_id}")
@limiter.limit("60/minute")
async def calendar_get_event(
    request: Request,
    event_id: str,
    calendar_id: str = "primary",
    user: dict = Depends(require_user),
):
    try:
        event = calendar.get_event(
            user["google_token"], event_id, calendar_id=calendar_id, email=user["email"],
        )
        return event
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/calendar/events")
@limiter.limit("30/minute")
async def calendar_create_event(
    request: Request,
    body: dict,
    user: dict = Depends(require_user),
):
    errors = []
    if not body.get("summary"):
        errors.append("Field 'summary' is required")
    if not body.get("start"):
        errors.append("Field 'start' is required")
    if not body.get("end"):
        errors.append("Field 'end' is required")
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    try:
        event = calendar.create_event(
            user["google_token"],
            summary=body["summary"],
            start=body["start"],
            end=body["end"],
            timezone=body.get("timezone", "UTC"),
            description=body.get("description"),
            location=body.get("location"),
            attendees=body.get("attendees"),
            recurrence=body.get("recurrence"),
            calendar_id=body.get("calendar_id", "primary"),
            email=user["email"],
        )
        return event
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.patch("/api/calendar/events/{event_id}")
@limiter.limit("30/minute")
async def calendar_update_event(
    request: Request,
    event_id: str,
    body: dict,
    user: dict = Depends(require_user),
):
    try:
        event = calendar.update_event(
            user["google_token"],
            event_id=event_id,
            summary=body.get("summary"),
            start=body.get("start"),
            end=body.get("end"),
            timezone=body.get("timezone"),
            description=body.get("description"),
            location=body.get("location"),
            attendees=body.get("attendees"),
            recurrence=body.get("recurrence"),
            calendar_id=body.get("calendar_id", "primary"),
            email=user["email"],
        )
        return event
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.delete("/api/calendar/events/{event_id}")
@limiter.limit("30/minute")
async def calendar_delete_event(
    request: Request,
    event_id: str,
    calendar_id: str = "primary",
    user: dict = Depends(require_user),
):
    try:
        calendar.delete_event(
            user["google_token"], event_id, calendar_id=calendar_id, email=user["email"],
        )
        return {"deleted": True}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/calendar/availability")
@limiter.limit("60/minute")
async def calendar_availability(
    request: Request,
    start: str,
    end: str,
    duration_minutes: int = 30,
    calendar_id: str = "primary",
    working_hours_only: bool = False,
    user: dict = Depends(require_user),
):
    try:
        slots = calendar.get_availability(
            user["google_token"], start, end, duration_minutes,
            calendar_id=calendar_id, working_hours_only=working_hours_only,
            email=user["email"],
        )
        return {"slots": slots}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Working hours routes ─────────────────────────────────────────────────

@app.get("/api/working-hours")
@limiter.limit("30/minute")
async def working_hours_get(
    request: Request,
    user: dict = Depends(require_user),
):
    hours = get_working_hours(user["email"])
    return {"working_hours": hours}


@app.post("/api/working-hours")
@limiter.limit("30/minute")
async def working_hours_set(
    request: Request,
    body: dict,
    user: dict = Depends(require_user),
):
    day = body.get("day_of_week")
    if day is None or not 0 <= day <= 6:
        raise HTTPException(status_code=422, detail="day_of_week must be 0 (Mon) - 6 (Sun)")
    if not body.get("start_time") or not body.get("end_time"):
        raise HTTPException(status_code=422, detail="start_time and end_time required (HH:MM)")
    set_working_hours(
        email=user["email"],
        day_of_week=day,
        start_time=body["start_time"],
        end_time=body["end_time"],
        timezone=body.get("timezone", "UTC"),
    )
    return {"status": "ok"}


@app.delete("/api/working-hours")
@limiter.limit("30/minute")
async def working_hours_delete(
    request: Request,
    day_of_week: int | None = None,
    user: dict = Depends(require_user),
):
    delete_working_hours(user["email"], day_of_week)
    return {"status": "ok"}


# ── Health ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

from pydantic import BaseModel, EmailStr
from typing import Optional


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_email: str
    user_name: str


class EmailMessage(BaseModel):
    id: str
    thread_id: str
    subject: str
    from_: str
    to: str
    snippet: str
    date: str
    labels: list[str] = []


class EmailListResponse(BaseModel):
    messages: list[EmailMessage]
    next_page_token: Optional[str] = None


class SendEmailRequest(BaseModel):
    to: list[str]
    subject: str
    body: str
    cc: list[str] = []
    bcc: list[str] = []


class SendEmailResponse(BaseModel):
    id: str
    thread_id: str


class CalendarEvent(BaseModel):
    id: str
    summary: str
    description: Optional[str] = None
    start: str
    end: str
    location: Optional[str] = None
    attendees: list[str] = []


class CalendarListResponse(BaseModel):
    events: list[CalendarEvent]
    next_page_token: Optional[str] = None


class CreateEventRequest(BaseModel):
    summary: str
    description: Optional[str] = None
    start: str
    end: str
    timezone: str = "UTC"
    location: Optional[str] = None
    attendees: list[str] = []


class AvailabilityRequest(BaseModel):
    start: str
    end: str
    timezone: str = "UTC"
    duration_minutes: int = 30

#!/usr/bin/env python3

import os
import sys
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
from typing import Any

from .client import (
    list_emails, send_email, reply_email, forward_email,
    get_thread, mark_read, mark_unread, get_attachment,
    list_calendars, list_calendar_events, create_calendar_event,
    update_calendar_event, delete_calendar_event, get_calendar_event,
    get_availability, get_working_hours, set_working_hours, delete_working_hours,
)

API_KEY = os.environ.get("CONNECTORS_API_KEY") or ""
if not API_KEY:
    config_path = os.path.expanduser("~/.connectors/config")
    if os.path.exists(config_path):
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("CONNECTORS_API_KEY="):
                    API_KEY = line.split("=", 1)[1]

if not API_KEY:
    print("ERROR: Set CONNECTORS_API_KEY env var or add it to ~/.connectors/config", file=sys.stderr)
    sys.exit(1)

server = Server("gws-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ── Email tools ──────────────────────────────────────────────
        Tool(
            name="list_emails",
            description="List email messages from your inbox. Supports Gmail search syntax: from:, to:, subject:, before:, after:, has:attachment, is:read, is:unread, in:inbox, in:spam, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Max emails to return (1-100)", "default": 20},
                    "query": {"type": "string", "description": "Gmail search query e.g. 'from:alice@.com subject:meeting has:attachment'", "default": ""},
                    "page_token": {"type": "string", "description": "Token for pagination (from previous response)", "default": None},
                },
            },
        ),
        Tool(
            name="send_email",
            description="Send an email. Optionally include base64-encoded attachments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "array", "items": {"type": "string"}, "description": "Recipient email addresses"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body text"},
                    "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients"},
                    "bcc": {"type": "array", "items": {"type": "string"}, "description": "BCC recipients"},
                    "attachments": {"type": "array", "items": {"type": "object", "properties": {
                        "filename": {"type": "string", "description": "Filename"},
                        "content": {"type": "string", "description": "Base64-encoded file content"},
                        "mime_type": {"type": "string", "description": "MIME type", "default": "application/octet-stream"},
                    }}},
                },
                "required": ["to", "subject", "body"],
            },
        ),
        Tool(
            name="reply_email",
            description="Reply to an existing email in the same thread.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Thread ID of the email to reply to"},
                    "message_id": {"type": "string", "description": "Message ID of the specific email to reply to"},
                    "body": {"type": "string", "description": "Reply body text"},
                    "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients"},
                },
                "required": ["thread_id", "message_id", "body"],
            },
        ),
        Tool(
            name="forward_email",
            description="Forward an email to new recipients.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Thread ID of the email to forward"},
                    "message_id": {"type": "string", "description": "Message ID of the specific email to forward"},
                    "to": {"type": "array", "items": {"type": "string"}, "description": "New recipient email addresses"},
                    "body": {"type": "string", "description": "Additional body text to include above the forwarded message"},
                    "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients"},
                },
                "required": ["thread_id", "message_id", "to", "body"],
            },
        ),
        Tool(
            name="get_thread",
            description="Get all messages in an email thread. Optionally include attachment metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "The thread ID to retrieve"},
                    "include_attachments": {"type": "boolean", "description": "Include attachment info in response", "default": False},
                },
                "required": ["thread_id"],
            },
        ),
        Tool(
            name="mark_read",
            description="Mark an email as read.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Message ID to mark as read"},
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="mark_unread",
            description="Mark an email as unread.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Message ID to mark as unread"},
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="get_attachment",
            description="Download an attachment by message ID and attachment ID. Returns base64-encoded data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Message ID containing the attachment"},
                    "attachment_id": {"type": "string", "description": "Attachment ID from thread response"},
                },
                "required": ["message_id", "attachment_id"],
            },
        ),
        # ── Calendar tools ───────────────────────────────────────────
        Tool(
            name="list_calendars",
            description="List all available calendars.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="list_calendar_events",
            description="List calendar events in a date range from a specific calendar (defaults to primary).",
            inputSchema={
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "Start time in ISO 8601 (e.g. 2026-07-22T00:00:00Z)"},
                    "end": {"type": "string", "description": "End time in ISO 8601 (e.g. 2026-07-23T00:00:00Z)"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (default: primary)", "default": "primary"},
                    "max_results": {"type": "integer", "description": "Max events to return", "default": 50},
                },
                "required": ["start", "end"],
            },
        ),
        Tool(
            name="get_calendar_event",
            description="Get a single calendar event by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID to retrieve"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (default: primary)", "default": "primary"},
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="create_calendar_event",
            description="Create a new calendar event. Add recurrence for repeating events.",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Event title"},
                    "start": {"type": "string", "description": "Start time in ISO 8601"},
                    "end": {"type": "string", "description": "End time in ISO 8601"},
                    "description": {"type": "string", "description": "Event description"},
                    "timezone": {"type": "string", "description": "Timezone (e.g. America/New_York)", "default": "UTC"},
                    "location": {"type": "string", "description": "Event location"},
                    "attendees": {"type": "array", "items": {"type": "string"}, "description": "Attendee email addresses"},
                    "recurrence": {"type": "array", "items": {"type": "string"}, "description": "RRULE lines e.g. ['RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR']"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (default: primary)", "default": "primary"},
                },
                "required": ["summary", "start", "end"],
            },
        ),
        Tool(
            name="update_calendar_event",
            description="Update an existing calendar event. Only provided fields will be updated.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID to update"},
                    "summary": {"type": "string", "description": "New title"},
                    "start": {"type": "string", "description": "New start time in ISO 8601"},
                    "end": {"type": "string", "description": "New end time in ISO 8601"},
                    "description": {"type": "string", "description": "New description"},
                    "timezone": {"type": "string", "description": "Timezone"},
                    "location": {"type": "string", "description": "New location"},
                    "attendees": {"type": "array", "items": {"type": "string"}, "description": "Attendee email addresses"},
                    "recurrence": {"type": "array", "items": {"type": "string"}, "description": "RRULE lines to replace existing"},
                    "calendar_id": {"type": "string", "description": "Calendar ID", "default": "primary"},
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="delete_calendar_event",
            description="Delete a calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID to delete"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (default: primary)", "default": "primary"},
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="get_availability",
            description="Find free time slots in your calendar. Optionally restrict to working hours.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "Start of the range in ISO 8601"},
                    "end": {"type": "string", "description": "End of the range in ISO 8601"},
                    "duration_minutes": {"type": "integer", "description": "Desired meeting duration in minutes", "default": 30},
                    "calendar_id": {"type": "string", "description": "Calendar ID (default: primary)", "default": "primary"},
                    "working_hours_only": {"type": "boolean", "description": "Only show slots within configured working hours", "default": False},
                },
                "required": ["start", "end"],
            },
        ),
        # ── Working hours tools ──────────────────────────────────────
        Tool(
            name="get_working_hours",
            description="Get your configured working hours.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="set_working_hours",
            description="Set working hours for a specific day of the week.",
            inputSchema={
                "type": "object",
                "properties": {
                    "day_of_week": {"type": "integer", "description": "0=Monday, 1=Tuesday ... 6=Sunday"},
                    "start_time": {"type": "string", "description": "Start time in HH:MM format e.g. 09:00"},
                    "end_time": {"type": "string", "description": "End time in HH:MM format e.g. 17:00"},
                    "timezone": {"type": "string", "description": "Timezone (e.g. America/New_York)", "default": "UTC"},
                },
                "required": ["day_of_week", "start_time", "end_time"],
            },
        ),
        Tool(
            name="delete_working_hours",
            description="Delete working hours for a specific day or all days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "day_of_week": {"type": "integer", "description": "0=Monday ... 6=Sunday (omit to clear all days)"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        # ── Email ────────────────────────────────────────────────────
        if name == "list_emails":
            result = list_emails(
                API_KEY,
                max_results=arguments.get("max_results", 20),
                query=arguments.get("query", ""),
                page_token=arguments.get("page_token"),
            )
            text = _format_email_list(result)

        elif name == "send_email":
            result = send_email(
                API_KEY,
                to=arguments["to"],
                subject=arguments["subject"],
                body=arguments["body"],
                cc=arguments.get("cc"),
                bcc=arguments.get("bcc"),
                attachments=arguments.get("attachments"),
            )
            text = f"Email sent. ID: {result['id']}, Thread: {result['thread_id']}"

        elif name == "reply_email":
            result = reply_email(
                API_KEY,
                thread_id=arguments["thread_id"],
                message_id=arguments["message_id"],
                body=arguments["body"],
                cc=arguments.get("cc"),
            )
            text = f"Reply sent. ID: {result['id']}, Thread: {result['thread_id']}"

        elif name == "forward_email":
            result = forward_email(
                API_KEY,
                thread_id=arguments["thread_id"],
                message_id=arguments["message_id"],
                to=arguments["to"],
                body=arguments["body"],
                cc=arguments.get("cc"),
            )
            text = f"Email forwarded. ID: {result['id']}, Thread: {result['thread_id']}"

        elif name == "get_thread":
            result = get_thread(
                API_KEY, arguments["thread_id"],
                include_attachments=arguments.get("include_attachments", False),
            )
            text = _format_thread(result["messages"])

        elif name == "mark_read":
            result = mark_read(API_KEY, arguments["message_id"])
            text = f"Marked as read. Labels: {', '.join(result['labels'])}"

        elif name == "mark_unread":
            result = mark_unread(API_KEY, arguments["message_id"])
            text = f"Marked as unread. Labels: {', '.join(result['labels'])}"

        elif name == "get_attachment":
            result = get_attachment(API_KEY, arguments["message_id"], arguments["attachment_id"])
            text = f"Attachment size: {result['size']} bytes\nData (base64, first 200 chars): {result['data'][:200]}..."

        # ── Calendar ─────────────────────────────────────────────────
        elif name == "list_calendars":
            result = list_calendars(API_KEY)
            text = _format_calendars(result["calendars"])

        elif name == "get_calendar_event":
            result = get_calendar_event(
                API_KEY, arguments["event_id"],
                calendar_id=arguments.get("calendar_id", "primary"),
            )
            text = _format_event_detail(result)

        elif name == "list_calendar_events":
            result = list_calendar_events(
                API_KEY, arguments["start"], arguments["end"],
                calendar_id=arguments.get("calendar_id", "primary"),
                max_results=arguments.get("max_results", 50),
            )
            text = _format_events(result["events"])

        elif name == "create_calendar_event":
            result = create_calendar_event(
                API_KEY,
                summary=arguments["summary"],
                start=arguments["start"],
                end=arguments["end"],
                timezone=arguments.get("timezone", "UTC"),
                description=arguments.get("description"),
                location=arguments.get("location"),
                attendees=arguments.get("attendees"),
                recurrence=arguments.get("recurrence"),
                calendar_id=arguments.get("calendar_id", "primary"),
            )
            text = f"Event created: {result['summary']}\nStart: {result['start']}\nEnd: {result['end']}\nLink: {result.get('html_link', 'N/A')}"

        elif name == "update_calendar_event":
            result = update_calendar_event(
                API_KEY,
                event_id=arguments["event_id"],
                summary=arguments.get("summary"),
                start=arguments.get("start"),
                end=arguments.get("end"),
                timezone=arguments.get("timezone"),
                description=arguments.get("description"),
                location=arguments.get("location"),
                attendees=arguments.get("attendees"),
                recurrence=arguments.get("recurrence"),
                calendar_id=arguments.get("calendar_id", "primary"),
            )
            text = f"Event updated: {result['summary']}\nStart: {result['start']}\nEnd: {result['end']}\nLink: {result.get('html_link', 'N/A')}"

        elif name == "delete_calendar_event":
            delete_calendar_event(
                API_KEY, arguments["event_id"],
                calendar_id=arguments.get("calendar_id", "primary"),
            )
            text = f"Event {arguments['event_id']} deleted."

        elif name == "get_availability":
            result = get_availability(
                API_KEY,
                start=arguments["start"],
                end=arguments["end"],
                duration_minutes=arguments.get("duration_minutes", 30),
                calendar_id=arguments.get("calendar_id", "primary"),
                working_hours_only=arguments.get("working_hours_only", False),
            )
            text = _format_slots(result["slots"])

        elif name == "get_working_hours":
            result = get_working_hours(API_KEY)
            text = _format_working_hours(result["working_hours"])

        elif name == "set_working_hours":
            set_working_hours(
                API_KEY,
                day_of_week=arguments["day_of_week"],
                start_time=arguments["start_time"],
                end_time=arguments["end_time"],
                timezone=arguments.get("timezone", "UTC"),
            )
            text = f"Working hours set for day {arguments['day_of_week']}: {arguments['start_time']} - {arguments['end_time']}"

        elif name == "delete_working_hours":
            delete_working_hours(API_KEY, arguments.get("day_of_week"))
            if "day_of_week" in arguments:
                text = f"Working hours deleted for day {arguments['day_of_week']}."
            else:
                text = "All working hours deleted."

        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=text)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(uri="gws://info", name="Account Info", mimeType="text/plain"),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "gws://info":
        return "gws_mcp — bring your Google Workspace (email, calendar) to any AI tool."
    raise ValueError(f"Unknown resource: {uri}")


# ── Formatters ───────────────────────────────────────────────────────────

def _format_email_list(data: dict) -> str:
    emails = data.get("messages", [])
    if not emails:
        return "No emails found."
    lines = []
    for i, m in enumerate(emails, 1):
        lines.append(f"{i}. [{m['id']}] {m['subject']}")
        lines.append(f"   From: {m['from_']}  |  Date: {m['date']}")
        labels = m.get("labels", [])
        if "UNREAD" in labels:
            lines.append(f"   📩 UNREAD")
        lines.append(f"   {m['snippet'][:100]}")
        lines.append("")
    if data.get("next_page_token"):
        lines.append(f"--- More results. Use page_token={data['next_page_token']} to fetch next page ---")
    return "\n".join(lines)


def _format_thread(messages: list[dict]) -> str:
    lines = []
    for i, m in enumerate(messages, 1):
        lines.append(f"--- Message {i} ---")
        lines.append(f"From: {m['from_']}  |  Date: {m['date']}")
        lines.append(f"Subject: {m['subject']}")
        lines.append(m['body'][:500] if m['body'] else m['snippet'])
        if m.get("attachments"):
            for att in m["attachments"]:
                lines.append(f"  📎 {att['filename']} ({att['mime_type']}, {att['size']} bytes) — attachment_id: {att['attachment_id']}")
        lines.append("")
    return "\n".join(lines) or "No messages found."


def _format_calendars(calendars: list[dict]) -> str:
    if not calendars:
        return "No calendars found."
    lines = []
    for i, c in enumerate(calendars, 1):
        primary = " (primary)" if c.get("primary") else ""
        lines.append(f"{i}. {c['summary']}{primary}")
        lines.append(f"   ID: {c['id']}  |  Role: {c['access_role']}  |  TZ: {c['timezone']}")
        lines.append("")
    return "\n".join(lines)


def _format_events(events: list[dict]) -> str:
    if not events:
        return "No events found in this range."
    lines = []
    for i, e in enumerate(events, 1):
        if e.get("status") == "cancelled":
            continue
        lines.append(f"{i}. {e['summary']}")
        lines.append(f"   {e['start']} → {e['end']}")
        if e.get("location"):
            lines.append(f"   Location: {e['location']}")
        if e.get("attendees"):
            lines.append(f"   Attendees: {', '.join(e['attendees'])}")
        if e.get("recurring_event_id"):
            lines.append(f"   🔄 Recurring instance")
        lines.append("")
    return "\n".join(lines)


def _format_event_detail(event: dict) -> str:
    lines = [
        f"Summary: {event['summary']}",
        f"Start: {event['start']}",
        f"End: {event['end']}",
    ]
    if event.get("description"):
        lines.append(f"Description: {event['description']}")
    if event.get("location"):
        lines.append(f"Location: {event['location']}")
    if event.get("attendees"):
        lines.append(f"Attendees: {', '.join(event['attendees'])}")
    if event.get("recurrence"):
        lines.append(f"Recurrence: {'; '.join(event['recurrence'])}")
    if event.get("recurring_event_id"):
        lines.append(f"🔄 Part of recurring series")
    lines.append(f"Link: {event.get('html_link', 'N/A')}")
    return "\n".join(lines)


def _format_working_hours(hours: list[dict]) -> str:
    if not hours:
        return "No working hours configured."
    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    lines = ["Working hours:"]
    for h in hours:
        name = DAY_NAMES[h["day_of_week"]]
        lines.append(f"  {name}: {h['start_time']} - {h['end_time']} ({h['timezone']})")
    return "\n".join(lines)


def _format_slots(slots: list[dict]) -> str:
    if not slots:
        return "No available slots found in this range."
    lines = ["Available time slots:"]
    for i, s in enumerate(slots, 1):
        lines.append(f"{i}. {s['start']} → {s['end']}")
    return "\n".join(lines)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import anyio
    anyio.run(main)

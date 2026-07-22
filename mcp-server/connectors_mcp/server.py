#!/usr/bin/env python3
"""
connectors.ai MCP Server

Run:  CONNECTORS_API_KEY=cnx_xxx python -m connectors_mcp.server
"""

import os
import sys
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
from typing import Any

from .client import (
    list_emails, send_email, get_thread,
    list_calendar_events, create_calendar_event, get_availability,
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

server = Server("connectors-ai")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_emails",
            description="List email messages from your inbox. Optionally filter with a search query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Max emails to return (1-100)", "default": 20},
                    "query": {"type": "string", "description": "Gmail search query (e.g. 'from:alice', 'subject:meeting')", "default": ""},
                },
            },
        ),
        Tool(
            name="send_email",
            description="Send an email from your connected account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "array", "items": {"type": "string"}, "description": "Recipient email addresses"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body text"},
                    "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients"},
                    "bcc": {"type": "array", "items": {"type": "string"}, "description": "BCC recipients"},
                },
                "required": ["to", "subject", "body"],
            },
        ),
        Tool(
            name="get_thread",
            description="Get all messages in an email thread by thread ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "The thread ID to retrieve"},
                },
                "required": ["thread_id"],
            },
        ),
        Tool(
            name="list_calendar_events",
            description="List calendar events in a date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "Start time in ISO 8601 format (e.g. 2026-07-22T00:00:00Z)"},
                    "end": {"type": "string", "description": "End time in ISO 8601 format (e.g. 2026-07-23T00:00:00Z)"},
                },
                "required": ["start", "end"],
            },
        ),
        Tool(
            name="create_calendar_event",
            description="Create a new calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Event title"},
                    "start": {"type": "string", "description": "Start time in ISO 8601 format"},
                    "end": {"type": "string", "description": "End time in ISO 8601 format"},
                    "description": {"type": "string", "description": "Event description"},
                    "timezone": {"type": "string", "description": "Timezone (e.g. America/New_York)", "default": "UTC"},
                    "location": {"type": "string", "description": "Event location"},
                    "attendees": {"type": "array", "items": {"type": "string"}, "description": "Attendee email addresses"},
                },
                "required": ["summary", "start", "end"],
            },
        ),
        Tool(
            name="get_availability",
            description="Find free time slots in your calendar.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "Start of the range in ISO 8601"},
                    "end": {"type": "string", "description": "End of the range in ISO 8601"},
                    "duration_minutes": {"type": "integer", "description": "Desired meeting duration in minutes", "default": 30},
                },
                "required": ["start", "end"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "list_emails":
            result = list_emails(
                API_KEY,
                max_results=arguments.get("max_results", 20),
                query=arguments.get("query", ""),
            )
            text = _format_emails(result)

        elif name == "send_email":
            result = send_email(
                API_KEY,
                to=arguments["to"],
                subject=arguments["subject"],
                body=arguments["body"],
                cc=arguments.get("cc"),
                bcc=arguments.get("bcc"),
            )
            text = f"Email sent. ID: {result['id']}, Thread: {result['thread_id']}"

        elif name == "get_thread":
            result = get_thread(API_KEY, arguments["thread_id"])
            text = _format_thread(result)

        elif name == "list_calendar_events":
            result = list_calendar_events(API_KEY, arguments["start"], arguments["end"])
            text = _format_events(result)

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
            )
            text = f"Event created: {result['summary']}\nStart: {result['start']}\nEnd: {result['end']}\nLink: {result.get('html_link', 'N/A')}"

        elif name == "get_availability":
            result = get_availability(
                API_KEY,
                start=arguments["start"],
                end=arguments["end"],
                duration_minutes=arguments.get("duration_minutes", 30),
            )
            text = _format_slots(result)

        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=text)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(uri="connectors://info", name="Account Info", mimeType="text/plain"),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "connectors://info":
        return "connectors.ai — bring your email, calendar, and more to any AI tool."
    raise ValueError(f"Unknown resource: {uri}")


def _format_emails(emails: list[dict]) -> str:
    if not emails:
        return "No emails found."
    lines = []
    for i, m in enumerate(emails, 1):
        lines.append(f"{i}. [{m['id']}] {m['subject']}")
        lines.append(f"   From: {m['from_']}  |  Date: {m['date']}")
        lines.append(f"   {m['snippet'][:100]}")
        lines.append("")
    return "\n".join(lines)


def _format_thread(messages: list[dict]) -> str:
    lines = []
    for i, m in enumerate(messages, 1):
        lines.append(f"--- Message {i} ---")
        lines.append(f"From: {m['from_']}  |  Date: {m['date']}")
        lines.append(f"Subject: {m['subject']}")
        lines.append(m['body'][:500] if m['body'] else m['snippet'])
        lines.append("")
    return "\n".join(lines) or "No messages found."


def _format_events(events: list[dict]) -> str:
    if not events:
        return "No events found in this range."
    lines = []
    for i, e in enumerate(events, 1):
        lines.append(f"{i}. {e['summary']}")
        lines.append(f"   {e['start']} → {e['end']}")
        if e.get("location"):
            lines.append(f"   Location: {e['location']}")
        if e.get("attendees"):
            lines.append(f"   Attendees: {', '.join(e['attendees'])}")
        lines.append("")
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

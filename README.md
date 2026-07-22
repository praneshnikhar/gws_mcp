# gws_mcp

Google Workspace MCP server — bring your Gmail and Google Calendar to any MCP-compatible AI client (Claude, Cursor, etc.).

## Quick start

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8321
# In another terminal:
CONNECTORS_API_KEY=cnx_xxx python -m mcp-server.connectors_mcp.server
```

## API routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/login` | Google OAuth login URL |
| GET | `/auth/callback` | OAuth callback |
| GET | `/api/email/list` | List emails (pagination, search) |
| POST | `/api/email/send` | Send email (with attachments) |
| POST | `/api/email/reply` | Reply to thread |
| POST | `/api/email/forward` | Forward email |
| GET | `/api/email/thread/{id}` | Get thread |
| POST | `/api/email/mark-read` | Mark as read |
| POST | `/api/email/mark-unread` | Mark as unread |
| GET | `/api/email/attachment` | Download attachment |
| GET | `/api/calendar/list` | List calendars |
| GET | `/api/calendar/events` | List events (recurring supported) |
| GET | `/api/calendar/events/{id}` | Get single event |
| POST | `/api/calendar/events` | Create event (RRULE supported) |
| PATCH | `/api/calendar/events/{id}` | Update event |
| DELETE | `/api/calendar/events/{id}` | Delete event |
| GET | `/api/calendar/availability` | Find free slots |
| GET | `/api/working-hours` | Get working hours |
| POST | `/api/working-hours` | Set working hours |
| DELETE | `/api/working-hours` | Delete working hours |

## MCP tools (21 total)

Email: `list_emails`, `send_email`, `reply_email`, `forward_email`, `get_thread`, `mark_read`, `mark_unread`, `get_attachment`

Calendar: `list_calendars`, `list_calendar_events`, `get_calendar_event`, `create_calendar_event`, `update_calendar_event`, `delete_calendar_event`, `get_availability`, `get_working_hours`, `set_working_hours`, `delete_working_hours`

## Contributors

<!-- markdownlint-disable -->
| | |
|:-|:-|
| <img src="https://github.com/praneshnikhar.png" width="40" height="40" alt=""> | **praneshnikhar** — code & architecture |
| <img src="https://avatars.githubusercontent.com/u/81847?v=4" width="40" height="40" alt=""> | **Claude Code** ([@claude](https://github.com/claude)) — AI pair programmer |
<!-- markdownlint-enable -->

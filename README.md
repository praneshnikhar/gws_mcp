# gws_mcp

Connect your Gmail and Google Calendar to AI assistants (Claude, Cursor, etc.) — read, send, and organize email + manage your calendar by talking to AI.

---

## How it works

```
You (in Claude/Cursor)  ◄──►  MCP Server  ◄──►  Backend API  ◄──►  Google
     ask in English          translates           talks to         Gmail +
                             your request         Google APIs      Calendar
                             into API calls
```

The MCP server runs alongside a small Python backend. The backend authenticates with Google and handles email and calendar operations. The MCP server acts as a translator — your AI assistant speaks MCP, the server converts that into API calls, and the backend talks to Google.

---

## What you can do

### Email
- **Read your inbox** — list emails, search by sender/subject/date, paginate through results
- **Send** — compose and send emails to anyone
- **Reply & forward** — reply to existing threads or forward messages
- **Manage drafts** — create drafts without sending, list them, send them later, delete them
- **Organize** — mark emails as read or unread
- **Attachments** — send files (base64 encoded) and download attachments from messages
- **Thread view** — see the full conversation in a thread

### Calendar
- **View events** — list events in any date range, from any of your calendars
- **Create events** — schedule meetings with title, time, location, attendees, description
- **Recurring events** — create repeating events using RRULE (e.g. "every Monday and Wednesday")
- **Update & delete** — modify or remove existing events
- **Find free time** — check availability in a date range, optionally filtered by your working hours
- **Multiple calendars** — manage all your calendars, not just the primary one

### Working Hours
- **Configure** — set your working hours for each day of the week
- **Smart availability** — when checking free slots, filter out time outside your working hours

---

## Setup

### Prerequisites

- Python 3.10+
- A Google Cloud project with Gmail API and Google Calendar API enabled
- Google OAuth credentials (client ID + client secret)

### 1. Get Google API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project or select an existing one
3. Enable the **Gmail API** and **Google Calendar API**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Choose **Web application**, add `http://localhost:8321/auth/callback` as an authorized redirect URI
6. Copy the **Client ID** and **Client Secret**

### 2. Install and start the backend

```bash
# Download the project
git clone https://github.com/praneshnikhar/gws_mcp
cd gws_mcp

# Install Python dependencies
pip install -r backend/requirements.txt

# Set your Google credentials (replace with your actual values)
export CONNECTORS_GOOGLE_CLIENT_ID="your_client_id_here"
export CONNECTORS_GOOGLE_CLIENT_SECRET="your_client_secret_here"

# Start the backend server
uvicorn backend.main:app --reload --port 8321
```

### 3. Get your API key

Open `http://localhost:8321/auth/login` in your browser. You'll be redirected to Google to sign in. After authorizing, you'll receive an API key starting with `cnx_`. **Save this key** — it's shown once.

### 4. Install and run the MCP server

```bash
# Install the MCP server package
pip install mcp-server/

# Start the MCP server (replace cnx_xxx with your actual key)
CONNECTORS_API_KEY=cnx_xxx python -m mcp-server.connectors_mcp.server
```

### 5. Connect your AI assistant

Tell your AI assistant to use the MCP server. The exact method depends on your assistant:

- **Claude Code**: Add the server to your claude.jsonc MCP configuration
- **Cursor**: Configure it in Cursor's MCP settings
- **Any MCP client**: Point it to the stdio command above

---

## Running tests

```bash
pip install pytest pytest-asyncio httpx
PYTHONPATH=. python -m pytest tests/ -v
```

62 tests covering all features.

---

## MCP tools (22 total)

```
Email (12):
  list_emails       — search and list inbox messages
  send_email        — compose and send
  reply_email       — reply to a thread
  forward_email     — forward a message
  get_thread        — view full conversation
  mark_read         — mark as read
  mark_unread       — mark as unread
  get_attachment    — download file from a message
  create_draft      — save a draft
  list_drafts       — view saved drafts
  send_draft        — send a saved draft
  delete_draft      — remove a draft

Calendar (7):
  list_calendars           — show all your calendars
  list_calendar_events     — list events in a date range
  get_calendar_event       — get event details
  create_calendar_event    — schedule a new event
  update_calendar_event    — modify an event
  delete_calendar_event    — remove an event
  get_availability         — find free time slots

Working Hours (3):
  get_working_hours        — view your configured hours
  set_working_hours        — set hours for a day
  delete_working_hours     — remove hours for a day
```

## MCP Prompts

Reusable prompt templates that help the AI understand common workflows:

| Prompt | What it does |
|--------|-------------|
| `summarize-emails` | "Review my last N emails and extract action items" |
| `schedule-meeting` | "Find a free slot, create an event, and invite people" |
| `draft-reply` | "Read a thread and write a professional response" |
| `my-day` | "Give me a morning briefing with today's events and email" |

---

## API reference

All endpoints require `Authorization: Bearer cnx_xxx` header.

### Auth
| Method | Path | What it does |
|--------|------|-------------|
| GET | `/auth/login` | Get Google OAuth URL |
| GET | `/auth/callback?code=&state=` | Complete OAuth (returns API key) |
| GET | `/health` | Check server status |

### Email
| Method | Path | What it does |
|--------|------|-------------|
| GET | `/api/email/list` | List/search with Gmail syntax |
| POST | `/api/email/send` | Send `{to, subject, body}` |
| POST | `/api/email/reply` | Reply `{thread_id, message_id, body}` |
| POST | `/api/email/forward` | Forward `{thread_id, message_id, to, body}` |
| GET | `/api/email/thread/{id}` | Get thread messages |
| POST | `/api/email/mark-read` | Mark as read `{message_id}` |
| POST | `/api/email/mark-unread` | Mark as unread `{message_id}` |
| GET | `/api/email/attachment` | Download attachment |
| POST | `/api/email/drafts` | Create draft `{to, subject, body}` |
| GET | `/api/email/drafts` | List drafts |
| POST | `/api/email/drafts/{id}/send` | Send a draft |
| DELETE | `/api/email/drafts/{id}` | Delete a draft |

### Calendar
| Method | Path | What it does |
|--------|------|-------------|
| GET | `/api/calendar/list` | List all calendars |
| GET | `/api/calendar/events` | List events in date range |
| GET | `/api/calendar/events/{id}` | Get event details |
| POST | `/api/calendar/events` | Create event `{summary, start, end}` |
| PATCH | `/api/calendar/events/{id}` | Update event fields |
| DELETE | `/api/calendar/events/{id}` | Delete event |
| GET | `/api/calendar/availability` | Find free time slots |

### Working Hours
| Method | Path | What it does |
|--------|------|-------------|
| GET | `/api/working-hours` | View configured hours |
| POST | `/api/working-hours` | Set hours for a day |
| DELETE | `/api/working-hours` | Delete hours |

---

## Configuration reference

| Variable | Default | What it is |
|----------|---------|-----------|
| `CONNECTORS_GOOGLE_CLIENT_ID` | — | Your Google OAuth client ID |
| `CONNECTORS_GOOGLE_CLIENT_SECRET` | — | Your Google OAuth client secret |
| `CONNECTORS_GOOGLE_CLIENT_CONFIG` | `~/.connectors/client_secret.json` | Path to client secret file |
| `CONNECTORS_API_KEY` | — | API key (from OAuth setup) |
| `CONNECTORS_API_URL` | `http://localhost:8321` | Backend URL |

## Docker

```bash
docker compose up
```

Runs the backend on port 8321 with persistent storage.

---

## Project structure

```
gws_mcp/
├── backend/                  # FastAPI server
│   ├── main.py              # Routes & app setup
│   ├── auth.py              # Google OAuth
│   ├── db.py                # SQLite storage
│   ├── models.py            # Pydantic schemas
│   └── api/
│       ├── gmail.py         # Gmail operations
│       └── calendar.py      # Calendar operations
├── mcp-server/               # MCP server package
│   └── connectors_mcp/
│       ├── server.py         # MCP tools & prompts
│       └── client.py         # Backend API client
├── tests/                    # 62 tests
├── setup.py                  # OAuth setup wizard
├── Dockerfile
└── docker-compose.yml
```

# connectors.ai MCP Server

Connect your email and calendar to any MCP-compatible AI client.

## 30-second install

1. Go to https://connectors.ai to connect your Google account (OAuth).
2. Copy your API key.
3. Add to your MCP client config:

```json
{
  "mcpServers": {
    "connectors": {
      "command": "npx",
      "args": ["-y", "connectors-mcp"],
      "env": {
        "CONNECTORS_API_KEY": "cnx_..."
      }
    }
  }
}
```

That's it. Your AI can now read emails, check your calendar, find free slots, and send messages on your behalf.

## Tools

- `list_emails` — browse your inbox
- `send_email` — send from your account
- `get_thread` — read a full email thread
- `list_calendar_events` — see what's on your calendar
- `create_calendar_event` — add an event
- `get_availability` — find free time slots

#!/usr/bin/env python3
"""
connectors.ai setup wizard.

Run:  python setup.py

Opens your browser, handles Google OAuth, saves your API key,
and prints the MCP config to paste into Claude/Cursor/etc.
"""

import os
import sys
import json
import webbrowser
import http.server
import urllib.parse
import threading
import time

CONFIG_DIR = os.path.expanduser("~/.connectors")
API_URL = os.environ.get("CONNECTORS_API_URL", "http://localhost:8321")
AUTH_URL = f"{API_URL}/auth/login"


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║       connectors.ai — 30-second setup       ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    # 1. Get auth URL from backend
    import httpx
    try:
        resp = httpx.get(f"{API_URL}/health", timeout=5)
        if resp.status_code != 200:
            print(f"Backend not running at {API_URL}")
            print(f"Start it with:  uvicorn backend.main:app --port 8321")
            sys.exit(1)
    except Exception:
        print(f"Backend not running at {API_URL}")
        print(f"Start it with:  uvicorn backend.main:app --port 8321")
        sys.exit(1)

    resp = httpx.get(AUTH_URL, timeout=10)
    data = resp.json()
    auth_url = data["auth_url"]

    # 2. Open browser
    print("Opening browser for Google login...")
    webbrowser.open(auth_url)

    # 3. Start local server to catch the callback
    api_key = [None]

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params and "state" in params:
                self.send_response(302)
                code = params["code"][0]
                state = params["state"][0]
                # Exchange code ourselves
                import httpx
                try:
                    r = httpx.get(
                        f"{API_URL}/auth/callback",
                        params={"code": code, "state": state},
                        timeout=15,
                    )
                    result = r.json()
                    api_key[0] = result.get("api_key", "")
                    self.send_response(302)
                    self.send_header("Location", "/success")
                except Exception as e:
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(f"<h3>Auth failed: {e}</h3>".encode())
                return

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family:sans-serif;padding:40px">
                <h2>connectors.ai</h2>
                <p>Waiting for Google login...</p>
                </body></html>
            """)

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("localhost", 8322), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"Waiting for authentication...")
    for _ in range(120):
        if api_key[0]:
            break
        time.sleep(0.5)
    server.shutdown()

    if not api_key[0]:
        print("Timed out waiting for authentication.")
        sys.exit(1)

    # 4. Save config
    os.makedirs(CONFIG_DIR, exist_ok=True)
    config_path = os.path.join(CONFIG_DIR, "config")
    with open(config_path, "w") as f:
        f.write(f"CONNECTORS_API_KEY={api_key[0]}\n")

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║           Connected successfully!           ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print("Your API key is saved to ~/.connectors/config")
    print()
    print("Add to Claude Desktop (claude_desktop_config.json):")
    print()
    config_json = {
        "mcpServers": {
            "connectors": {
                "command": "npx",
                "args": ["-y", "connectors-mcp"],
                "env": {
                    "CONNECTORS_API_KEY": api_key[0],
                },
            }
        }
    }
    print(json.dumps(config_json, indent=2))
    print()
    print("Or for Cursor/Windsurf:")
    print("  Set CONNECTORS_API_KEY in your MCP server env.")
    print()


if __name__ == "__main__":
    main()

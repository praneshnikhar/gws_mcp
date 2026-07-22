import os
import secrets
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]

CLIENT_CONFIG = None


def load_client_config():
    global CLIENT_CONFIG
    client_id = os.environ.get("CONNECTORS_GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("CONNECTORS_GOOGLE_CLIENT_SECRET")

    if client_id and client_secret:
        CLIENT_CONFIG = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8321/auth/callback"],
            }
        }
        return

    config_path = os.environ.get(
        "CONNECTORS_GOOGLE_CLIENT_CONFIG",
        os.path.expanduser("~/.connectors/client_secret.json"),
    )
    if os.path.exists(config_path):
        with open(config_path) as f:
            CLIENT_CONFIG = json.load(f)
        return

    raise RuntimeError(
        "Set CONNECTORS_GOOGLE_CLIENT_ID and CONNECTORS_GOOGLE_CLIENT_SECRET, "
        "or provide a client_secret.json at ~/.connectors/client_secret.json"
    )


def create_flow(state: str, redirect_uri: str = "http://localhost:8321/auth/callback") -> Flow:
    if CLIENT_CONFIG is None:
        load_client_config()
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    flow.state = state
    return flow


def get_auth_url() -> tuple[str, str]:
    state = secrets.token_urlsafe(32)
    flow = create_flow(state)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state


def exchange_code(code: str, state: str, redirect_uri: str = "http://localhost:8321/auth/callback") -> dict:
    flow = create_flow(state, redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "token": creds.to_json(),
        "email": _get_email(creds),
        "name": _get_name(creds),
    }


def refresh_google_token(token_json: str, email: str | None = None) -> str:
    creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        new_token = creds.to_json()
        if email:
            from backend.db import update_user_token
            update_user_token(email, new_token)
        return new_token
    return token_json


def _get_email(creds: Credentials) -> str:
    import httpx
    resp = httpx.get(
        "https://www.googleapis.com/oauth2/v1/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
    )
    return resp.json().get("email", "unknown")


def _get_name(creds: Credentials) -> str:
    import httpx
    resp = httpx.get(
        "https://www.googleapis.com/oauth2/v1/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
    )
    return resp.json().get("name", "User")

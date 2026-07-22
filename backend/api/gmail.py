import json
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from backend.auth import refresh_google_token, SCOPES


API_SERVICE_NAME = "gmail"


def _get_service(token_json: str, email: str | None = None):
    try:
        token = refresh_google_token(token_json, email)
    except Exception as e:
        raise RuntimeError(f"Failed to refresh Google token: {e}")
    creds = Credentials.from_authorized_user_info(json.loads(token), SCOPES)
    return build("gmail", "v1", credentials=creds)


def _handle_google_error(e: HttpError, action: str):
    if e.resp.status == 403:
        raise RuntimeError(f"Insufficient permissions to {action}. Re-authentication may be required.")
    if e.resp.status == 404:
        raise RuntimeError(f"Resource not found while trying to {action}.")
    if e.resp.status == 429:
        raise RuntimeError(f"Google API rate limit exceeded. Try again later.")
    raise RuntimeError(f"Google API error while {action}: {e.resp.status} {e.reason}")


def list_messages(token_json: str, max_results: int = 20, query: str = "", email: str | None = None) -> list[dict]:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    try:
        results = service.users().messages().list(
            userId="me", maxResults=max_results, q=query
        ).execute()
    except HttpError as e:
        _handle_google_error(e, "listing emails")

    messages = []
    for msg in results.get("messages", []):
        try:
            full = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "To", "Date"],
            ).execute()
        except HttpError as e:
            _handle_google_error(e, f"fetching email {msg['id']}")
        headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
        messages.append({
            "id": full["id"],
            "thread_id": full["threadId"],
            "subject": headers.get("Subject", "(no subject)"),
            "from_": headers.get("From", ""),
            "to": headers.get("To", ""),
            "snippet": full.get("snippet", ""),
            "date": headers.get("Date", ""),
            "labels": full.get("labelIds", []),
        })

    return messages


def send_message(token_json: str, to: list[str], subject: str, body: str,
                 cc: list[str] | None = None, bcc: list[str] | None = None,
                 email: str | None = None) -> dict:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except HttpError as e:
        _handle_google_error(e, "sending email")
    return {"id": sent["id"], "thread_id": sent["threadId"]}


def get_thread(token_json: str, thread_id: str, email: str | None = None) -> list[dict]:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    try:
        thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    except HttpError as e:
        _handle_google_error(e, f"fetching thread {thread_id}")

    messages = []
    for msg in thread.get("messages", []):
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        body = ""
        if msg["payload"].get("parts"):
            for part in msg["payload"]["parts"]:
                if part["mimeType"] == "text/plain" and part["body"].get("data"):
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                    break
        elif msg["payload"]["body"].get("data"):
            body = base64.urlsafe_b64decode(msg["payload"]["body"]["data"]).decode("utf-8", errors="replace")

        messages.append({
            "id": msg["id"],
            "from_": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "body": body,
            "snippet": msg.get("snippet", ""),
        })

    return messages

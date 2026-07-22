import json
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from backend.auth import refresh_google_token, SCOPES


def _get_service(token_json: str):
    token = refresh_google_token(token_json)
    creds = Credentials.from_authorized_user_info(json.loads(token), SCOPES)
    return build("gmail", "v1", credentials=creds)


def list_messages(token_json: str, max_results: int = 20, query: str = "") -> list[dict]:
    service = _get_service(token_json)
    results = service.users().messages().list(
        userId="me", maxResults=max_results, q=query
    ).execute()

    messages = []
    for msg in results.get("messages", []):
        full = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["Subject", "From", "To", "Date"],
        ).execute()
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


def send_message(token_json: str, to: list[str], subject: str, body: str, cc: list[str] = None, bcc: list[str] = None):
    service = _get_service(token_json)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"id": sent["id"], "thread_id": sent["threadId"]}


def get_thread(token_json: str, thread_id: str) -> list[dict]:
    service = _get_service(token_json)
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()

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

import json
import base64
import os
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.audio import MIMEAudio
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.utils import formatdate, parsedate_to_datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from backend.auth import refresh_google_token, SCOPES


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


def _get_message_headers(msg: dict) -> dict:
    return {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}


def _extract_body(msg: dict) -> str:
    payload = msg["payload"]
    if payload.get("parts"):
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain" and part["body"].get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        for part in payload["parts"]:
            if part["mimeType"] == "text/html" and part["body"].get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    if payload["body"].get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    return ""


def _extract_attachments(service, user_id: str, msg_id: str, payload: dict) -> list[dict]:
    parts = [payload]
    attachments = []
    while parts:
        part = parts.pop()
        if part.get("parts"):
            parts.extend(part["parts"])
        filename = part.get("filename", "")
        if filename and part["body"].get("attachmentId"):
            attachment_id = part["body"]["attachmentId"]
            att = service.users().messages().attachments().get(
                userId=user_id, messageId=msg_id, id=attachment_id
            ).execute()
            data = att.get("data", "")
            attachments.append({
                "filename": filename,
                "mime_type": part.get("mimeType", "application/octet-stream"),
                "size": att.get("size", 0),
                "data": data,
                "attachment_id": attachment_id,
            })
    return attachments


# ── List / Search ────────────────────────────────────────────────────────

def list_messages(token_json: str, max_results: int = 20, query: str = "",
                  page_token: str | None = None,
                  email: str | None = None) -> tuple[list[dict], str | None]:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    params = {"userId": "me", "maxResults": max_results}
    if query:
        params["q"] = query
    if page_token:
        params["pageToken"] = page_token

    try:
        results = service.users().messages().list(**params).execute()
    except HttpError as e:
        _handle_google_error(e, "listing emails")

    next_page_token = results.get("nextPageToken")

    messages = []
    for msg in results.get("messages", []):
        try:
            full = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "To", "Date"],
            ).execute()
        except HttpError as e:
            _handle_google_error(e, f"fetching email {msg['id']}")
        headers = _get_message_headers(full)
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

    return messages, next_page_token


# ── Send ─────────────────────────────────────────────────────────────────

def _build_mime(to: list[str], subject: str, body: str,
                cc: list[str] | None = None, bcc: list[str] | None = None,
                in_reply_to: str | None = None, references: str | None = None,
                attachments: list[dict] | None = None) -> bytes:
    has_attachments = attachments and any(a.get("content") or a.get("filepath") for a in attachments)

    if has_attachments:
        msg = MIMEMultipart("mixed")
        text_part = MIMEText(body, "plain")
        msg.attach(text_part)
    else:
        msg = MIMEText(body, "plain")

    msg["Subject"] = subject
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Date"] = formatdate()
    msg["Message-ID"] = f"<{uuid.uuid4().hex}@gws-mcp>"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    if has_attachments:
        for att in attachments:
            content = att.get("content")
            filepath = att.get("filepath")
            if filepath and os.path.exists(filepath):
                with open(filepath, "rb") as f:
                    content = base64.b64encode(f.read()).decode()
            if not content:
                continue
            decoded = base64.b64decode(content)
            filename = att.get("filename", "attachment")
            mime_type = att.get("mime_type", "application/octet-stream")
            maintype, subtype = mime_type.split("/", 1)

            part = MIMEBase(maintype, subtype)
            part.set_payload(decoded)
            import email.encoders
            email.encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)

    return msg.as_bytes()


def send_message(token_json: str, to: list[str], subject: str, body: str,
                 cc: list[str] | None = None, bcc: list[str] | None = None,
                 attachments: list[dict] | None = None,
                 email: str | None = None) -> dict:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    raw_bytes = _build_mime(to, subject, body, cc, bcc, attachments=attachments)
    raw = base64.urlsafe_b64encode(raw_bytes).decode()

    try:
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except HttpError as e:
        _handle_google_error(e, "sending email")
    return {"id": sent["id"], "thread_id": sent["threadId"]}


# ── Reply / Forward ──────────────────────────────────────────────────────

def _get_original_headers(service, msg_id: str) -> dict:
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="metadata",
        metadataHeaders=["Message-ID", "References", "Subject", "From", "To", "Cc"],
    ).execute()
    return _get_message_headers(msg)


def reply_message(token_json: str, thread_id: str, message_id: str,
                  body: str, cc: list[str] | None = None,
                  email: str | None = None) -> dict:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    headers = _get_original_headers(service, message_id)
    orig_subject = headers.get("Subject", "")
    if not orig_subject.lower().startswith("re:"):
        subject = f"Re: {orig_subject}"
    else:
        subject = orig_subject

    orig_msg_id = headers.get("Message-ID", "")
    orig_refs = headers.get("References", "")
    references = f"{orig_refs} {orig_msg_id}".strip()

    orig_to = headers.get("From", "")  # reply to original sender
    orig_cc = headers.get("Cc", "")

    raw_bytes = _build_mime(
        to=[orig_to],
        subject=subject,
        body=body,
        cc=cc,
        in_reply_to=orig_msg_id,
        references=references,
    )
    raw = base64.urlsafe_b64encode(raw_bytes).decode()

    try:
        sent = service.users().messages().send(
            userId="me", body={"raw": raw, "threadId": thread_id}
        ).execute()
    except HttpError as e:
        _handle_google_error(e, "replying to email")
    return {"id": sent["id"], "thread_id": sent["threadId"]}


def forward_message(token_json: str, thread_id: str, message_id: str,
                    to: list[str], body: str, cc: list[str] | None = None,
                    email: str | None = None) -> dict:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    headers = _get_original_headers(service, message_id)
    orig_subject = headers.get("Subject", "")
    if not orig_subject.lower().startswith("fwd:"):
        subject = f"Fwd: {orig_subject}"
    else:
        subject = orig_subject

    # Get original message body to include
    orig = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    orig_body = _extract_body(orig)
    orig_from = headers.get("From", "")
    orig_date = headers.get("Date", "")

    forwarded_body = (
        f"{body}\n\n"
        f"---------- Forwarded message ---------\n"
        f"From: {orig_from}\n"
        f"Date: {orig_date}\n"
        f"Subject: {headers.get('Subject', '')}\n\n"
        f"{orig_body}"
    )

    raw_bytes = _build_mime(to, subject, forwarded_body, cc)
    raw = base64.urlsafe_b64encode(raw_bytes).decode()

    try:
        sent = service.users().messages().send(
            userId="me", body={"raw": raw, "threadId": thread_id}
        ).execute()
    except HttpError as e:
        _handle_google_error(e, "forwarding email")
    return {"id": sent["id"], "thread_id": sent["threadId"]}


# ── Thread ───────────────────────────────────────────────────────────────

def get_thread(token_json: str, thread_id: str,
               include_attachments: bool = False,
               email: str | None = None) -> list[dict]:
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
        headers = _get_message_headers(msg)
        entry = {
            "id": msg["id"],
            "from_": headers.get("From", ""),
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "body": _extract_body(msg),
            "snippet": msg.get("snippet", ""),
        }
        if include_attachments:
            entry["attachments"] = _extract_attachments(service, "me", msg["id"], msg["payload"])
        messages.append(entry)

    return messages


# ── Labels / Modify ──────────────────────────────────────────────────────

def modify_message_labels(token_json: str, message_id: str,
                          add_labels: list[str] | None = None,
                          remove_labels: list[str] | None = None,
                          email: str | None = None) -> dict:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    body = {}
    if add_labels:
        body["addLabelIds"] = add_labels
    if remove_labels:
        body["removeLabelIds"] = remove_labels

    try:
        result = service.users().messages().modify(
            userId="me", id=message_id, body=body
        ).execute()
    except HttpError as e:
        _handle_google_error(e, "modifying email labels")
    return {"id": result["id"], "labels": result.get("labelIds", [])}


def mark_read(token_json: str, message_id: str, email: str | None = None) -> dict:
    return modify_message_labels(token_json, message_id, remove_labels=["UNREAD"], email=email)


def mark_unread(token_json: str, message_id: str, email: str | None = None) -> dict:
    return modify_message_labels(token_json, message_id, add_labels=["UNREAD"], email=email)


# ── Attachments ──────────────────────────────────────────────────────────

def get_attachment(token_json: str, message_id: str, attachment_id: str,
                   email: str | None = None) -> dict:
    try:
        service = _get_service(token_json, email)
    except RuntimeError as e:
        raise

    try:
        att = service.users().messages().attachments().get(
            userId="me", messageId=message_id, id=attachment_id
        ).execute()
    except HttpError as e:
        _handle_google_error(e, "fetching attachment")

    return {
        "data": att.get("data", ""),
        "size": att.get("size", 0),
        "mime_type": att.get("mimeType", "application/octet-stream"),
    }

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.expanduser("~/.connectors/auth.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            google_token TEXT NOT NULL,
            api_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_api_key ON users(api_key);
    """)
    conn.commit()
    conn.close()


def save_user(email: str, name: str, google_token: str, api_key: str):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO users (email, name, google_token, api_key)
           VALUES (?, ?, ?, ?)""",
        (email, name, google_token, api_key),
    )
    conn.commit()
    conn.close()


def get_user_by_api_key(api_key: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE api_key = ?", (api_key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_token(email: str, google_token: str):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET google_token = ? WHERE email = ?",
        (google_token, email),
    )
    conn.commit()
    conn.close()

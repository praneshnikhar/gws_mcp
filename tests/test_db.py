import os
import tempfile
from backend.db import get_conn, init_db, save_user, get_user_by_api_key, get_user_by_email, update_user_token

DB_PATH_ORIG = None


def setup_module():
    global DB_PATH_ORIG
    from backend import db
    DB_PATH_ORIG = db.DB_PATH
    db.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")


def test_init_db():
    init_db()
    conn = get_conn()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = [r["name"] for r in tables]
    assert "users" in names
    assert "working_hours" in names
    conn.close()


def test_save_and_get_user():
    save_user("test@example.com", "Test User", '{"token":"abc"}', "cnx_test123")
    user = get_user_by_api_key("cnx_test123")
    assert user is not None
    assert user["email"] == "test@example.com"
    assert user["name"] == "Test User"

    user2 = get_user_by_email("test@example.com")
    assert user2 is not None
    assert user2["api_key"] == "cnx_test123"


def test_update_token():
    save_user("test2@example.com", "Test2", '{"token":"old"}', "cnx_test456")
    update_user_token("test2@example.com", '{"token":"new"}')
    user = get_user_by_email("test2@example.com")
    assert user["google_token"] == '{"token":"new"}'

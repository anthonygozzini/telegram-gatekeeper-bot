"""SQLite storage: applications, profiles already used, and joins/leaves of the private group."""
import json
import sqlite3
import time
from contextlib import closing

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    full_name TEXT,
    answers TEXT NOT NULL,
    signals TEXT NOT NULL,
    decision TEXT NOT NULL,
    decided_by TEXT,
    invite_link TEXT,
    created_at INTEGER NOT NULL,
    decided_at INTEGER
);
CREATE INDEX IF NOT EXISTS applications_user ON applications(user_id);
CREATE TABLE IF NOT EXISTS profiles (
    profile_key TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (profile_key, user_id)
);
CREATE TABLE IF NOT EXISTS member_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    full_name TEXT,
    action TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path):
        self.path = path
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def last_application_time(self, user_id):
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT MAX(created_at) AS t FROM applications WHERE user_id = ?", (user_id,)).fetchone()
        return row["t"]

    def profiles_used_by_others(self, profile_keys, user_id):
        if not profile_keys:
            return []
        with closing(self._connect()) as conn:
            marks = ",".join("?" for _ in profile_keys)
            rows = conn.execute(
                f"SELECT DISTINCT profile_key FROM profiles WHERE profile_key IN ({marks}) AND user_id != ?",
                (*profile_keys, user_id),
            ).fetchall()
        return sorted(row["profile_key"] for row in rows)

    def add_application(self, user_id, username, full_name, answers, signals, profile_keys, decision, now=None):
        now = int(now if now is not None else time.time())
        decided_at = None if decision == "review" else now
        decided_by = None if decision == "review" else "auto"
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT INTO applications (user_id, username, full_name, answers, signals, decision, decided_by, created_at, decided_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, full_name, json.dumps(answers), json.dumps(signals), decision, decided_by, now, decided_at),
            )
            conn.executemany(
                "INSERT OR IGNORE INTO profiles (profile_key, user_id) VALUES (?, ?)",
                [(key, user_id) for key in profile_keys],
            )
            return cursor.lastrowid

    def get_application(self, application_id):
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        if row is None:
            return None
        application = dict(row)
        application["answers"] = json.loads(application["answers"])
        application["signals"] = json.loads(application["signals"])
        return application

    def claim_review(self, application_id, decision, decided_by, now=None):
        """Record an admin decision once. Returns False if the application was already decided."""
        now = int(now if now is not None else time.time())
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "UPDATE applications SET decision = ?, decided_by = ?, decided_at = ? WHERE id = ? AND decision = 'review'",
                (decision, decided_by, now, application_id),
            )
            return cursor.rowcount == 1

    def set_invite_link(self, application_id, invite_link):
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE applications SET invite_link = ? WHERE id = ?", (invite_link, application_id))

    def add_member_event(self, user_id, username, full_name, action, chat_id, now=None):
        now = int(now if now is not None else time.time())
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO member_events (user_id, username, full_name, action, chat_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, full_name, action, chat_id, now),
            )

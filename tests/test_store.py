import sqlite3
from contextlib import closing

from gatekeeper.store import Store


def test_review_flow(tmp_path):
    store = Store(str(tmp_path / "g.db"))
    assert store.last_application_time(1) is None
    app_id = store.add_application(1, "mario", "Mario Rossi", {"profile": "x:mario"}, [], ["x:mario"], "review", now=1000)
    assert store.last_application_time(1) == 1000
    assert store.profiles_used_by_others(["x:mario"], 1) == []
    assert store.profiles_used_by_others(["x:mario"], 2) == ["x:mario"]
    assert store.claim_review(app_id, "approved", "@admin", now=2000) is True
    assert store.claim_review(app_id, "rejected", "@other", now=2001) is False
    store.set_invite_link(app_id, "https://t.me/+example")
    saved = store.get_application(app_id)
    assert (saved["decision"], saved["decided_by"], saved["invite_link"]) == ("approved", "@admin", "https://t.me/+example")
    assert saved["answers"] == {"profile": "x:mario"}


def test_automatic_decisions_are_final(tmp_path):
    store = Store(str(tmp_path / "g.db"))
    app_id = store.add_application(3, None, "Someone", {}, [], [], "approve")
    assert store.claim_review(app_id, "rejected", "@admin") is False
    assert store.get_application(app_id)["decided_by"] == "auto"


def test_member_events(tmp_path):
    path = str(tmp_path / "g.db")
    Store(path).add_member_event(5, "user", "User", "joined", -1001, now=1)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT action, chat_id FROM member_events").fetchall() == [("joined", -1001)]

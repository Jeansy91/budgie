"""Automatic FinTS fetch: PIN storage, unattended jobs and the scheduler (simulated bank)."""

from datetime import UTC, datetime, timedelta

import pytest
from fints.exceptions import FinTSConnectionError
from fints.utils import mt940_to_array
from sqlalchemy import delete, select

from app import crypto
from app.db import SessionLocal
from app.fints import autosync, jobs, scheduler
from app.models import BankConnection, Transaction

from .conftest import DATA, find_category
from .test_fints import FakeBank, connect, fake_bank, wait  # noqa: F401  (fixture)

PIN = "12345"


class QuietBank(FakeBank):
    """A bank that needs no TAN for fetching transactions (as long as the session is known)."""

    def get_transactions(self, account, start_date, end_date):
        self.ranges.append((start_date, end_date))
        return mt940_to_array((DATA / "ing_beispiel.mt940").read_text())


def manual_sync(client, conn_id):
    job = client.post(f"/api/fints/connections/{conn_id}/sync", json={"pin": PIN}).json()
    assert wait(client, job["id"])["state"] == "done"


def enable(client, conn_id, **extra):
    r = client.patch(f"/api/fints/connections/{conn_id}", json={"auto_sync_enabled": True, "pin": PIN, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def row(conn_id) -> BankConnection:
    with SessionLocal() as db:
        c = db.get(BankConnection, conn_id)
        db.expunge(c)
        return c


def make_due(conn_id):
    with SessionLocal() as db:
        db.get(BankConnection, conn_id).next_auto_sync_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()


@pytest.fixture
def synced(admin):
    """A connection with one manual sync done and auto sync enabled."""
    conn = connect(admin)
    manual_sync(admin, conn["id"])
    enable(admin, conn["id"])
    make_due(conn["id"])
    return conn["id"]


# --- API ---------------------------------------------------------------------------


def test_enabling_requires_pin(admin):
    conn = connect(admin)
    assert conn["auto_sync_enabled"] is False and conn["auto_sync_interval_hours"] == 12
    r = admin.patch(f"/api/fints/connections/{conn['id']}", json={"auto_sync_enabled": True})
    assert r.status_code == 400
    assert row(conn["id"]).auto_sync_enabled is False


def test_interval_is_validated(admin):
    conn = connect(admin)
    r = admin.patch(f"/api/fints/connections/{conn['id']}", json={"auto_sync_interval_hours": 5, "pin": PIN})
    assert r.status_code == 422
    out = enable(admin, conn["id"], auto_sync_interval_hours=6)
    assert out["auto_sync_interval_hours"] == 6 and out["next_auto_sync_at"]


def test_pin_is_stored_encrypted_and_never_returned(admin):
    conn = connect(admin)
    out = enable(admin, conn["id"])
    assert out["auto_sync_enabled"] is True and out["has_stored_pin"] is True
    # Nothing first synced yet: the user has to start with a manual fetch
    assert out["auto_sync_paused_reason"] == "manual_sync_required"
    assert PIN not in str(out) and "pin" not in {k for k in out if k != "has_stored_pin"}
    assert PIN not in str(admin.get("/api/fints/connections").json())
    stored = row(conn["id"])
    assert PIN not in stored.pin_enc and crypto.decrypt(stored.pin_enc) == PIN.encode()


def test_disabling_deletes_pin(admin):
    conn = connect(admin)
    enable(admin, conn["id"])
    out = admin.patch(f"/api/fints/connections/{conn['id']}", json={"auto_sync_enabled": False}).json()
    assert out["auto_sync_enabled"] is False and out["has_stored_pin"] is False
    assert out["next_auto_sync_at"] is None and out["auto_sync_paused_reason"] is None
    assert row(conn["id"]).pin_enc is None


def test_changing_login_clears_pin_and_disables(admin):
    conn = connect(admin)
    manual_sync(admin, conn["id"])
    enable(admin, conn["id"])
    out = admin.patch(f"/api/fints/connections/{conn['id']}", json={"login": "9999999999"}).json()
    assert out["auto_sync_enabled"] is False and out["has_stored_pin"] is False
    assert row(conn["id"]).pin_enc is None
    enable(admin, conn["id"])
    out = admin.patch(f"/api/fints/connections/{conn['id']}", json={"customer_id": "abc"}).json()
    assert out["auto_sync_enabled"] is False and out["has_stored_pin"] is False


def test_interval_change_keeps_unresolved_pause(admin, synced):
    with SessionLocal() as db:
        db.get(BankConnection, synced).auto_sync_paused_reason = "tan_required"
        db.commit()
    out = admin.patch(f"/api/fints/connections/{synced}", json={"auto_sync_interval_hours": 24}).json()
    assert out["auto_sync_interval_hours"] == 24 and out["auto_sync_paused_reason"] == "tan_required"


# --- Unattended sync -----------------------------------------------------------------


def test_unattended_run_imports_and_categorizes(admin, synced, monkeypatch):
    stadtwerke = find_category(admin, "Wohnen", "Strom")
    admin.post("/api/rules", json={"category_id": stadtwerke, "pattern": "stadtwerke"})
    # Remove the transactions of the manual sync so the unattended run has something to import
    with SessionLocal() as db:
        db.execute(delete(Transaction))
        db.commit()
    assert admin.get("/api/transactions").json()["items"] == []
    monkeypatch.setattr(jobs, "client_factory", QuietBank)
    assert scheduler.run_due_once() == 1

    bank = QuietBank.instances[-1]
    assert bank.pin == PIN and bank.from_data == b"gespeicherter-zustand"
    items = admin.get("/api/transactions", params={"q": "Stadtwerke"}).json()["items"]
    assert len(items) == 1 and items[0]["category_id"] == stadtwerke
    c = row(synced)
    assert c.auto_sync_failures == 0 and c.auto_sync_paused_reason is None
    assert c.next_auto_sync_at > datetime.now(UTC) + timedelta(hours=11)
    assert c.last_sync_at > datetime.now(UTC) - timedelta(minutes=1)
    # Not due any more
    assert scheduler.run_due_once() == 0


def test_unattended_tan_request_pauses_without_polling(admin, synced, monkeypatch):
    sent = []
    monkeypatch.setattr(FakeBank, "send_tan", lambda self, *a: sent.append(a))
    assert scheduler.run_due_once() == 1
    assert sent == []
    c = row(synced)
    assert c.auto_sync_paused_reason == "tan_required"
    assert c.auto_sync_enabled is True and c.pin_enc is not None
    assert c.last_error and c.next_auto_sync_at is None
    out = admin.get("/api/fints/connections").json()[0]
    assert out["auto_sync_paused_reason"] == "tan_required"
    # Paused connections are skipped; only one bank dialog was ever opened
    make_due(synced)
    n = len(FakeBank.instances)
    assert scheduler.run_due_once() == 0
    assert len(FakeBank.instances) == n


def test_unattended_never_asks_for_choice(admin, synced):
    with SessionLocal() as db:
        db.get(BankConnection, synced).tan_mechanism = None
        db.get(BankConnection, synced).client_state_enc = crypto.encrypt(b"x")
        db.commit()
    assert scheduler.run_due_once() == 1
    # A reset TAN mechanism would require a choice: abort instead of waiting
    assert row(synced).auto_sync_paused_reason == "manual_sync_required"


def test_unattended_needs_first_manual_sync(admin):
    conn = connect(admin)
    enable(admin, conn["id"])
    with SessionLocal() as db:  # even if the pause marker were missing
        c = db.get(BankConnection, conn["id"])
        c.auto_sync_paused_reason = None
        c.next_auto_sync_at = None
        db.commit()
    assert scheduler.run_due_once() == 1
    assert row(conn["id"]).auto_sync_paused_reason == "manual_sync_required"
    assert FakeBank.instances == []  # no bank dialog opened


def test_pin_rejected_deletes_pin_and_pauses(admin, synced, monkeypatch):
    monkeypatch.setattr(FakeBank, "wrong_pin", True)
    assert scheduler.run_due_once() == 1
    c = row(synced)
    assert c.auto_sync_paused_reason == "pin_rejected" and c.pin_enc is None
    assert c.auto_sync_enabled is True
    out = admin.get("/api/fints/connections").json()[0]
    assert out["has_stored_pin"] is False
    # Entering the PIN again resumes
    out = enable(admin, synced)
    assert out["auto_sync_paused_reason"] is None and out["has_stored_pin"] is True


def test_temporary_lock_pauses(admin, synced, monkeypatch):
    from fints.exceptions import FinTSClientTemporaryAuthError

    def locked(self):
        raise FinTSClientTemporaryAuthError("gesperrt")

    monkeypatch.setattr(FakeBank, "__enter__", locked)
    scheduler.run_due_once()
    c = row(synced)
    assert c.auto_sync_paused_reason == "locked" and c.pin_enc is not None


def test_transient_error_backs_off_then_recovers(admin, synced, monkeypatch):
    def broken(self):
        raise FinTSConnectionError("down")

    monkeypatch.setattr(FakeBank, "__enter__", broken)
    scheduler.run_due_once()
    c = row(synced)
    assert c.auto_sync_failures == 1 and c.auto_sync_paused_reason is None and c.pin_enc is not None
    # 12 h interval doubled once = 24 h, plus up to 10 % jitter of the interval
    wait_h = (c.next_auto_sync_at - datetime.now(UTC)).total_seconds() / 3600
    assert 23.9 < wait_h < 25.3

    make_due(synced)
    scheduler.run_due_once()
    assert row(synced).auto_sync_failures == 2

    monkeypatch.undo()
    monkeypatch.setattr(jobs, "client_factory", QuietBank)
    make_due(synced)
    scheduler.run_due_once()
    c = row(synced)
    assert c.auto_sync_failures == 0 and c.last_error is None


def test_backoff_is_capped():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert autosync.next_run(24, failures=5, now=now) <= now + timedelta(hours=48 + 2.4)
    assert autosync.next_run(6, failures=0, now=now) >= now + timedelta(hours=6)


def test_manual_sync_clears_pause(admin, synced, monkeypatch):
    with SessionLocal() as db:
        c = db.get(BankConnection, synced)
        c.auto_sync_paused_reason = "tan_required"
        c.auto_sync_failures = 3
        c.next_auto_sync_at = None
        db.commit()
    manual_sync(admin, synced)
    c = row(synced)
    assert c.auto_sync_paused_reason is None and c.auto_sync_failures == 0
    assert c.next_auto_sync_at > datetime.now(UTC) + timedelta(hours=11)
    out = admin.get("/api/fints/connections").json()[0]
    assert out["auto_sync_paused_reason"] is None and out["last_sync_at"]


# --- Scheduler selection ------------------------------------------------------------------


def test_due_selection(admin, synced):
    now = datetime.now(UTC)

    def ids():
        with SessionLocal() as db:
            return scheduler.due_connection_ids(db, now)

    assert ids() == [synced]
    with SessionLocal() as db:
        c = db.get(BankConnection, synced)
        c.next_auto_sync_at = now + timedelta(hours=1)
        db.commit()
    assert ids() == []
    with SessionLocal() as db:
        c = db.get(BankConnection, synced)
        c.next_auto_sync_at = None  # never scheduled: due
        db.commit()
    assert ids() == [synced]
    with SessionLocal() as db:
        db.get(BankConnection, synced).auto_sync_paused_reason = "locked"
        db.commit()
    assert ids() == []
    with SessionLocal() as db:
        c = db.get(BankConnection, synced)
        c.auto_sync_paused_reason = None
        c.pin_enc = None
        db.commit()
    assert ids() == []
    with SessionLocal() as db:
        c = db.get(BankConnection, synced)
        c.pin_enc = crypto.encrypt(PIN)
        c.auto_sync_enabled = False
        db.commit()
    assert ids() == []


def test_scheduler_skips_when_fints_not_configured(admin, synced, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "fints_product_id", "")
    n = len(FakeBank.instances)
    assert scheduler.run_due_once() == 0
    assert len(FakeBank.instances) == n


def test_scheduler_skips_connection_with_running_manual_job(admin, synced, monkeypatch):
    monkeypatch.setattr(FakeBank, "polls_until_approved", 10_000)
    job = admin.post(f"/api/fints/connections/{synced}/sync", json={"pin": PIN}).json()
    wait(admin, job["id"], until=("need_tan",))
    assert scheduler.run_due_once() == 0
    admin.post(f"/api/fints/jobs/{job['id']}/cancel")
    wait(admin, job["id"])
    assert row(synced).auto_sync_paused_reason is None


def test_locale_of_user_is_used(admin, synced, monkeypatch):
    with SessionLocal() as db:
        from app.models import User

        db.scalar(select(User)).language = "en"
        db.commit()
    scheduler.run_due_once()
    assert "manual fetch" in row(synced).last_error

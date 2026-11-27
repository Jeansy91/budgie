"""Periodic automatic FinTS fetch.

One daemon thread wakes up about every minute, looks for connections that are
due and runs them one after another, so there is never more than one bank
dialog at a time. The fetch itself is the normal sync job in unattended mode
(see jobs.py), so imports, rules and AI categorization behave exactly like a
manual sync. The API runs as exactly one uvicorn process, so there is exactly
one scheduler.

Logs only mention the connection ID, never the login or an IBAN.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from sqlalchemy import or_, select

from ..db import SessionLocal
from ..i18n import DEFAULT_LOCALE, use_locale
from ..models import BankConnection, User
from . import autosync, jobs

log = logging.getLogger(__name__)

# Seconds between two checks for due connections
CHECK_INTERVAL_SECONDS = 60
# Delay after startup, so the API is up and migrated first
STARTUP_DELAY_SECONDS = 15
# A single unattended fetch must not block the scheduler forever
MAX_JOB_SECONDS = 30 * 60

_stop = threading.Event()
_thread: threading.Thread | None = None


def due_connection_ids(db, now: datetime) -> list[int]:
    """Connections that are enabled, not paused, have a stored PIN and are due."""
    return list(
        db.scalars(
            select(BankConnection.id)
            .where(
                BankConnection.auto_sync_enabled.is_(True),
                BankConnection.auto_sync_paused_reason.is_(None),
                BankConnection.pin_enc.is_not(None),
                or_(BankConnection.next_auto_sync_at.is_(None), BankConnection.next_auto_sync_at <= now),
            )
            .order_by(BankConnection.next_auto_sync_at.asc().nulls_first(), BankConnection.id)
        )
    )


def run_due_once(now: datetime | None = None) -> int:
    """Fetches all due connections one after another. Returns how many were started."""
    from ..routers.fints import _missing

    if _missing():
        return 0
    now = now or datetime.now(UTC)
    with SessionLocal() as db:
        ids = due_connection_ids(db, now)
    started = 0
    for connection_id in ids:
        if _stop.is_set():
            break
        if _run_connection(connection_id):
            started += 1
    return started


def _run_connection(connection_id: int) -> bool:
    with SessionLocal() as db:
        connection = db.get(BankConnection, connection_id)
        # Re-check: the user may have changed it since the list was read
        if connection is None or not connection.auto_sync_enabled or connection.auto_sync_paused_reason:
            return False
        user = db.get(User, connection.user_id)
        if user is None:
            return False
        try:
            pin = autosync.get_pin(connection)
        except Exception as exc:
            log.warning("Auto sync: PIN of connection %s cannot be read", connection_id)
            autosync.apply_failure(connection, exc)
            connection.last_error = str(exc)
            db.commit()
            return False
        if pin is None:
            return False
        with use_locale(user.language or DEFAULT_LOCALE):
            try:
                job = jobs.start_sync(connection, user, pin, None, unattended=True)
            except jobs.JobFailed:
                # A manual sync is running for this connection; try again at the next check
                return False
        log.info("Auto sync started for connection %s", connection_id)
        if not job.wait(MAX_JOB_SECONDS):
            log.warning("Auto sync for connection %s takes unusually long", connection_id)
        else:
            log.info("Auto sync for connection %s finished: %s", connection_id, job.state)
        return True


def _loop() -> None:
    if _stop.wait(STARTUP_DELAY_SECONDS):
        return
    while not _stop.is_set():
        try:
            run_due_once()
        except Exception:
            log.exception("Auto sync check failed")
        if _stop.wait(CHECK_INTERVAL_SECONDS):
            return


def start() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="fints-scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)

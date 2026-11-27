"""Rules for automatic (unattended) FinTS fetches.

This module holds everything about *when* and *with which PIN* a connection is
fetched without the user being present. The actual bank dialog lives in
`jobs.py`, the periodic trigger in `scheduler.py`.

Why a fixed set of intervals: PSD2 limits account access without the customer
being present, banks commonly allow about four such fetches per day, and many
banks rate-limit FinTS dialogs. 6, 12 and 24 hours stay well below that.

PIN storage is opt-in per connection. The PIN is encrypted with the key derived
from BUDGIE_SECRET_KEY (see crypto.py). All access goes through `get_pin`,
`store_pin` and `clear_pin`, so the storage can be swapped out later.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from fints.exceptions import FinTSClientPINError, FinTSClientTemporaryAuthError, FinTSSCARequiredError

from .. import crypto
from ..models import BankConnection

ALLOWED_INTERVALS = (6, 12, 24)
DEFAULT_INTERVAL_HOURS = 12
# Backoff after transient errors never exceeds this
MAX_BACKOFF_HOURS = 48
# Random delay added to every schedule, as a fraction of the interval
JITTER_FRACTION = 0.1

# Machine codes in BankConnection.auto_sync_paused_reason
PAUSE_TAN_REQUIRED = "tan_required"
PAUSE_PIN_REJECTED = "pin_rejected"
PAUSE_LOCKED = "locked"
PAUSE_MANUAL_SYNC_REQUIRED = "manual_sync_required"


class AttentionRequired(Exception):
    """An unattended sync needs the user (TAN, approval, choice). It must not wait for them."""

    def __init__(self, reason: str, message: str = ""):
        super().__init__(message or reason)
        self.reason = reason


# --- PIN storage ------------------------------------------------------------------


def get_pin(connection: BankConnection) -> str | None:
    """The stored PIN of a connection, or None if the user did not opt in."""
    return crypto.decrypt(connection.pin_enc).decode() if connection.pin_enc else None


def store_pin(connection: BankConnection, pin: str) -> None:
    connection.pin_enc = crypto.encrypt(pin)


def clear_pin(connection: BankConnection) -> None:
    connection.pin_enc = None


# --- Schedule --------------------------------------------------------------------


def next_run(interval_hours: int, failures: int = 0, now: datetime | None = None) -> datetime:
    """Next fetch time: the interval, doubled per consecutive failure (max 48 h), plus jitter."""
    now = now or datetime.now(UTC)
    hours = min(interval_hours * 2**failures, MAX_BACKOFF_HOURS)
    jitter = random.uniform(0, JITTER_FRACTION * interval_hours)  # noqa: S311  (not security relevant)
    return now + timedelta(hours=hours + jitter)


def has_client_state(connection: BankConnection) -> bool:
    """Unattended fetches need a first manual sync that stored a TAN mechanism."""
    return connection.client_state_enc is not None and connection.tan_mechanism is not None


def enable(connection: BankConnection, interval_hours: int, now: datetime | None = None) -> None:
    """Turns automatic fetching on (the PIN must already be stored) and schedules the first run."""
    connection.auto_sync_enabled = True
    connection.auto_sync_interval_hours = interval_hours
    connection.auto_sync_failures = 0
    connection.auto_sync_paused_reason = None if has_client_state(connection) else PAUSE_MANUAL_SYNC_REQUIRED
    connection.next_auto_sync_at = next_run(interval_hours, now=now)


def disable(connection: BankConnection) -> None:
    """Turns automatic fetching off and deletes the stored PIN."""
    clear_pin(connection)
    connection.auto_sync_enabled = False
    connection.auto_sync_failures = 0
    connection.auto_sync_paused_reason = None
    connection.next_auto_sync_at = None


def apply_success(connection: BankConnection, now: datetime | None = None) -> None:
    """After any successful sync (manual or unattended): clears pause and failures, reschedules."""
    connection.auto_sync_paused_reason = None
    connection.auto_sync_failures = 0
    connection.next_auto_sync_at = (
        next_run(connection.auto_sync_interval_hours, now=now) if connection.auto_sync_enabled else None
    )


def pause(connection: BankConnection, reason: str) -> None:
    connection.auto_sync_paused_reason = reason
    connection.next_auto_sync_at = None


def apply_failure(connection: BankConnection, exc: Exception, now: datetime | None = None) -> None:
    """Records a failed unattended sync: pause if the user has to act, otherwise back off."""
    if isinstance(exc, AttentionRequired):
        pause(connection, exc.reason)
    elif isinstance(exc, FinTSClientPINError):
        # Retrying a wrong PIN would lock the bank account
        clear_pin(connection)
        pause(connection, PAUSE_PIN_REJECTED)
    elif isinstance(exc, FinTSClientTemporaryAuthError):
        pause(connection, PAUSE_LOCKED)
    elif isinstance(exc, FinTSSCARequiredError):
        pause(connection, PAUSE_TAN_REQUIRED)
    else:
        connection.auto_sync_failures += 1
        connection.next_auto_sync_at = next_run(
            connection.auto_sync_interval_hours, connection.auto_sync_failures, now=now
        )

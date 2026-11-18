"""Sync jobs with TAN approval.

A sync runs in its own thread because the bank may wait for an approval in
between: with ING you confirm access in the banking app ("decoupled"), with
other mechanisms you type in a TAN. The UI polls the job state and submits the
TAN when needed.

The FinTS dialog and the PIN only live in this thread's memory and are gone
after the sync. Jobs are therefore kept in the memory of the API process; the
API runs as exactly one uvicorn process (see Dockerfile).
"""

from __future__ import annotations

import base64
import logging
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from fints.client import FinTS3PinTanClient, NeedTANResponse
from fints.exceptions import (
    FinTSClientPINError,
    FinTSClientTemporaryAuthError,
    FinTSConnectionError,
    FinTSError,
    FinTSSCARequiredError,
)
from sqlalchemy import func, select

from .. import crypto
from ..i18n import date_text, get_locale, t, use_locale
from ..config import get_settings
from ..db import SessionLocal
from ..importers.ing_csv import normalize_iban
from ..importers.store import store_transactions
from ..models import Account, BankConnection, ImportBatch, Transaction, User
from .convert import to_parsed

log = logging.getLogger(__name__)

# First sync of an account: this many days back. Without renewed strong
# customer authentication, banks often only return 90 days under PSD2.
FIRST_SYNC_DAYS = 90
# Later syncs overlap with the previous one so late bookings are not missed
OVERLAP_DAYS = 14
# Polling interval while waiting for app approval (seconds)
DECOUPLED_POLL_SECONDS = 3
# Finished jobs are forgotten after this time (seconds)
JOB_TTL_SECONDS = 30 * 60

# Replaceable in tests
client_factory: Callable[..., FinTS3PinTanClient] = FinTS3PinTanClient


class JobCancelled(Exception):
    pass


class JobFailed(Exception):
    pass


@dataclass
class SyncJob:
    id: str
    user_id: int
    connection_id: int
    # running → (need_tan → running)* → done | error | cancelled
    # Language of the user who started the sync; messages are written in it
    locale: str = "de"
    state: str = "running"
    message: str = ""
    challenge: str | None = None
    challenge_image: str | None = None
    decoupled: bool = False
    results: list[dict] = field(default_factory=list)
    error: str | None = None
    updated: float = field(default_factory=time.monotonic)
    _tan: str | None = field(default=None, repr=False)
    _tan_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def finished(self) -> bool:
        return self.state in ("done", "error", "cancelled")

    def set(self, **changes) -> None:
        with _lock:
            for k, v in changes.items():
                setattr(self, k, v)
            self.updated = time.monotonic()

    def submit_tan(self, tan: str) -> None:
        self._tan = tan
        self._tan_event.set()

    def cancel(self) -> None:
        self._cancel.set()
        self._tan_event.set()


_jobs: dict[str, SyncJob] = {}
_lock = threading.Lock()


def get_job(job_id: str, user_id: int) -> SyncJob | None:
    with _lock:
        job = _jobs.get(job_id)
    return job if job is not None and job.user_id == user_id else None


def _cleanup() -> None:
    now = time.monotonic()
    with _lock:
        for job_id in [j.id for j in _jobs.values() if j.finished and now - j.updated > JOB_TTL_SECONDS]:
            del _jobs[job_id]


def start_sync(connection: BankConnection, user: User, pin: str, start_date: date | None) -> SyncJob:
    _cleanup()
    with _lock:
        for other in _jobs.values():
            if other.connection_id == connection.id and not other.finished:
                raise JobFailed(t("fints.already_running"))
        job = SyncJob(
            id=secrets.token_urlsafe(16),
            user_id=user.id,
            connection_id=connection.id,
            locale=get_locale(),
            message=t("fints.connecting"),
        )
        _jobs[job.id] = job
    thread = threading.Thread(target=_run, args=(job, pin, start_date), name=f"fints-{job.id[:6]}", daemon=True)
    thread.start()
    return job


# --- Flow -----------------------------------------------------------------


def _run(job: SyncJob, pin: str, start_date: date | None) -> None:
    with use_locale(job.locale), SessionLocal() as db:
        connection = db.get(BankConnection, job.connection_id)
        try:
            if connection is None:
                raise JobFailed(t("fints.connection_not_found"))
            _sync(db, job, connection, pin, start_date)
            connection.last_sync_at = datetime.now(UTC)
            connection.last_error = None
            db.commit()
            job.set(state="done", message=t("fints.done"), challenge=None, challenge_image=None)
        except JobCancelled:
            db.rollback()
            job.set(state="cancelled", message=t("fints.cancelled"), challenge=None, challenge_image=None)
        except Exception as exc:  # noqa: BLE001  every error should reach the UI
            db.rollback()
            text = _error_text(exc)
            if not isinstance(exc, (JobFailed, FinTSError)):
                log.exception("FinTS-Abruf fehlgeschlagen")
            if connection is not None:
                connection.last_error = text
                db.commit()
            job.set(state="error", error=text, message=t("fints.failed"), challenge=None, challenge_image=None)


def _error_text(exc: Exception) -> str:
    if isinstance(exc, FinTSClientPINError):
        return t("fints.pin_rejected")
    if isinstance(exc, FinTSClientTemporaryAuthError):
        return t("fints.temporarily_locked")
    if isinstance(exc, FinTSSCARequiredError):
        return t("fints.sca_required")
    if isinstance(exc, FinTSConnectionError):
        return t("fints.connection_error", error=exc)
    if isinstance(exc, (JobFailed, crypto.SecretKeyMissing, ValueError)):
        return str(exc)
    return t("fints.error", error=exc)


def _sync(db, job: SyncJob, connection: BankConnection, pin: str, start_date: date | None) -> None:
    settings = get_settings()
    if not settings.fints_product_id:
        raise JobFailed(t("fints.product_id_missing"))
    user = db.get(User, job.user_id)

    state = crypto.decrypt(connection.client_state_enc) if connection.client_state_enc else None
    customer_id = crypto.decrypt(connection.customer_id_enc).decode() if connection.customer_id_enc else None
    client = client_factory(
        connection.bank_code,
        crypto.decrypt(connection.login_enc).decode(),
        pin,
        connection.server_url,
        customer_id=customer_id,
        product_id=settings.fints_product_id,
        from_data=state,
    )

    _choose_tan_mechanism(client, connection)
    _check_cancel(job)

    with client:
        if isinstance(client.init_tan_response, NeedTANResponse):
            _resolve(job, client, client.init_tan_response)
        job.set(state="running", message=t("fints.fetching_accounts"))
        sepa_accounts = _resolve(job, client, client.get_sepa_accounts())
        if not sepa_accounts:
            raise JobFailed(t("fints.no_accounts"))

        for sepa in sepa_accounts:
            _check_cancel(job)
            iban = normalize_iban(sepa.iban or "")
            if not iban:
                continue
            account, created = _find_or_create_account(db, user, connection, iban)
            if account is None:
                job.results.append({"iban": iban, "skipped": t("fints.foreign_account")})
                continue
            since = start_date or _default_start(db, account)
            job.set(message=t("fints.fetching_transactions", account=account.name))
            raw = _resolve(job, client, client.get_transactions(sepa, since, date.today()))
            parsed = to_parsed(raw or [])
            batch = store_transactions(
                db,
                household_id=user.household_id,
                user_id=user.id,
                account=account,
                parsed=parsed,
                source="fints",
                filename=t("fints.import_name", date=date_text(since)),
            )
            _update_balance(job, client, sepa, account)
            db.flush()
            job.results.append(
                {
                    "import_id": batch.id,
                    "account_id": account.id,
                    "account_name": account.name,
                    "iban": iban,
                    "account_created": created,
                    "since": since.isoformat(),
                    "rows_total": batch.rows_total,
                    "rows_imported": batch.rows_imported,
                    "rows_duplicate": batch.rows_duplicate,
                    "rows_categorized": batch.rows_categorized,
                }
            )

    # Remember system ID, bank parameters and TAN mechanism for the next sync (without the PIN)
    connection.client_state_enc = crypto.encrypt(client.deconstruct(including_private=True))


def _choose_tan_mechanism(client, connection: BankConnection) -> None:
    """Selects the TAN mechanism on the first sync, preferring app approval."""
    if client.get_current_tan_mechanism():
        return
    client.fetch_tan_mechanisms()
    mechanisms = client.get_tan_mechanisms()
    if len(mechanisms) > 1:
        chosen = None
        if connection.tan_mechanism in mechanisms:
            chosen = connection.tan_mechanism
        else:
            for function, params in mechanisms.items():
                if getattr(params, "decoupled_max_poll_number", None) is not None:
                    chosen = function
                    break
            chosen = chosen or next(iter(mechanisms))
        client.set_tan_mechanism(chosen)
    current = client.get_current_tan_mechanism()
    if current in mechanisms:
        connection.tan_mechanism = current
        connection.tan_mechanism_name = getattr(mechanisms[current], "name", None) or current

    if client.selected_tan_medium is None and client.is_tan_media_required():
        _usage, media = client.get_tan_media()
        if media:
            client.set_tan_medium(media[0])
        else:
            client.selected_tan_medium = ""


def _resolve(job: SyncJob, client, response):
    """Waits until the bank answers a request without asking for another TAN."""
    deadline = time.monotonic() + get_settings().fints_tan_timeout
    poll_seconds = DECOUPLED_POLL_SECONDS
    while isinstance(response, NeedTANResponse):
        image = None
        if response.challenge_matrix:
            mime, data = response.challenge_matrix
            image = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        job.set(
            state="need_tan",
            decoupled=bool(response.decoupled),
            challenge=response.challenge or None,
            challenge_image=image,
            message=t("fints.approve_in_app") if response.decoupled else t("fints.enter_tan"),
        )
        if response.decoupled:
            while True:
                _wait(job, poll_seconds, deadline)
                result = client.send_tan(response, "")
                if not (isinstance(result, NeedTANResponse) and result.decoupled):
                    break
            response = result
        else:
            job._tan_event.clear()
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not job._tan_event.wait(remaining):
                raise JobFailed(t("fints.no_tan"))
            _check_cancel(job)
            tan, job._tan = job._tan or "", None
            job.set(state="running", message=t("fints.checking_tan"), challenge=None, challenge_image=None)
            response = client.send_tan(response, tan)
    if job.state == "need_tan":
        job.set(state="running", message=t("fints.approved"), challenge=None, challenge_image=None)
    return response


def _wait(job: SyncJob, seconds: float, deadline: float) -> None:
    if time.monotonic() + seconds > deadline:
        raise JobFailed(t("fints.no_approval"))
    if job._cancel.wait(seconds):
        raise JobCancelled()


def _check_cancel(job: SyncJob) -> None:
    if job._cancel.is_set():
        raise JobCancelled()


def _find_or_create_account(db, user: User, connection: BankConnection, iban: str) -> tuple[Account | None, bool]:
    from ..deps import visible_accounts_query

    account = db.scalar(select(Account).where(Account.household_id == user.household_id, Account.iban == iban))
    if account is not None:
        if db.scalar(visible_accounts_query(user).where(Account.id == account.id)) is None:
            return None, False
        if account.bank_connection_id is None:
            account.bank_connection_id = connection.id
        return account, False
    account = Account(
        household_id=user.household_id,
        name=f"{connection.name} {iban[-4:]}",
        iban=iban,
        bank=connection.name,
        bank_connection_id=connection.id,
        members=[user],
    )
    db.add(account)
    db.flush()
    return account, True


def _default_start(db, account: Account) -> date:
    last = db.scalar(
        select(func.max(Transaction.booking_date))
        .join(ImportBatch, ImportBatch.id == Transaction.import_id)
        .where(Transaction.account_id == account.id, ImportBatch.source == "fints")
    )
    if last is None:
        return date.today() - timedelta(days=FIRST_SYNC_DAYS)
    return last - timedelta(days=OVERLAP_DAYS)


def _update_balance(job: SyncJob, client, sepa, account: Account) -> None:
    """Balance reported by the bank. If fetching it fails, the old balance is kept."""
    try:
        balance = _resolve(job, client, client.get_balance(sepa))
    except (JobCancelled, JobFailed):
        raise
    except Exception:  # noqa: BLE001
        log.warning("Kontostand für %s nicht abrufbar", account.iban, exc_info=True)
        return
    if balance is None or getattr(balance, "amount", None) is None:
        return
    amount = getattr(balance.amount, "amount", balance.amount)
    account.bank_balance = amount
    account.bank_balance_date = getattr(balance, "date", None) or date.today()

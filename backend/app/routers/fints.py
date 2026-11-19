from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from .. import crypto
from ..config import get_settings
from ..deps import DB, CurrentUser
from ..fints import directory, jobs
from ..models import Account, BankConnection
from ..schemas import (
    BankConnectionIn,
    BankConnectionOut,
    BankConnectionPatch,
    BankOut,
    ChoiceIn,
    FintsStatus,
    SyncIn,
    SyncJobOut,
    TanIn,
)

router = APIRouter(prefix="/fints", tags=["fints"])


def _missing() -> list[str]:
    settings = get_settings()
    missing = []
    if not settings.fints_product_id:
        missing.append("BUDGIE_FINTS_PRODUCT_ID")
    if len(settings.secret_key) < 16:
        missing.append("BUDGIE_SECRET_KEY")
    return missing


def _require_enabled() -> None:
    missing = _missing()
    if missing:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "FinTS ist nicht eingerichtet, es fehlt: " + ", ".join(missing)
        )


def _hint(login: str) -> str:
    return login.strip()[-4:]


def _own_connection(db: DB, user: CurrentUser, connection_id: int) -> BankConnection:
    connection = db.get(BankConnection, connection_id)
    # Credentials belong to one person, even within the household
    if connection is None or connection.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bankverbindung nicht gefunden")
    return connection


def _job_out(job: jobs.SyncJob) -> SyncJobOut:
    return SyncJobOut(
        id=job.id,
        connection_id=job.connection_id,
        state=job.state,
        message=job.message,
        decoupled=job.decoupled,
        challenge=job.challenge,
        challenge_image=job.challenge_image,
        challenge_hhduc=job.challenge_hhduc,
        choice_kind=job.choice_kind,
        options=list(job.options),
        error=job.error,
        results=list(job.results),
    )


@router.get("/status", response_model=FintsStatus)
def fints_status(user: CurrentUser):
    missing = _missing()
    return FintsStatus(enabled=not missing, missing=missing)


@router.get("/banks", response_model=list[BankOut])
def search_banks(user: CurrentUser, q: Annotated[str, Query(max_length=100)] = ""):
    """Searches the bank directory by bank code (BLZ), BIC, name or location."""
    return [b.to_dict() for b in directory.search(q)]


@router.get("/banks/{bank_code}", response_model=BankOut)
def get_bank(bank_code: str, user: CurrentUser):
    bank = directory.lookup(bank_code)
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bankleitzahl nicht im Verzeichnis")
    return bank.to_dict()


def _server_url(bank_code: str, server_url: str | None) -> str:
    if server_url:
        return server_url.strip()
    if bank_code == directory.ING_BANK_CODE:
        return directory.ING_FINTS_URL
    bank = directory.lookup(bank_code)
    if bank is None or not bank.server_url:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Für diese Bankleitzahl ist keine FinTS-Adresse bekannt. Bitte die Adresse angeben "
            "(steht meist in der Hilfe der Bank unter „FinTS“ oder „HBCI PIN/TAN“).",
        )
    return bank.server_url


@router.get("/connections", response_model=list[BankConnectionOut])
def list_connections(db: DB, user: CurrentUser):
    return db.scalars(select(BankConnection).where(BankConnection.user_id == user.id).order_by(BankConnection.id)).all()


@router.post("/connections", response_model=BankConnectionOut, status_code=201)
def create_connection(data: BankConnectionIn, db: DB, user: CurrentUser):
    _require_enabled()
    connection = BankConnection(
        household_id=user.household_id,
        user_id=user.id,
        name=data.name,
        bank_code=data.bank_code,
        server_url=_server_url(data.bank_code, data.server_url),
        login_enc=crypto.encrypt(data.login.strip()),
        customer_id_enc=crypto.encrypt(data.customer_id.strip()) if data.customer_id else None,
        login_hint=_hint(data.login),
    )
    db.add(connection)
    db.commit()
    return connection


@router.patch("/connections/{connection_id}", response_model=BankConnectionOut)
def update_connection(connection_id: int, data: BankConnectionPatch, db: DB, user: CurrentUser):
    connection = _own_connection(db, user, connection_id)
    if data.name is not None:
        connection.name = data.name
    if data.login is not None:
        _require_enabled()
        connection.login_enc = crypto.encrypt(data.login.strip())
        connection.login_hint = _hint(data.login)
        # Different login: cached bank data no longer applies
        connection.client_state_enc = None
        connection.tan_mechanism = None
        connection.tan_mechanism_name = None
    if data.customer_id is not None:
        _require_enabled()
        customer_id = data.customer_id.strip()
        connection.customer_id_enc = crypto.encrypt(customer_id) if customer_id else None
        connection.client_state_enc = None
        connection.tan_mechanism = None
        connection.tan_mechanism_name = None
    if data.server_url is not None:
        connection.server_url = data.server_url.strip()
    if data.reset_tan_mechanism:
        connection.tan_mechanism = None
        connection.tan_mechanism_name = None
    db.commit()
    return connection


@router.delete("/connections/{connection_id}", status_code=204)
def delete_connection(connection_id: int, db: DB, user: CurrentUser):
    """Deletes only the connection. Accounts and transactions are kept."""
    connection = _own_connection(db, user, connection_id)
    for account in db.scalars(select(Account).where(Account.bank_connection_id == connection.id)):
        account.bank_connection_id = None
    db.delete(connection)
    db.commit()


@router.post("/connections/{connection_id}/sync", response_model=SyncJobOut, status_code=202)
def start_sync(connection_id: int, data: SyncIn, db: DB, user: CurrentUser):
    """Starts a sync. Progress is available at GET /fints/jobs/{id}."""
    _require_enabled()
    connection = _own_connection(db, user, connection_id)
    try:
        job = jobs.start_sync(connection, user, data.pin, data.start_date)
    except jobs.JobFailed as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return _job_out(job)


def _job(job_id: str, user: CurrentUser) -> jobs.SyncJob:
    job = jobs.get_job(job_id, user.id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Abruf nicht gefunden")
    return job


@router.get("/jobs/{job_id}", response_model=SyncJobOut)
def get_job(job_id: str, user: CurrentUser):
    return _job_out(_job(job_id, user))


@router.post("/jobs/{job_id}/tan", response_model=SyncJobOut)
def send_tan(job_id: str, data: TanIn, user: CurrentUser):
    job = _job(job_id, user)
    if job.state != "need_tan" or job.decoupled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Der Abruf wartet gerade auf keine TAN")
    job.submit_tan(data.tan.strip())
    return _job_out(job)


@router.post("/jobs/{job_id}/choice", response_model=SyncJobOut)
def send_choice(job_id: str, data: ChoiceIn, user: CurrentUser):
    job = _job(job_id, user)
    if job.state != "need_choice":
        raise HTTPException(status.HTTP_409_CONFLICT, "Der Abruf wartet gerade auf keine Auswahl")
    if data.option not in {o["id"] for o in job.options}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ungültige Auswahl")
    job.submit_choice(data.option)
    return _job_out(job)


@router.post("/jobs/{job_id}/cancel", response_model=SyncJobOut)
def cancel_job(job_id: str, user: CurrentUser):
    job = _job(job_id, user)
    if not job.finished:
        job.cancel()
    return _job_out(job)

"""FinTS sync against a fake bank client (no real bank connection)."""

import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from fints.client import NeedTANResponse
from fints.exceptions import FinTSClientPINError
from fints.models import SEPAAccount
from fints.utils import mt940_to_array
from mt940.models import Amount, Balance
from sqlalchemy import select

from app import crypto
from app.config import get_settings
from app.db import SessionLocal
from app.fints import jobs
from app.fints.convert import to_parsed
from app.models import BankConnection

from .conftest import DATA, find_category

IBAN = "DE89370400440532013000"


@dataclass
class Mechanism:
    name: str
    decoupled_max_poll_number: int | None = None


def need_tan(decoupled: bool, challenge: str) -> NeedTANResponse:
    resp = object.__new__(NeedTANResponse)
    resp.decoupled = decoupled
    resp.challenge = challenge
    resp.challenge_matrix = None if decoupled else ("image/png", b"\x89PNG")
    return resp


class FakeBank:
    """Behaves like FinTS3PinTanClient with ING: fetching transactions with app approval."""

    decoupled = True
    polls_until_approved = 2
    wrong_pin = False
    instances: list["FakeBank"] = []

    def __init__(self, bank_code, login, pin, server, customer_id=None, product_id=None, from_data=None):
        self.bank_code, self.login, self.pin, self.server = bank_code, login, pin, server
        self.product_id, self.from_data = product_id, from_data
        self.mechanism = "902" if from_data else None
        self.selected_tan_medium = None
        self.init_tan_response = None
        self.polls = 0
        self.ranges: list[tuple[date, date]] = []
        FakeBank.instances.append(self)

    # TAN mechanisms
    def get_current_tan_mechanism(self):
        return self.mechanism

    def fetch_tan_mechanisms(self):
        self.mechanism = "900"

    def get_tan_mechanisms(self):
        return {"900": Mechanism("photoTAN"), "902": Mechanism("ING App", decoupled_max_poll_number=60)}

    def set_tan_mechanism(self, function):
        self.mechanism = function

    def is_tan_media_required(self):
        return False

    # Dialog
    def __enter__(self):
        if self.wrong_pin or self.pin != "12345":
            raise FinTSClientPINError("PIN falsch")

    def __exit__(self, *exc):
        return False

    def get_sepa_accounts(self):
        return [SEPAAccount(iban=IBAN, bic="INGDDEFFXXX", accountnumber="0532013000", subaccount=None, blz="50010517")]

    def get_transactions(self, account, start_date, end_date):
        self.ranges.append((start_date, end_date))
        return need_tan(self.decoupled, "Bitte bestätigen Sie den Umsatzabruf in der App")

    def send_tan(self, challenge, tan):
        if challenge.decoupled:
            self.polls += 1
            if self.polls < self.polls_until_approved:
                return challenge
        elif tan != "123456":
            return challenge
        return mt940_to_array((DATA / "ing_beispiel.mt940").read_text())

    def get_balance(self, account):
        return Balance(status="C", amount=Amount("2285.67", "C", "EUR"), date=date(2026, 11, 16))

    def deconstruct(self, including_private=False):
        return b"gespeicherter-zustand"


@pytest.fixture(autouse=True)
def fake_bank(monkeypatch):
    monkeypatch.setattr(jobs, "client_factory", FakeBank)
    monkeypatch.setattr(jobs, "DECOUPLED_POLL_SECONDS", 0.01)
    FakeBank.instances = []
    FakeBank.decoupled = True
    FakeBank.wrong_pin = False
    return FakeBank


def wait(client, job_id, until=("done", "error", "cancelled"), timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/fints/jobs/{job_id}").json()
        if job["state"] in until:
            return job
        time.sleep(0.02)
    raise AssertionError(f"Auftrag hängt: {job}")


def connect(client, **extra):
    r = client.post("/api/fints/connections", json={"login": "5402012345", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_convert_mt940():
    parsed = to_parsed(mt940_to_array((DATA / "ing_beispiel.mt940").read_text()))
    assert [p.booking_date for p in parsed] == [date(2026, 11, 3)] + [date(2026, 11, 14)] * 3 + [date(2026, 11, 16)]
    strom = parsed[0]
    assert strom.amount == Decimal("-89.00")
    assert strom.payee == "Stadtwerke Musterstadt"
    assert strom.purpose == "Abschlag Strom 11/2026"
    assert strom.booking_text == "Lastschrift"
    # Two identical bakery transactions get different fingerprints
    assert parsed[1].dedup_hash != parsed[2].dedup_hash


def test_status_and_missing_config(admin, monkeypatch):
    assert admin.get("/api/fints/status").json() == {"enabled": True, "missing": []}
    monkeypatch.setattr(get_settings(), "fints_product_id", "")
    assert admin.get("/api/fints/status").json()["missing"] == ["BUDGIE_FINTS_PRODUCT_ID"]
    assert admin.post("/api/fints/connections", json={"login": "x"}).status_code == 503


def test_login_is_stored_encrypted(admin):
    conn = connect(admin)
    assert conn["login_hint"] == "2345"
    assert conn["bank_code"] == "50010517" and conn["server_url"] == "https://fints.ing.de/fints/"
    with SessionLocal() as db:
        stored = db.scalar(select(BankConnection))
        assert "5402012345" not in stored.login_enc
        assert crypto.decrypt(stored.login_enc) == b"5402012345"


def test_sync_with_app_approval(admin):
    conn = connect(admin)
    job = admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()
    job = wait(admin, job["id"])
    assert job["state"] == "done", job
    [result] = job["results"]
    assert result["account_created"] is True and result["iban"] == IBAN
    assert result["rows_imported"] == 5 and result["rows_duplicate"] == 0

    bank = FakeBank.instances[0]
    assert bank.login == "5402012345" and bank.product_id == "TESTPRODUKT"
    assert bank.mechanism == "902"  # App approval was preferred
    assert bank.polls == 2

    accounts = admin.get("/api/accounts").json()
    assert accounts[0]["balance"] == "2285.67"
    assert accounts[0]["bank_connection_id"] == conn["id"]

    conn = admin.get("/api/fints/connections").json()[0]
    assert conn["tan_mechanism_name"] == "ING App"
    assert conn["last_sync_at"] and conn["last_error"] is None
    assert conn["accounts"][0]["iban"] == IBAN

    # Second sync: state is reused, no duplicates, period overlaps
    job = admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()
    job = wait(admin, job["id"])
    assert job["results"][0]["rows_imported"] == 0 and job["results"][0]["rows_duplicate"] == 5
    second = FakeBank.instances[1]
    assert second.from_data == b"gespeicherter-zustand"
    assert second.ranges[0][0] == date(2026, 11, 2)  # last transaction Nov 16 minus 14 days


def test_sync_with_tan_input(admin):
    FakeBank.decoupled = False
    conn = connect(admin)
    job = admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()
    job = wait(admin, job["id"], until=("need_tan", "error"))
    assert job["state"] == "need_tan" and job["decoupled"] is False
    assert job["challenge_image"].startswith("data:image/png;base64,")

    admin.post(f"/api/fints/jobs/{job['id']}/tan", json={"tan": "000000"})
    time.sleep(0.1)
    job = wait(admin, job["id"], until=("need_tan", "error"))
    assert job["state"] == "need_tan"  # wrong TAN: bank asks again

    admin.post(f"/api/fints/jobs/{job['id']}/tan", json={"tan": "123456"})
    job = wait(admin, job["id"])
    assert job["state"] == "done" and job["results"][0]["rows_imported"] == 5


def test_csv_then_fints_skips_cross_source_duplicates(admin, sample_csv):
    supermarkt = find_category(admin, "Lebensmittel", "Supermarkt")
    admin.post("/api/rules", json={"category_id": supermarkt, "pattern": "tankstelle"})
    r = admin.post("/api/imports/ing-csv", files={"file": ("u.csv", sample_csv, "text/csv")})
    assert r.json()["rows_imported"] == 7

    conn = connect(admin)
    job = admin.post(
        f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345", "start_date": "2026-11-01"}
    ).json()
    job = wait(admin, job["id"])
    [result] = job["results"]
    assert result["account_created"] is False
    # Electricity, 2x bakery and REWE are already known from the CSV; only the gas station is new
    assert result["rows_imported"] == 1 and result["rows_duplicate"] == 4
    assert result["rows_categorized"] == 1
    assert admin.get("/api/accounts").json()[0]["transaction_count"] == 8


def test_wrong_pin(admin):
    conn = connect(admin)
    job = admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "00000"}).json()
    job = wait(admin, job["id"])
    assert job["state"] == "error" and "PIN" in job["error"]
    assert admin.get("/api/fints/connections").json()[0]["last_error"] == job["error"]


def test_cancel_while_waiting_for_app(admin, monkeypatch):
    monkeypatch.setattr(FakeBank, "polls_until_approved", 10_000)
    conn = connect(admin)
    job = admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()
    job = wait(admin, job["id"], until=("need_tan",))
    assert job["decoupled"] is True
    assert admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).status_code == 409
    admin.post(f"/api/fints/jobs/{job['id']}/cancel")
    assert wait(admin, job["id"])["state"] == "cancelled"
    assert admin.get("/api/accounts").json() == []


def test_connections_are_private(admin, client):
    conn = connect(admin)
    admin.post(
        "/api/users", json={"username": "partnerin", "display_name": "Partnerin", "password": "geheim123"}
    )
    from fastapi.testclient import TestClient

    from app.main import app

    other = TestClient(app)
    assert other.post("/api/auth/login", json={"username": "partnerin", "password": "geheim123"}).status_code == 200
    assert other.get("/api/fints/connections").json() == []
    assert other.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "1"}).status_code == 404
    assert other.delete(f"/api/fints/connections/{conn['id']}").status_code == 404


def test_delete_connection_keeps_account(admin):
    conn = connect(admin)
    wait(admin, admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()["id"])
    assert admin.delete(f"/api/fints/connections/{conn['id']}").status_code == 204
    accounts = admin.get("/api/accounts").json()
    assert accounts[0]["bank_connection_id"] is None and accounts[0]["transaction_count"] == 5

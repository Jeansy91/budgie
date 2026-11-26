"""FinTS sync against a fake bank client (no real bank connection)."""

import dataclasses
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar

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
from app.fints.convert import split_iban_name, to_parsed
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
    instances: ClassVar[list["FakeBank"]] = []

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

    mechanisms: ClassVar[dict] = {
        "900": Mechanism("photoTAN"),
        "902": Mechanism("ING App", decoupled_max_poll_number=60),
    }
    media: ClassVar[list] = []

    def get_tan_mechanisms(self):
        return self.mechanisms

    def set_tan_mechanism(self, function):
        self.mechanism = function

    def is_tan_media_required(self):
        return bool(self.media)

    def get_tan_media(self):
        return None, self.media

    def set_tan_medium(self, medium):
        self.selected_tan_medium = medium.tan_medium_name

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
    FakeBank.mechanisms = {"900": Mechanism("photoTAN"), "902": Mechanism("ING App", decoupled_max_poll_number=60)}
    FakeBank.media = []
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
    # SEPA details; the IBAN delivered in front of the name is split off
    assert strom.counterparty_iban == "DE02120300000000202051"
    assert strom.counterparty_bic == "COBADEFFXXX"
    assert strom.end_to_end_ref == "ABS-2026-11-0042"
    assert strom.mandate_id == "SWM-778899"
    assert strom.creditor_id == "DE98ZZZ09999999999"
    assert parsed[1].counterparty_iban is None and parsed[1].end_to_end_ref is None
    # Two identical bakery transactions get different fingerprints
    assert parsed[1].dedup_hash != parsed[2].dedup_hash


def test_split_iban_name():
    assert split_iban_name("DE02120300000000202051Stadtwerke") == ("DE02120300000000202051", "Stadtwerke")
    assert split_iban_name("NL91ABNA0417164300 Shop B.V.") == ("NL91ABNA0417164300", "Shop B.V.")
    assert split_iban_name("DE Bahn") == (None, "DE Bahn")
    assert split_iban_name("REWE Markt GmbH") == (None, "REWE Markt GmbH")


def test_fingerprint_ignores_iban_split():
    """Transactions synced before the IBAN was split off are still duplicates."""
    from app.importers.ing_csv import fingerprint

    parsed = to_parsed(mt940_to_array((DATA / "ing_beispiel.mt940").read_text()))
    strom = parsed[0]
    glued = dataclasses.replace(strom, payee=strom.counterparty_iban + strom.payee)
    assert strom.dedup_hash == fingerprint(glued, 0)


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

    # Detail view: SEPA fields and the import source
    strom = admin.get("/api/transactions", params={"q": "Stadtwerke"}).json()["items"][0]
    detail = admin.get(f"/api/transactions/{strom['id']}").json()
    assert detail["payee"] == "Stadtwerke Musterstadt"
    assert detail["counterparty_iban"] == "DE02120300000000202051"
    assert detail["mandate_id"] == "SWM-778899"
    assert detail["import_batch"]["source"] == "fints"
    assert detail["account"]["iban"] == IBAN

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
    admin.post("/api/users", json={"username": "partnerin", "display_name": "Partnerin", "password": "geheim123"})
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


# --- Other banks --------------------------------------------------------------

SPARKASSE_MECHANISMS = {
    "910": Mechanism("chipTAN optisch"),
    "913": Mechanism("chipTAN QR"),
    "921": Mechanism("pushTAN 2.0", decoupled_max_poll_number=60),
    "922": Mechanism("App-Freigabe Zweitgerät", decoupled_max_poll_number=60),
}


@dataclass
class Medium:
    tan_medium_name: str


def test_bank_directory(admin):
    from app.fints import directory

    assert directory.lookup("50010517").server_url == "https://fints.ing.de/fints/"
    # Cooperative banks moved to Atruvia
    assert all("atruvia.de" in b.server_url for b in directory.search("volksbank") if b.server_url)
    hits = admin.get("/api/fints/banks", params={"q": "dkb"}).json()
    assert hits[0]["bank_code"] == "12030000" and hits[0]["server_url"].startswith("https://")
    assert admin.get("/api/fints/banks", params={"q": "5001"}).json()[0]["bank_code"].startswith("5001")
    assert admin.get("/api/fints/banks/12030000").json()["name"].startswith("Deutsche Kreditbank")
    assert admin.get("/api/fints/banks/99999999").status_code == 404


def test_official_institute_list(monkeypatch, tmp_path):
    from app.fints import directory

    csv = (
        "Nr.;BLZ;BIC;Institut;Ort;RZ;Organisation;HBCI-Zugang DNS;PIN/TAN-Zugang URL;Version\n"
        "1;12345678;TESTDEFFXXX;Testbank eG;Musterstadt;;BVR;;https://hbci-pintan.gad.de/cgi-bin/hbciservlet;FinTS V3.0\n"  # noqa: E501
    ).encode("cp1252")
    path = tmp_path / "fints_institute.csv"
    path.write_bytes(csv)
    monkeypatch.setattr(get_settings(), "fints_institutes_file", str(path))
    directory.reload()
    try:
        bank = directory.lookup("12345678")
        assert bank.name == "Testbank eG" and bank.server_url == "https://fints2.atruvia.de/cgi-bin/hbciservlet"
        assert directory.lookup("50010517") is None
    finally:
        monkeypatch.undo()
        directory.reload()


def test_connection_takes_server_from_directory(admin):
    conn = connect(admin, name="DKB", bank_code="12030000")
    assert conn["server_url"] == "https://banking-dkb.s-fints-pt-dkb.de/fints30"
    r = admin.post("/api/fints/connections", json={"login": "x", "bank_code": "99999999"})
    assert r.status_code == 400 and "FinTS-Adresse" in r.json()["detail"]
    conn = connect(admin, bank_code="99999999", server_url="https://fints.example.org/")
    assert conn["server_url"] == "https://fints.example.org/"
    r = admin.patch(f"/api/fints/connections/{conn['id']}", json={"server_url": "https://fints2.example.org/"})
    assert r.json()["server_url"] == "https://fints2.example.org/"


def test_user_picks_tan_mechanism_and_medium(admin):
    """Two app approvals and two devices (as with many Sparkassen): the user chooses."""
    FakeBank.mechanisms = SPARKASSE_MECHANISMS
    FakeBank.media = [Medium("iPhone"), Medium("Tablet")]
    conn = connect(admin, name="Sparkasse", bank_code="37050198")
    job = admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()

    job = wait(admin, job["id"], until=("need_choice", "error"))
    assert job["state"] == "need_choice" and job["choice_kind"] == "tan_mechanism"
    assert [o["id"] for o in job["options"]] == ["910", "913", "921", "922"]
    assert [o["decoupled"] for o in job["options"]] == [False, False, True, True]
    assert admin.post(f"/api/fints/jobs/{job['id']}/choice", json={"option": "999"}).status_code == 400
    admin.post(f"/api/fints/jobs/{job['id']}/choice", json={"option": "921"})

    time.sleep(0.05)
    job = wait(admin, job["id"], until=("need_choice", "error"))
    assert job["choice_kind"] == "tan_medium" and [o["name"] for o in job["options"]] == ["iPhone", "Tablet"]
    admin.post(f"/api/fints/jobs/{job['id']}/choice", json={"option": "Tablet"})

    job = wait(admin, job["id"])
    assert job["state"] == "done", job
    bank = FakeBank.instances[0]
    assert bank.mechanism == "921" and bank.selected_tan_medium == "Tablet"
    assert bank.server == "https://banking-rl7.s-fints-pt-rl.de/fints30"
    assert admin.get("/api/fints/connections").json()[0]["tan_mechanism_name"] == "pushTAN 2.0"


def test_single_app_approval_is_chosen_automatically(admin):
    FakeBank.mechanisms = {"910": Mechanism("chipTAN optisch"), "921": Mechanism("pushTAN 2.0", 60)}
    FakeBank.media = [Medium("iPhone")]
    conn = connect(admin, bank_code="37050198")
    job = wait(admin, admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()["id"])
    assert job["state"] == "done"
    assert FakeBank.instances[0].mechanism == "921" and FakeBank.instances[0].selected_tan_medium == "iPhone"


def test_reset_tan_mechanism_asks_again(admin):
    conn = connect(admin)
    wait(admin, admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()["id"])
    r = admin.patch(f"/api/fints/connections/{conn['id']}", json={"reset_tan_mechanism": True})
    assert r.json()["tan_mechanism_name"] is None

    FakeBank.decoupled = False
    job = admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()
    job = wait(admin, job["id"], until=("need_choice", "error"))
    assert job["choice_kind"] == "tan_mechanism"
    admin.post(f"/api/fints/jobs/{job['id']}/choice", json={"option": "900"})
    job = wait(admin, job["id"], until=("need_tan", "error"))
    admin.post(f"/api/fints/jobs/{job['id']}/tan", json={"tan": "123456"})
    assert wait(admin, job["id"])["state"] == "done"
    assert FakeBank.instances[1].mechanism == "900"
    assert admin.get("/api/fints/connections").json()[0]["tan_mechanism_name"] == "photoTAN"


def test_cancel_while_choosing(admin):
    FakeBank.mechanisms = SPARKASSE_MECHANISMS
    conn = connect(admin, bank_code="37050198")
    job = admin.post(f"/api/fints/connections/{conn['id']}/sync", json={"pin": "12345"}).json()
    job = wait(admin, job["id"], until=("need_choice",))
    admin.post(f"/api/fints/jobs/{job['id']}/cancel")
    job = wait(admin, job["id"])
    assert job["state"] == "cancelled" and job["options"] == []

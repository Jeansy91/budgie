from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..deps import DB, CurrentUser, get_visible_account, visible_accounts_query
from ..importers.common import normalize_iban
from ..models import Account, Transaction, User
from ..schemas import AccountIn, AccountOut, AccountPatch

router = APIRouter(prefix="/accounts", tags=["accounts"])


def account_out(db: DB, account: Account) -> AccountOut:
    last = db.execute(
        select(Transaction.balance_after, Transaction.booking_date)
        .where(Transaction.account_id == account.id, Transaction.balance_after.is_not(None))
        .order_by(Transaction.booking_date.desc(), Transaction.id.desc())
        .limit(1)
    ).first()
    last_balance = last[0] if last else None
    # The FinTS balance wins unless it is older than the one from the last CSV import
    if account.bank_balance is not None and (last is None or account.bank_balance_date >= last[1]):
        last_balance = account.bank_balance
    count = db.scalar(select(func.count(Transaction.id)).where(Transaction.account_id == account.id)) or 0
    out = AccountOut.model_validate(account)
    out.member_ids = [m.id for m in account.members]
    out.balance = last_balance
    out.transaction_count = count
    return out


def _members(db: DB, user: User, ids: list[int]) -> list[User]:
    members = db.scalars(select(User).where(User.household_id == user.household_id, User.id.in_(ids))).all()
    if len(members) != len(set(ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannter Nutzer")
    return list(members)


@router.get("", response_model=list[AccountOut])
def list_accounts(db: DB, user: CurrentUser):
    return [account_out(db, a) for a in db.scalars(visible_accounts_query(user).order_by(Account.id))]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(data: AccountIn, db: DB, user: CurrentUser):
    iban = normalize_iban(data.iban) if data.iban else None
    if iban and db.scalar(select(Account).where(Account.household_id == user.household_id, Account.iban == iban)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ein Konto mit dieser IBAN gibt es schon")
    account = Account(household_id=user.household_id, name=data.name, iban=iban, bank=data.bank, shared=data.shared)
    # Whoever creates a non-shared account can see it themselves
    account.members = _members(db, user, list({*data.member_ids, user.id}))
    db.add(account)
    db.commit()
    return account_out(db, account)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, data: AccountPatch, db: DB, user: CurrentUser):
    account = get_visible_account(db, user, account_id)
    if data.name is not None:
        account.name = data.name
    if data.shared is not None:
        account.shared = data.shared
    if data.member_ids is not None:
        account.members = _members(db, user, list({*data.member_ids, user.id}))
    db.commit()
    return account_out(db, account)


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, db: DB, user: CurrentUser):
    account = get_visible_account(db, user, account_id)
    db.delete(account)
    db.commit()

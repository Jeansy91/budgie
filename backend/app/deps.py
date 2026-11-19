from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .db import get_db
from .i18n import http_error
from .models import Account, User, UserSession, account_members
from .security import hash_token

SESSION_COOKIE = "budgie_session"

DB = Annotated[Session, Depends(get_db)]


def current_user(db: DB, budgie_session: Annotated[str | None, Cookie()] = None) -> User:
    if not budgie_session:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "auth.not_signed_in")
    session = db.get(UserSession, hash_token(budgie_session))
    if session is None or session.expires_at <= datetime.now(UTC):
        raise http_error(status.HTTP_401_UNAUTHORIZED, "auth.session_expired")
    return session.user


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise http_error(status.HTTP_403_FORBIDDEN, "auth.admin_only")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def visible_accounts_query(user: User):
    """Accounts the user may see: all shared ones plus those the user is a member of."""
    member_of = select(account_members.c.account_id).where(account_members.c.user_id == user.id)
    return select(Account).where(
        Account.household_id == user.household_id,
        or_(Account.shared.is_(True), Account.id.in_(member_of)),
    )


def visible_account_ids(user: User):
    return visible_accounts_query(user).with_only_columns(Account.id).scalar_subquery()


def get_visible_account(db: Session, user: User, account_id: int) -> Account:
    account = db.scalar(visible_accounts_query(user).where(Account.id == account_id))
    if account is None:
        raise http_error(status.HTTP_404_NOT_FOUND, "accounts.not_found")
    return account

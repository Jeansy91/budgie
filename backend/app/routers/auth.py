from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Response, status
from sqlalchemy import delete, func, select

from ..config import get_settings
from ..deps import DB, SESSION_COOKIE, CurrentUser
from ..i18n import http_error
from ..models import Household, User, UserSession
from ..schemas import LoginIn, MeOut, MePatch, PasswordIn, SetupIn, SetupStatus
from ..security import hash_password, hash_token, new_session_token, verify_password
from ..seed import seed_categories

router = APIRouter(prefix="/auth", tags=["auth"])

# Checked for unknown usernames so the response time stays the same
_DUMMY_HASH = hash_password("budgie-dummy-password")


def _start_session(db: DB, response: Response, user: User) -> None:
    settings = get_settings()
    token = new_session_token()
    expires = datetime.now(UTC) + timedelta(days=settings.session_days)
    db.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(UTC)))
    db.add(UserSession(token_hash=hash_token(token), user_id=user.id, expires_at=expires))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def _me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_admin=user.is_admin,
        household_name=user.household.name,
        language=user.language,
    )


@router.get("/setup", response_model=SetupStatus)
def setup_status(db: DB):
    return SetupStatus(needs_setup=db.scalar(select(func.count(User.id))) == 0)


@router.post("/setup", response_model=MeOut, status_code=201)
def setup(data: SetupIn, db: DB, response: Response):
    """Initial setup: creates the household, the first user (admin) and the default categories."""
    # The lock prevents two concurrent calls from creating two households
    db.execute(select(func.pg_advisory_xact_lock(4711)))
    if (db.scalar(select(func.count(User.id))) or 0) > 0:
        raise http_error(status.HTTP_409_CONFLICT, "auth.already_set_up")
    household = Household(name=data.household_name)
    db.add(household)
    db.flush()
    seed_categories(db, household.id)
    user = User(
        household_id=household.id,
        username=data.username.lower(),
        display_name=data.display_name,
        password_hash=hash_password(data.password),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    _start_session(db, response, user)
    return _me(user)


@router.post("/login", response_model=MeOut)
def login(data: LoginIn, db: DB, response: Response):
    user = db.scalar(select(User).where(User.username == data.username.strip().lower()))
    if user is None:
        verify_password(data.password, _DUMMY_HASH)
        raise http_error(status.HTTP_401_UNAUTHORIZED, "auth.invalid_login")
    if not verify_password(data.password, user.password_hash):
        raise http_error(status.HTTP_401_UNAUTHORIZED, "auth.invalid_login")
    _start_session(db, response, user)
    return _me(user)


@router.post("/logout", status_code=204)
def logout(db: DB, response: Response, user: CurrentUser):
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser):
    return _me(user)


@router.patch("/me", response_model=MeOut)
def update_me(data: MePatch, db: DB, user: CurrentUser):
    """Personal preferences. `language: null` follows the browser language."""
    user.language = data.language
    db.commit()
    return _me(user)


@router.post("/password", status_code=204)
def change_password(data: PasswordIn, db: DB, user: CurrentUser):
    if not verify_password(data.current_password, user.password_hash):
        raise http_error(status.HTTP_400_BAD_REQUEST, "auth.wrong_password")
    user.password_hash = hash_password(data.new_password)
    db.commit()

from fastapi import APIRouter, status
from sqlalchemy import select

from ..deps import DB, AdminUser, CurrentUser
from ..i18n import http_error
from ..models import User
from ..schemas import UserIn, UserOut
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DB, user: CurrentUser):
    return db.scalars(select(User).where(User.household_id == user.household_id).order_by(User.id)).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserIn, db: DB, admin: AdminUser):
    username = data.username.lower()
    if db.scalar(select(User).where(User.username == username)):
        raise http_error(status.HTTP_409_CONFLICT, "users.username_taken")
    user = User(
        household_id=admin.household_id,
        username=username,
        display_name=data.display_name,
        password_hash=hash_password(data.password),
        is_admin=data.is_admin,
    )
    db.add(user)
    db.commit()
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: DB, admin: AdminUser):
    user = db.get(User, user_id)
    if user is None or user.household_id != admin.household_id:
        raise http_error(status.HTTP_404_NOT_FOUND, "users.not_found")
    if user.id == admin.id:
        raise http_error(status.HTTP_400_BAD_REQUEST, "users.cannot_delete_self")
    db.delete(user)
    db.commit()

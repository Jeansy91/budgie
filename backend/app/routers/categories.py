from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..deps import DB, CurrentUser
from ..models import Category, Transaction, User
from ..schemas import CategoryIn, CategoryOut, CategoryPatch

router = APIRouter(prefix="/categories", tags=["categories"])


def get_category(db: DB, user: User, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None or category.household_id != user.household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kategorie nicht gefunden")
    return category


@router.get("", response_model=list[CategoryOut])
def list_categories(db: DB, user: CurrentUser):
    """Categories as a tree: main categories with their subcategories."""
    return db.scalars(
        select(Category)
        .where(Category.household_id == user.household_id, Category.parent_id.is_(None))
        .options(selectinload(Category.children))
        .order_by(Category.sort_order, Category.name)
    ).all()


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, db: DB, user: CurrentUser):
    kind = data.kind
    siblings = select(Category.sort_order).where(Category.household_id == user.household_id)
    if data.parent_id is not None:
        parent = get_category(db, user, data.parent_id)
        if parent.parent_id is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nur zwei Ebenen: Haupt- und Unterkategorie")
        kind = parent.kind  # Subcategories inherit the kind of their main category
        siblings = siblings.where(Category.parent_id == parent.id)
    else:
        siblings = siblings.where(Category.parent_id.is_(None))
    last = max(db.scalars(siblings).all(), default=-1)
    category = Category(
        household_id=user.household_id, parent_id=data.parent_id, name=data.name, kind=kind, sort_order=last + 1
    )
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese Kategorie gibt es schon") from None
    return category


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryPatch, db: DB, user: CurrentUser):
    category = get_category(db, user, category_id)
    if data.name is not None:
        category.name = data.name
    if data.sort_order is not None:
        category.sort_order = data.sort_order
    if data.kind is not None:
        if category.parent_id is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Die Art wird an der Hauptkategorie festgelegt")
        category.kind = data.kind
        for child in category.children:
            child.kind = data.kind
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese Kategorie gibt es schon") from None
    return category


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: DB, user: CurrentUser):
    """Deletes the category with its subcategories and rules. Its transactions become uncategorized."""
    category = get_category(db, user, category_id)
    ids = [category.id, *(c.id for c in category.children)]
    db.execute(
        update(Transaction)
        .where(Transaction.category_id.in_(ids))
        .values(category_id=None, category_source=None, rule_id=None)
    )
    db.delete(category)
    db.commit()

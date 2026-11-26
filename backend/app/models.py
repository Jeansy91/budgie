"""Budgie data model.

A household groups users, accounts, categories and rules. Several users
share one household; each account can be visible to all users or only to
selected members.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class CategoryKind(str, enum.Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"  # transfers count as neither income nor expense


class CategorySource(str, enum.Enum):
    """Where the category of a transaction came from."""

    manual = "manual"
    rule = "rule"
    model = "model"  # local classifier (scikit-learn)
    llm = "llm"  # local language model via Ollama


class BudgetShift(str, enum.Enum):
    """Manual override of a transaction's budget month (NULL = automatic)."""

    next = "next"  # counts towards the following month
    same = "same"  # counts towards the booking month


class RuleField(str, enum.Enum):
    payee = "payee"
    purpose = "purpose"
    any = "any"  # payee or purpose


class RuleMatch(str, enum.Enum):
    contains = "contains"
    equals = "equals"
    starts_with = "starts_with"
    regex = "regex"


def _enum(e: type[enum.Enum], name: str) -> Enum:
    return Enum(e, name=name, values_callable=lambda x: [m.value for m in x])


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # UI language ("de", "en"); NULL = follow the browser
    language: Mapped[str | None] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    household: Mapped[Household] = relationship()


class UserSession(Base):
    """A user login session. Only the hash of the token is stored."""

    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


account_members = Table(
    "account_members",
    Base.metadata,
    Column("account_id", ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("household_id", "iban"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    iban: Mapped[str | None] = mapped_column(String(34))
    bank: Mapped[str] = mapped_column(String(100), default="ING")
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    # True: every user of the household sees the account. False: only its members.
    shared: Mapped[bool] = mapped_column(Boolean, default=True)
    # FinTS: the bank connection used to sync this account, and the balance it reported
    bank_connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("bank_connections.id", ondelete="SET NULL"), index=True
    )
    bank_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    bank_balance_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list[User]] = relationship(secondary=account_members)


class BankConnection(Base):
    """A user's FinTS login, e.g. their online banking access.

    The login name and the state cached by python-fints (system ID, bank and
    user parameters, selected TAN mechanism) are stored encrypted in the
    database, see app/crypto.py. The PIN is never stored; it is entered for
    every sync.
    """

    __tablename__ = "bank_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    bank_code: Mapped[str] = mapped_column(String(8))
    server_url: Mapped[str] = mapped_column(String(255))
    login_enc: Mapped[str] = mapped_column(Text)
    customer_id_enc: Mapped[str | None] = mapped_column(Text)
    # Last four characters of the login name, to tell connections apart
    login_hint: Mapped[str] = mapped_column(String(8), default="")
    client_state_enc: Mapped[str | None] = mapped_column(Text)
    tan_mechanism: Mapped[str | None] = mapped_column(String(10))
    tan_mechanism_name: Mapped[str | None] = mapped_column(String(100))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    accounts: Mapped[list[Account]] = relationship(order_by="Account.id")


class Category(Base):
    """Main categories and subcategories. A main category has parent_id = NULL."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("household_id", "parent_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[CategoryKind] = mapped_column(_enum(CategoryKind, "category_kind"), default=CategoryKind.expense)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Key of a default category (see app/seed.py), e.g. "groceries.supermarket". Its name is
    # shown in the user's language. NULL for categories the user created or renamed.
    default_key: Mapped[str | None] = mapped_column(String(50))

    parent: Mapped[Category | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[Category]] = relationship(
        back_populates="parent", order_by="Category.sort_order", cascade="all, delete-orphan"
    )


class ImportBatch(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(20), default="ing_csv")
    filename: Mapped[str | None] = mapped_column(String(255))
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    rows_categorized: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CsvProfile(Base):
    """A saved column assignment for CSV exports of a bank without a built-in layout.

    Recognized by the header row of the file (`signature`), see app/importers/bank_csv.py.
    """

    __tablename__ = "csv_profiles"
    __table_args__ = (UniqueConstraint("household_id", "signature"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    signature: Mapped[str] = mapped_column(String(64))
    # delimiter, header_row, columns (field → index), date_format, decimal
    mapping: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Rule(Base):
    """A fixed assignment, e.g. payee contains "REWE" → Lebensmittel › Supermarkt."""

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    field: Mapped[RuleField] = mapped_column(_enum(RuleField, "rule_field"), default=RuleField.payee)
    match_type: Mapped[RuleMatch] = mapped_column(_enum(RuleMatch, "rule_match"), default=RuleMatch.contains)
    pattern: Mapped[str] = mapped_column(String(255))
    # Higher priority wins; on a tie, the older rule wins
    priority: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped[Category] = relationship()


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("account_id", "dedup_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    booking_date: Mapped[date] = mapped_column(Date, index=True)
    value_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    payee: Mapped[str] = mapped_column(String(255), default="")
    booking_text: Mapped[str] = mapped_column(String(100), default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    note: Mapped[str] = mapped_column(Text, default="")

    # SEPA details of the counterparty, as far as the source delivers them.
    # FinTS (MT940/camt) usually does; the ING CSV export does not.
    counterparty_iban: Mapped[str | None] = mapped_column(String(34))
    counterparty_bic: Mapped[str | None] = mapped_column(String(11))
    mandate_id: Mapped[str | None] = mapped_column(String(35))
    creditor_id: Mapped[str | None] = mapped_column(String(35))
    end_to_end_ref: Mapped[str | None] = mapped_column(String(35))

    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    category_source: Mapped[CategorySource | None] = mapped_column(_enum(CategorySource, "category_source"))
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("rules.id", ondelete="SET NULL"))
    # Classifier confidence (0–1) when the category was assigned by the AI
    category_confidence: Mapped[float | None] = mapped_column(Float)
    # AI suggestion when it was not confident enough to assign the category
    suggested_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    suggestion_confidence: Mapped[float | None] = mapped_column(Float)

    # Budget month: the date that decides where the transaction counts in the
    # overview and monthly totals. Usually equal to the booking date; a salary
    # paid at the end of a month is moved to the first of the following month
    # (see app/budget_month.py).
    budget_date: Mapped[date] = mapped_column(
        Date, index=True, default=lambda ctx: ctx.get_current_parameters()["booking_date"]
    )
    budget_shift: Mapped[BudgetShift | None] = mapped_column(_enum(BudgetShift, "budget_shift"))

    import_id: Mapped[int | None] = mapped_column(ForeignKey("imports.id", ondelete="SET NULL"))
    # Fingerprint of the transaction, used to detect duplicate imports
    dedup_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[Account] = relationship()
    category: Mapped[Category | None] = relationship(foreign_keys=[category_id])
    rule: Mapped[Rule | None] = relationship()
    import_batch: Mapped[ImportBatch | None] = relationship()


class ClassifierModel(Base):
    """A household's trained classifier (scikit-learn, serialized).

    Only the most recent model is kept.
    """

    __tablename__ = "classifier_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    samples: Mapped[int] = mapped_column(Integer, default=0)  # own examples (manual + rules)
    corrections: Mapped[int] = mapped_column(Integer, default=0)  # of which assigned manually
    classes: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float | None] = mapped_column(Float)  # cross-validated on manual assignments
    blob: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BudgetSettings(Base):
    """Household budget month settings (assign salary to the following month)."""

    __tablename__ = "budget_settings"

    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), primary_key=True)
    salary_shift_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Income received in the last n days of a month counts towards the following month
    salary_shift_days: Mapped[int] = mapped_column(Integer, default=7)
    # Categories treated as salary (main categories or subcategories)
    salary_category_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    # Payers whose payments count as salary (case-insensitive "contains")
    salary_payees: Mapped[list[str]] = mapped_column(ARRAY(String(255)), default=list)
    # Detect salary without a category: booking text "Gehalt/Rente" or a
    # recurring payment from the same payer at the end of the month
    salary_auto_detect: Mapped[bool] = mapped_column(Boolean, default=True)

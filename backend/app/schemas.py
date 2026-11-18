from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from typing import Literal

from .models import BudgetShift, CategoryKind, CategorySource, RuleField, RuleMatch


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Users ----------------------------------------------------------------

class SetupIn(BaseModel):
    household_name: str = Field("Unser Haushalt", min_length=1, max_length=100)
    username: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    is_admin: bool = False


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class UserOut(ORM):
    id: int
    username: str
    display_name: str
    is_admin: bool


class MeOut(UserOut):
    household_name: str


class SetupStatus(BaseModel):
    needs_setup: bool


# --- Accounts -------------------------------------------------------------

class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    iban: str | None = Field(None, max_length=42)
    bank: str = "ING"
    shared: bool = True
    member_ids: list[int] = []


class AccountPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    shared: bool | None = None
    member_ids: list[int] | None = None


class AccountOut(ORM):
    id: int
    name: str
    iban: str | None
    bank: str
    currency: str
    shared: bool
    member_ids: list[int] = []
    balance: Decimal | None = None
    transaction_count: int = 0
    bank_connection_id: int | None = None


# --- Categories -----------------------------------------------------------

class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None
    kind: CategoryKind = CategoryKind.expense


class CategoryPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    kind: CategoryKind | None = None
    sort_order: int | None = None


class CategoryOut(ORM):
    id: int
    name: str
    parent_id: int | None
    kind: CategoryKind
    sort_order: int
    children: list["CategoryOut"] = []


# --- Rules ----------------------------------------------------------------

class RuleIn(BaseModel):
    category_id: int
    field: RuleField = RuleField.payee
    match_type: RuleMatch = RuleMatch.contains
    pattern: str = Field(min_length=1, max_length=255)
    priority: int = 0
    active: bool = True


class RulePatch(BaseModel):
    category_id: int | None = None
    field: RuleField | None = None
    match_type: RuleMatch | None = None
    pattern: str | None = Field(None, min_length=1, max_length=255)
    priority: int | None = None
    active: bool | None = None


class RuleOut(ORM):
    id: int
    category_id: int
    field: RuleField
    match_type: RuleMatch
    pattern: str
    priority: int
    active: bool
    match_count: int = 0


class ApplyRulesIn(BaseModel):
    overwrite_rule_results: bool = False


class ApplyRulesOut(BaseModel):
    changed: int


# --- Transactions ---------------------------------------------------------

class TransactionOut(ORM):
    id: int
    account_id: int
    booking_date: date
    value_date: date | None
    amount: Decimal
    currency: str
    payee: str
    booking_text: str
    purpose: str
    note: str
    category_id: int | None
    category_source: CategorySource | None
    rule_id: int | None
    # Month the transaction counts towards (end-of-month salary → following month)
    budget_date: date
    budget_shift: BudgetShift | None
    category_confidence: float | None = None
    suggested_category_id: int | None = None
    suggestion_confidence: float | None = None


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int


class TransactionPatch(BaseModel):
    category_id: int | None = None
    note: str | None = None
    # Create a rule "payee contains …" straight from the correction
    create_rule: bool = False
    rule_pattern: str | None = None
    # Also apply the new rule to other transactions not assigned manually
    apply_rule: bool = True
    # Budget month: auto = automatic detection, next = following month, same = booking month
    budget_shift: Literal["auto", "next", "same"] | None = None


class TransactionPatchOut(BaseModel):
    transaction: TransactionOut
    rule: RuleOut | None = None
    other_changed: int = 0


# --- Import ---------------------------------------------------------------

class ImportOut(ORM):
    id: int
    account_id: int
    filename: str | None
    rows_total: int
    rows_imported: int
    rows_duplicate: int
    rows_categorized: int
    account_created: bool = False


# --- AI -------------------------------------------------------------------

class AiModelInfo(BaseModel):
    trained_at: datetime
    samples: int
    corrections: int
    classes: int
    accuracy: float | None


class LlmInfo(BaseModel):
    configured: bool
    reachable: bool
    model_available: bool
    model: str
    error: str | None
    running: bool = False
    done: int = 0
    total: int = 0
    failed: int = 0


class AiStatus(BaseModel):
    enabled: bool
    auto_threshold: float
    model: AiModelInfo | None
    llm: LlmInfo
    ai_categorized: int
    suggestions: int
    uncategorized: int


class RecategorizeIn(BaseModel):
    use_llm: bool = True


class RecategorizeOut(BaseModel):
    assigned: int
    suggested: int
    llm_queued: int


# --- Overview -------------------------------------------------------------

class CategorySum(BaseModel):
    category_id: int | None
    name: str
    amount: Decimal
    count: int
    children: list["CategorySum"] = []


class MonthTotal(BaseModel):
    month: str
    income: Decimal
    expenses: Decimal


class OverviewOut(BaseModel):
    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    transfers: Decimal
    # Of which income booked in the previous month (end-of-month salary)
    income_from_previous_month: Decimal = Decimal("0.00")
    uncategorized_count: int
    expense_categories: list[CategorySum]
    income_categories: list[CategorySum]
    history: list[MonthTotal]


# --- Budget month ---------------------------------------------------------

class BudgetSettingsIn(BaseModel):
    salary_shift_enabled: bool = True
    salary_shift_days: int = Field(7, ge=1, le=15)
    salary_category_ids: list[int] = []
    salary_payees: list[str] = Field([], max_length=50)
    salary_auto_detect: bool = True


class BudgetSettingsOut(BudgetSettingsIn, ORM):
    # How many transactions are currently assigned to a different month
    shifted_count: int = 0


# --- FinTS ----------------------------------------------------------------

ING_BANK_CODE = "50010517"
ING_FINTS_URL = "https://fints.ing.de/fints/"


class FintsStatus(BaseModel):
    enabled: bool
    missing: list[str]


class BankConnectionIn(BaseModel):
    name: str = Field("ING", min_length=1, max_length=100)
    login: str = Field(min_length=1, max_length=100)
    customer_id: str | None = Field(None, max_length=100)
    bank_code: str = Field(ING_BANK_CODE, pattern=r"^\d{8}$")
    server_url: str = Field(ING_FINTS_URL, pattern=r"^https://", max_length=255)


class BankConnectionPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    login: str | None = Field(None, min_length=1, max_length=100)


class LinkedAccount(ORM):
    id: int
    name: str
    iban: str | None


class BankConnectionOut(ORM):
    id: int
    name: str
    bank_code: str
    server_url: str
    login_hint: str
    tan_mechanism_name: str | None
    last_sync_at: datetime | None
    last_error: str | None
    accounts: list[LinkedAccount] = []


class SyncIn(BaseModel):
    pin: str = Field(min_length=1, max_length=100)
    start_date: date | None = None


class TanIn(BaseModel):
    tan: str = Field(min_length=1, max_length=100)


class SyncResult(BaseModel):
    iban: str
    account_id: int | None = None
    account_name: str | None = None
    account_created: bool = False
    since: date | None = None
    import_id: int | None = None
    rows_total: int = 0
    rows_imported: int = 0
    rows_duplicate: int = 0
    rows_categorized: int = 0
    skipped: str | None = None


class SyncJobOut(BaseModel):
    id: str
    connection_id: int
    state: str
    message: str
    decoupled: bool
    challenge: str | None
    challenge_image: str | None
    error: str | None
    results: list[SyncResult]

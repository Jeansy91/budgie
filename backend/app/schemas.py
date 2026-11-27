from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .i18n import category_name
from .models import BudgetShift, Category, CategoryKind, CategorySource, RuleField, RuleMatch


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
    # UI language; None = follow the browser
    language: Literal["de", "en"] | None = None


class MePatch(BaseModel):
    language: Literal["de", "en"] | None


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
    # Default categories in the request language, see app/seed.py
    name: str
    parent_id: int | None
    kind: CategoryKind
    sort_order: int
    children: list["CategoryOut"] = []

    @model_validator(mode="before")
    @classmethod
    def _localize(cls, data):
        if isinstance(data, Category):
            return {
                "id": data.id,
                "name": category_name(data),
                "parent_id": data.parent_id,
                "kind": data.kind,
                "sort_order": data.sort_order,
                "children": list(data.children) if data.parent_id is None else [],
            }
        return data


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


class TransactionAccount(ORM):
    id: int
    name: str
    iban: str | None
    bank: str


class TransactionImport(ORM):
    id: int
    # "fints" or "ing_csv"
    source: str
    filename: str | None
    created_at: datetime


class TransactionDetail(TransactionOut):
    """Everything stored about a transaction, for the detail view."""

    balance_after: Decimal | None
    counterparty_iban: str | None
    counterparty_bic: str | None
    mandate_id: str | None
    creditor_id: str | None
    end_to_end_ref: str | None
    created_at: datetime
    account: TransactionAccount
    import_batch: TransactionImport | None
    # The rule that assigned the category (category_source = "rule")
    rule: RuleOut | None = None


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
    # Recognized file layout, e.g. "Sparkasse", or the name of a saved mapping
    format_name: str | None = None


class CsvFormatOut(BaseModel):
    id: str
    name: str
    hint: str


class CsvMappingIn(BaseModel):
    delimiter: str = Field(max_length=1)
    header_row: int = Field(ge=0)
    columns: dict[str, int]
    date_format: str = "dd.mm.yyyy"
    decimal: Literal["comma", "point"] = "comma"


class CsvSuggestion(BaseModel):
    columns: dict[str, int]
    date_format: str
    decimal: str


class CsvPreviewOut(BaseModel):
    """Result of looking at a file before importing it."""

    # Built-in layout or saved mapping that recognizes the file; null if unknown
    format_name: str | None
    delimiter: str
    header_row: int
    columns: list[str]
    rows: list[list[str]]
    suggestion: CsvSuggestion


class CsvProfileOut(ORM):
    id: int
    name: str
    created_at: datetime


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


# --- Transfers ------------------------------------------------------------


class ExtraAccountIn(BaseModel):
    """An own account that is not tracked in Budgie."""

    name: str = Field(max_length=100)
    iban: str = Field(max_length=50)


class ExtraAccountOut(BaseModel):
    name: str
    iban: str


class TransferSettingsIn(BaseModel):
    auto_detect: bool = True
    extra_accounts: list[ExtraAccountIn] = Field([], max_length=50)


class TransferAccountOut(BaseModel):
    name: str
    iban: str


class TransferSettingsOut(BaseModel):
    auto_detect: bool
    extra_accounts: list[ExtraAccountOut]
    account_ibans: list[TransferAccountOut]
    # Transactions currently marked as detected transfers
    detected_count: int = 0
    # Transactions reassigned by the last save
    changed: int = 0


# --- FinTS ----------------------------------------------------------------

ING_BANK_CODE = "50010517"


class FintsStatus(BaseModel):
    enabled: bool
    missing: list[str]


class BankOut(BaseModel):
    """Entry of the bank directory."""

    bank_code: str
    name: str
    location: str
    bic: str
    server_url: str | None


class BankConnectionIn(BaseModel):
    # Defaults to ING, which Budgie supported first
    name: str = Field("ING", min_length=1, max_length=100)
    login: str = Field(min_length=1, max_length=100)
    customer_id: str | None = Field(None, max_length=100)
    bank_code: str = Field(ING_BANK_CODE, pattern=r"^\d{8}$")
    # Without an address, it is taken from the bank directory
    server_url: str | None = Field(None, pattern=r"^https://", max_length=255)


class BankConnectionPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    login: str | None = Field(None, min_length=1, max_length=100)
    customer_id: str | None = Field(None, max_length=100)
    server_url: str | None = Field(None, pattern=r"^https://", max_length=255)
    # Asks for the TAN mechanism (and TAN medium) again on the next sync
    reset_tan_mechanism: bool = False
    # Automatic fetching. Enabling needs a stored PIN; disabling deletes it.
    auto_sync_enabled: bool | None = None
    # Hours between fetches (PSD2 limits unattended access, see fints/autosync.py)
    auto_sync_interval_hours: Literal[6, 12, 24] | None = None
    # Write-only: stored encrypted, never returned
    pin: str | None = Field(None, min_length=1, max_length=100)


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
    auto_sync_enabled: bool
    auto_sync_interval_hours: int
    has_stored_pin: bool
    next_auto_sync_at: datetime | None
    # "tan_required", "pin_rejected", "locked" or "manual_sync_required"
    auto_sync_paused_reason: str | None
    accounts: list[LinkedAccount] = []


class SyncIn(BaseModel):
    pin: str = Field(min_length=1, max_length=100)
    start_date: date | None = None


class TanIn(BaseModel):
    tan: str = Field(min_length=1, max_length=100)


class ChoiceIn(BaseModel):
    option: str = Field(min_length=1, max_length=100)


class ChoiceOption(BaseModel):
    id: str
    name: str
    decoupled: bool = False


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
    challenge_hhduc: str | None = None
    choice_kind: str | None = None
    options: list[ChoiceOption] = []
    error: str | None
    results: list[SyncResult]

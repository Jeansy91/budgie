"""Training, prediction and background work for AI categorization."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Account, Category, CategoryKind, CategorySource, ClassifierModel, Transaction
from . import llm
from .classifier import WEIGHT_EXAMPLE, WEIGHT_MANUAL, WEIGHT_RULE, Classifier, Sample, cross_validate, train
from .examples import EXAMPLES
from .features import TxText

log = logging.getLogger(__name__)

# In tests everything runs immediately instead of in the background
SYNC = False
# Several corrections in quick succession trigger only one training run
RETRAIN_DELAY = 3.0


def tx_text(t: Transaction) -> TxText:
    return TxText(t.payee or "", t.booking_text or "", t.purpose or "", t.amount, t.booking_date)


# --- Categories -----------------------------------------------------------


@dataclass
class CategoryIndex:
    labels: dict[int, str] = field(default_factory=dict)  # id → "Main › Sub" (subcategories only)
    by_name: dict[tuple[str, str], int] = field(default_factory=dict)
    kinds: dict[int, CategoryKind] = field(default_factory=dict)

    def exclude(self) -> dict[int, set[int]]:
        # Debits are never income
        return {-1: {cid for cid, kind in self.kinds.items() if kind == CategoryKind.income}}


def category_index(db: Session, household_id: int) -> CategoryIndex:
    idx = CategoryIndex()
    cats = db.scalars(select(Category).where(Category.household_id == household_id)).all()
    names = {c.id: c.name for c in cats}
    for c in cats:
        idx.kinds[c.id] = c.kind
        if c.parent_id is not None:
            main = names.get(c.parent_id, "")
            idx.labels[c.id] = f"{main} › {c.name}"
            idx.by_name[(main.casefold(), c.name.casefold())] = c.id
    return idx


# --- Training -------------------------------------------------------------


def household_query(household_id: int):
    accounts = select(Account.id).where(Account.household_id == household_id)
    return select(Transaction).where(Transaction.account_id.in_(accounts))


def collect_samples(db: Session, household_id: int, idx: CategoryIndex) -> tuple[list[Sample], int, int]:
    """Training data: own assignments, rule matches and matching seed examples."""
    rows = db.scalars(
        household_query(household_id).where(
            Transaction.category_id.is_not(None),
            Transaction.category_source.in_([CategorySource.manual, CategorySource.rule]),
        )
    ).all()
    samples = [
        Sample(tx_text(t), t.category_id, WEIGHT_MANUAL if t.category_source == CategorySource.manual else WEIGHT_RULE)
        for t in rows
        if t.category_id in idx.kinds
    ]
    own, manual = len(samples), sum(s.weight == WEIGHT_MANUAL for s in samples)
    for payee, booking_text, amount, main, sub in EXAMPLES:
        cid = idx.by_name.get((main.casefold(), sub.casefold()))
        if cid is not None:
            samples.append(Sample(TxText(payee, booking_text, "", amount), cid, WEIGHT_EXAMPLE))
    return samples, own, manual


_cache: dict[int, tuple[int, Classifier]] = {}
_cache_lock = threading.Lock()


def fit_household(db: Session, household_id: int, with_accuracy: bool = True) -> ClassifierModel | None:
    """Retrains and adds the model to the session (without committing)."""
    idx = category_index(db, household_id)
    samples, own, manual = collect_samples(db, household_id, idx)
    started = time.monotonic()
    model = train(samples)
    if model is None:
        return None
    accuracy = cross_validate(samples) if with_accuracy else None
    row = ClassifierModel(
        household_id=household_id,
        samples=own,
        corrections=manual,
        classes=len(model.classes),
        accuracy=accuracy,
        blob=model.dumps(),
    )
    db.execute(delete(ClassifierModel).where(ClassifierModel.household_id == household_id))
    db.add(row)
    db.flush()
    with _cache_lock:
        _cache[household_id] = (row.id, model)
    log.info(
        "KI-Modell für Haushalt %s trainiert: %s eigene Beispiele, %s Kategorien, %.1fs",
        household_id, own, len(model.classes), time.monotonic() - started,
    )
    return row


def latest_model_row(db: Session, household_id: int) -> ClassifierModel | None:
    return db.scalar(
        select(ClassifierModel).where(ClassifierModel.household_id == household_id).order_by(ClassifierModel.id.desc())
    )


def load_model(db: Session, household_id: int, train_if_missing: bool = True) -> Classifier | None:
    latest_id = db.scalar(
        select(ClassifierModel.id)
        .where(ClassifierModel.household_id == household_id)
        .order_by(ClassifierModel.id.desc())
        .limit(1)
    )
    if latest_id is None:
        if not train_if_missing:
            return None
        # First use: start with the seed examples (and whatever is already assigned)
        row = fit_household(db, household_id, with_accuracy=False)
        return _cache[household_id][1] if row else None
    with _cache_lock:
        cached = _cache.get(household_id)
        if cached and cached[0] == latest_id:
            return cached[1]
    blob = db.scalar(select(ClassifierModel.blob).where(ClassifierModel.id == latest_id))
    try:
        model = Classifier.loads(blob)
    except Exception:
        # E.g. after a scikit-learn upgrade: simply retrain
        log.warning("Gespeichertes KI-Modell nicht lesbar, wird neu trainiert", exc_info=True)
        row = fit_household(db, household_id, with_accuracy=False)
        return _cache[household_id][1] if row else None
    with _cache_lock:
        _cache[household_id] = (latest_id, model)
    return model


# --- Prediction -----------------------------------------------------------


@dataclass
class CategorizeResult:
    assigned: int = 0
    suggested: int = 0
    unsure_ids: list[int] = field(default_factory=list)


def categorize(
    db: Session, household_id: int, transactions: Iterable[Transaction], redo_model: bool = False
) -> CategorizeResult:
    """Categorizes uncategorized transactions with the classifier.

    Manual and rule assignments are left untouched. With `redo_model`, earlier
    classifier results are recomputed as well.
    """
    result = CategorizeResult()
    settings = get_settings()
    if not settings.ai_enabled:
        return result
    todo = [
        t
        for t in transactions
        if t.category_id is None or (redo_model and t.category_source == CategorySource.model)
    ]
    if not todo:
        return result
    model = load_model(db, household_id)
    if model is None:
        return result
    idx = category_index(db, household_id)
    for t, p in zip(todo, model.predict([tx_text(t) for t in todo], idx.exclude()), strict=True):
        if p.category_id not in idx.kinds:
            continue  # Category has been deleted in the meantime
        if p.confidence >= settings.ai_auto_threshold:
            if t.category_id != p.category_id or t.category_source != CategorySource.model:
                result.assigned += 1
            t.category_id, t.category_source, t.rule_id = p.category_id, CategorySource.model, None
            t.category_confidence = round(p.confidence, 4)
            t.suggested_category_id, t.suggestion_confidence = None, None
            continue
        if t.category_source == CategorySource.model:
            t.category_id, t.category_source, t.category_confidence = None, None, None
        if p.confidence >= settings.ai_suggest_threshold:
            t.suggested_category_id, t.suggestion_confidence = p.category_id, round(p.confidence, 4)
            result.suggested += 1
        else:
            t.suggested_category_id, t.suggestion_confidence = None, None
        if t.id is not None:
            result.unsure_ids.append(t.id)
    return result


def recategorize(db: Session, household_id: int) -> CategorizeResult:
    """Recategorize all transactions not assigned manually or by a rule."""
    rows = db.scalars(
        household_query(household_id).where(
            (Transaction.category_id.is_(None)) | (Transaction.category_source == CategorySource.model)
        )
    ).all()
    return categorize(db, household_id, rows, redo_model=True)


# --- Background work ------------------------------------------------------

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="budgie-ai")
_lock = threading.Lock()
_retrain_pending: set[int] = set()
_futures: list[Future] = []


@dataclass
class LlmProgress:
    running: bool = False
    done: int = 0
    total: int = 0
    failed: int = 0
    last_error: str | None = None


llm_progress: dict[int, LlmProgress] = {}


def _submit(fn: Callable, *args) -> None:
    if SYNC:
        fn(*args)
        return
    with _lock:
        _futures[:] = [f for f in _futures if not f.done()]
        _futures.append(_executor.submit(fn, *args))


def wait_idle(timeout: float = 60) -> None:
    """Waits until all background tasks are done (for tests)."""
    with _lock:
        pending = list(_futures)
    for f in pending:
        f.result(timeout=timeout)


def after_commit(db: Session, fn: Callable[[], None]) -> None:
    """Runs `fn` once the current database transaction has been committed."""
    event.listen(db, "after_commit", lambda _session: fn(), once=True)


def schedule_retrain(household_id: int) -> None:
    with _lock:
        if household_id in _retrain_pending:
            return
        _retrain_pending.add(household_id)
    _submit(_retrain_job, household_id)


def _retrain_job(household_id: int) -> None:
    from ..db import SessionLocal

    if not SYNC:
        time.sleep(RETRAIN_DELAY)
    with _lock:
        _retrain_pending.discard(household_id)
    try:
        with SessionLocal() as db:
            if fit_household(db, household_id) is None:
                db.commit()
                return
            result = recategorize(db, household_id)
            db.commit()
        if result.unsure_ids:
            schedule_llm(household_id, result.unsure_ids)
    except Exception:
        log.exception("Training der KI für Haushalt %s fehlgeschlagen", household_id)


def schedule_llm(household_id: int, transaction_ids: list[int]) -> None:
    if not transaction_ids or not llm.enabled() or not get_settings().ai_enabled:
        return
    _submit(_llm_job, household_id, list(transaction_ids))


def _llm_job(household_id: int, transaction_ids: list[int]) -> None:
    from ..db import SessionLocal

    settings = get_settings()
    progress = llm_progress.setdefault(household_id, LlmProgress())
    ids = transaction_ids[: settings.ollama_max_per_run]
    progress.running, progress.done, progress.total, progress.failed = True, 0, len(ids), 0
    try:
        with SessionLocal() as db:
            idx = category_index(db, household_id)
            label_to_id = {label: cid for cid, label in idx.labels.items()}
            model = load_model(db, household_id, train_if_missing=False)
            for tid in ids:
                t = db.get(Transaction, tid)
                if t is None or t.category_id is not None:
                    progress.total -= 1
                    continue
                # Direction does not match: no income category for debits
                banned = idx.exclude().get(1 if float(t.amount) > 0 else -1, set())
                labels = [label for cid, label in idx.labels.items() if cid not in banned]
                hints = []
                if model is not None:
                    hints = [idx.labels[p.category_id] for p in model.top(tx_text(t)) if p.category_id in idx.labels]
                try:
                    label = llm.classify(tx_text(t), labels, hints)
                except llm.LlmError as exc:
                    progress.failed += 1
                    progress.last_error = str(exc)
                    log.warning("Sprachmodell konnte Buchung %s nicht einordnen: %s", tid, exc)
                    if progress.failed >= 3 and progress.done == 0:
                        break  # Ollama does not respond at all, try again later
                    continue
                db.refresh(t)
                if t.category_id is None:
                    t.category_id, t.category_source, t.rule_id = label_to_id[label], CategorySource.llm, None
                    t.category_confidence = None
                    t.suggested_category_id, t.suggestion_confidence = None, None
                    db.commit()
                progress.done += 1
    except Exception as exc:
        progress.last_error = str(exc)
        log.exception("Sprachmodell-Durchlauf für Haushalt %s fehlgeschlagen", household_id)
    finally:
        progress.running = False

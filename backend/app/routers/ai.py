from fastapi import APIRouter, status
from sqlalchemy import func

from ..ai import llm
from ..ai import service as ai
from ..config import get_settings
from ..deps import DB, CurrentUser
from ..i18n import http_error
from ..models import CategorySource, Transaction
from ..schemas import AiModelInfo, AiStatus, LlmInfo, RecategorizeIn, RecategorizeOut

router = APIRouter(prefix="/ai", tags=["ai"])


def _count(db: DB, household_id: int, *conditions) -> int:
    query = ai.household_query(household_id).where(*conditions).with_only_columns(func.count(Transaction.id))
    return db.scalar(query) or 0


@router.get("/status", response_model=AiStatus)
def ai_status(db: DB, user: CurrentUser):
    settings = get_settings()
    row = ai.latest_model_row(db, user.household_id)
    ollama = llm.status()
    progress = ai.llm_progress.get(user.household_id, ai.LlmProgress())
    hh = user.household_id
    return AiStatus(
        enabled=settings.ai_enabled,
        auto_threshold=settings.ai_auto_threshold,
        model=AiModelInfo(
            trained_at=row.created_at,
            samples=row.samples,
            corrections=row.corrections,
            classes=row.classes,
            accuracy=row.accuracy,
        )
        if row
        else None,
        llm=LlmInfo(
            configured=ollama.configured,
            reachable=ollama.reachable,
            model_available=ollama.model_available,
            model=ollama.model,
            error=ollama.error or (progress.last_error if progress.failed else None),
            running=progress.running,
            done=progress.done,
            total=progress.total,
            failed=progress.failed,
        ),
        ai_categorized=_count(db, hh, Transaction.category_source.in_([CategorySource.model, CategorySource.llm])),
        suggestions=_count(db, hh, Transaction.suggested_category_id.is_not(None)),
        uncategorized=_count(db, hh, Transaction.category_id.is_(None)),
    )


def _require_enabled() -> None:
    if not get_settings().ai_enabled:
        raise http_error(status.HTTP_409_CONFLICT, "ai.disabled")


@router.post("/train", response_model=AiStatus)
def train_now(db: DB, user: CurrentUser):
    """Retrains immediately and then recategorizes all open AI cases."""
    _require_enabled()
    if ai.fit_household(db, user.household_id) is not None:
        ai.recategorize(db, user.household_id)
    db.commit()
    return ai_status(db, user)


@router.post("/recategorize", response_model=RecategorizeOut)
def recategorize(data: RecategorizeIn, db: DB, user: CurrentUser):
    """Recategorizes all transactions without a manual or rule assignment.

    Uncertain cases are then sent to the language model in the background.
    """
    _require_enabled()
    result = ai.recategorize(db, user.household_id)
    queued = 0
    if data.use_llm and llm.enabled() and result.unsure_ids:
        household_id, ids = user.household_id, result.unsure_ids
        queued = min(len(ids), get_settings().ollama_max_per_run)
        ai.after_commit(db, lambda: ai.schedule_llm(household_id, ids))
    db.commit()
    return RecategorizeOut(assigned=result.assigned, suggested=result.suggested, llm_queued=queued)

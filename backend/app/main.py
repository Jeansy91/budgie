from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from . import budget_month
from .config import get_settings
from .fints import scheduler
from .i18n import LocaleMiddleware
from .routers import (
    accounts,
    ai,
    auth,
    budget,
    categories,
    fints,
    imports,
    overview,
    rules,
    transactions,
    transfers,
    users,
)

budget_month.register_events()  # automatic recomputation of the budget months (idempotent)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if get_settings().fints_auto_sync:
        scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(title="Budgie", version="0.2.0", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
app.add_middleware(LocaleMiddleware)

api = APIRouter(prefix="/api")
for module in (auth, users, accounts, categories, rules, transactions, imports, fints, ai, overview, budget, transfers):
    api.include_router(module.router)


@api.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


app.include_router(api)

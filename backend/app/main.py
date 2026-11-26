from fastapi import APIRouter, FastAPI

from . import budget_month
from .i18n import LocaleMiddleware
from .routers import accounts, ai, auth, budget, categories, fints, imports, overview, rules, transactions, users

budget_month.register_events()  # automatic recomputation of the budget months (idempotent)

app = FastAPI(title="Budgie", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(LocaleMiddleware)

api = APIRouter(prefix="/api")
for module in (auth, users, accounts, categories, rules, transactions, imports, fints, ai, overview, budget):
    api.include_router(module.router)


@api.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


app.include_router(api)

"""Optional local language model via Ollama (https://ollama.com).

Only used when BUDGIE_OLLAMA_URL is set. The response is constrained to the
existing categories with a JSON schema. The prompt is in German because
transaction texts and category names are German.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from ..config import get_settings
from .features import TxText

log = logging.getLogger(__name__)


class LlmError(Exception):
    pass


@dataclass
class OllamaStatus:
    configured: bool
    reachable: bool = False
    model_available: bool = False
    model: str = ""
    error: str | None = None


def enabled() -> bool:
    return bool(get_settings().ollama_url.strip())


def status() -> OllamaStatus:
    settings = get_settings()
    if not enabled():
        return OllamaStatus(configured=False, model=settings.ollama_model)
    try:
        r = httpx.get(settings.ollama_url.rstrip("/") + "/api/tags", timeout=3)
        r.raise_for_status()
        names = {m.get("name", "") for m in r.json().get("models", [])}
        wanted = settings.ollama_model
        available = wanted in names or (":" not in wanted and f"{wanted}:latest" in names)
        return OllamaStatus(
            configured=True,
            reachable=True,
            model_available=available,
            model=wanted,
            error=None if available else f"Modell {wanted} fehlt, bitte mit „ollama pull {wanted}“ laden",
        )
    except (httpx.HTTPError, ValueError) as exc:
        return OllamaStatus(configured=True, model=settings.ollama_model, error=f"Ollama nicht erreichbar: {exc}")


SYSTEM_PROMPT = (
    "Du ordnest Kontobewegungen eines deutschen Privathaushalts genau einer Kategorie zu. "
    "Antworte nur mit JSON. Wähle die Kategorie, die am besten passt. Negative Beträge sind Ausgaben, "
    "positive Beträge Einnahmen oder Erstattungen. Umbuchungen zwischen eigenen Konten und "
    "Kreditkartenabrechnungen sind Transfers."
)


def classify(t: TxText, labels: list[str], hints: list[str] | None = None) -> str:
    """Returns one of `labels` (format "Main › Sub")."""
    settings = get_settings()
    lines = [
        f"Empfänger/Auftraggeber: {t.payee or '-'}",
        f"Buchungstext: {t.booking_text or '-'}",
        f"Verwendungszweck: {(t.purpose or '-')[:400]}",
        f"Betrag: {float(t.amount):.2f} EUR",
    ]
    if hints:
        lines.append("Vermutung eines einfachen Modells (kann falsch sein): " + ", ".join(hints))
    lines.append("\nMögliche Kategorien:\n" + "\n".join(f"- {label}" for label in labels))
    schema = {
        "type": "object",
        "properties": {"kategorie": {"type": "string", "enum": labels}},
        "required": ["kategorie"],
    }
    try:
        r = httpx.post(
            settings.ollama_url.rstrip("/") + "/api/chat",
            json={
                "model": settings.ollama_model,
                "stream": False,
                "format": schema,
                "keep_alive": "15m",
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "\n".join(lines)},
                ],
            },
            timeout=settings.ollama_timeout,
        )
        r.raise_for_status()
        content = r.json()["message"]["content"]
        label = json.loads(content)["kategorie"]
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        raise LlmError(str(exc)) from exc
    if label not in labels:
        raise LlmError(f"Unbekannte Kategorie in der Antwort: {label!r}")
    return label

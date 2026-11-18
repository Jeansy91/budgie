"""Regenerates app/fints/banks.json, the bundled bank directory.

Source: `fints-institutes.json` from the npm package `fints-institute-db`
(public domain, CC0 1.0), or the official `fints_institute.csv` of the
Deutsche Kreditwirtschaft for a local, non-redistributed build.

    npm pack fints-institute-db && tar xzf fints-institute-db-*.tgz
    python scripts/build_bank_directory.py package/fints-institutes.json

The directory keeps one entry per bank code (BLZ): name, location, BIC and the
FinTS PIN/TAN address. Moved server addresses are corrected at load time, see
`URL_REPLACEMENTS` in app/fints/directory.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.fints.directory import BUNDLED, Bank, _dedupe, parse_institute_csv  # noqa: E402


def load(path: Path) -> list[Bank]:
    if path.suffix == ".csv":
        return parse_institute_csv(path.read_bytes())
    return [
        Bank(
            bank_code=entry["blz"],
            name=" ".join((entry.get("name") or "").split()),
            location=" ".join((entry.get("location") or "").split()),
            bic=entry.get("bic") or "",
            server_url=entry.get("pinTanURL") or None,
        )
        for entry in json.loads(path.read_text(encoding="utf-8"))
        if entry.get("blz") and len(entry["blz"]) == 8
    ]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    banks = sorted(_dedupe(load(Path(sys.argv[1]))).values(), key=lambda b: b.bank_code)
    data = {
        "source": "fints-institute-db (CC0 1.0), https://github.com/jhermsmeier/fints-institute-db",
        "fields": ["bank_code", "name", "location", "bic", "server_url"],
        "banks": [[b.bank_code, b.name, b.location, b.bic, b.server_url or ""] for b in banks],
    }
    lines = ",\n".join(json.dumps(row, ensure_ascii=False) for row in data["banks"])
    head = json.dumps({k: v for k, v in data.items() if k != "banks"}, ensure_ascii=False)[:-1]
    BUNDLED.write_text(f'{head}, "banks": [\n{lines}\n]}}\n', encoding="utf-8")
    print(f"{len(banks)} banks, {sum(1 for b in banks if b.server_url)} with FinTS address → {BUNDLED}")


if __name__ == "__main__":
    main()

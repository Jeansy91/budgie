<h1 align="center">🦜 Budgie</h1>

<p align="center">
  <strong>A self-hosted household budget book for German bank accounts, with FinTS sync and local, privacy-friendly AI categorization.</strong>
</p>

<p align="center">
  <a href="https://github.com/Jeansy91/budgie/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Jeansy91/budgie/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/Jeansy91/budgie/actions/workflows/codeql.yml"><img alt="CodeQL" src="https://github.com/Jeansy91/budgie/actions/workflows/codeql.yml/badge.svg"></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/Jeansy91/budgie"><img alt="OpenSSF Scorecard" src="https://api.scorecard.dev/projects/github.com/Jeansy91/budgie/badge"></a>
  <a href="https://github.com/Jeansy91/budgie/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/Jeansy91/budgie?sort=semver"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green.svg"></a>
  <a href="https://github.com/Jeansy91/budgie/pkgs/container/budgie-api"><img alt="Docker images on GHCR" src="https://img.shields.io/badge/docker-ghcr.io-2496ED?logo=docker&logoColor=white"></a>
  <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white">
  <img alt="SvelteKit" src="https://img.shields.io/badge/SvelteKit-FF3E00?logo=svelte&logoColor=white">
  <img alt="Self-hosted" src="https://img.shields.io/badge/self--hosted-yes-10b981">
</p>

<p align="center">
  <img src="docs/screenshots/overview.png" alt="Monthly overview" width="900">
</p>

Budgie (budgerigar + budget) pulls your transactions straight from your bank via FinTS/HBCI or from a CSV export, sorts them into categories with a classifier that learns from your corrections, and shows where your money goes each month. Everything runs in your own Docker stack: no cloud service ever sees your banking data.

> [!NOTE]
> The user interface is available in **German** and **English**; each user picks a language in the settings (by default Budgie follows the browser language). FinTS sync works with German banks that offer PIN/TAN access; it was built for ING first, and other banks are supported through a bank directory and TAN mechanism selection (see [Supported banks](#supported-banks)).

## Features

- **Bank sync via FinTS** – pick your bank from a built-in directory and fetch transactions for all accounts of a login, with app approval (ING, pushTAN 2.0, …) or classic TAN entry such as chipTAN or photoTAN. By default the PIN is not stored.
- **CSV import** – CSV exports of ING, Sparkasse, Volksbank/Raiffeisenbank, DKB, comdirect, Commerzbank, Deutsche Bank and N26 are recognized automatically; for any other bank you assign the columns once and save the mapping as a template. Duplicates are detected across both sources.
- **Learning categorization** – a local scikit-learn classifier assigns categories and suggests them when unsure. Every correction becomes a training example and the model retrains in the background.
- **Optional local LLM** – uncertain cases can be handed to a language model running in [Ollama](https://ollama.com) on your own CPU.
- **Rules** – deterministic rules (contains, equals, starts with, regex) always take precedence over the AI. Manual assignments are never overwritten.
- **Transaction details** – tap a transaction to see everything the bank delivered: full purpose text, counterparty IBAN/BIC, mandate reference, creditor ID, end-to-end reference, import source and how the category was assigned. Change the category or budget month, add a note or create a rule right from there.
- **Budget month** – salary paid at the end of a month automatically counts towards the following month, so your monthly overview matches how you actually spend.
- **Multi-user households** – separate logins, shared or private accounts, and a default set of 14 main categories with subcategories (fully editable).
- **Modern, mobile-friendly UI** – light and dark mode, custom form controls, bottom sheets on phones.

<p align="center">
  <img src="docs/screenshots/budget-month.png" alt="Transactions with budget month" width="440">
  <img src="docs/screenshots/category-picker-dark.png" alt="Category picker in dark mode" width="440">
</p>
<p align="center">
  <img src="docs/screenshots/rules-dark.png" alt="Rules" width="440">
  <img src="docs/screenshots/mobile-category-picker.png" alt="Category picker on mobile" width="200">
</p>

## Quick start

Budgie ships as prebuilt images on the GitHub Container Registry (`linux/amd64`):

- `ghcr.io/jeansy91/budgie-api`
- `ghcr.io/jeansy91/budgie-web`

The provided `docker-compose.yml` expects [Traefik](https://traefik.io) as a reverse proxy attached to an external Docker network (default name `traefik`).

```bash
git clone https://github.com/Jeansy91/budgie.git
cd budgie
cp .env.example .env      # set the database password, hostname and Traefik network
docker compose pull
docker compose up -d
```

Downloading just `docker-compose.yml` and `.env.example` works as well.

Then open `https://<BUDGIE_HOST>`. On first launch you create the household and your admin account; the default categories are set up automatically. Additional users can be added under **Einstellungen** (settings).

> [!IMPORTANT]
> If you serve Budgie without HTTPS, set `BUDGIE_COOKIE_SECURE=false`, otherwise login will not work.

> [!TIP]
> If the container images are private (for example in a fork), log in once with a personal access token that only has the `read:packages` scope:
> `echo <TOKEN> | docker login ghcr.io -u <github-user> --password-stdin`

### Services

| Service  | Purpose                                                        | Networks           |
| -------- | -------------------------------------------------------------- | ------------------ |
| `web`    | SvelteKit frontend (port 3000)                                 | Traefik            |
| `api`    | FastAPI backend under `/api` (port 8000), runs DB migrations on start | Traefik + internal |
| `db`     | PostgreSQL 16, data in the `db-data` volume                    | internal only      |
| `ollama` | Optional local LLM (profile `ai`)                              | internal + egress  |

Traefik routes `Host(BUDGIE_HOST) && PathPrefix(/api)` to `api` and everything else to `web`. No ports are published on the host.

### Updating

```bash
docker compose pull && docker compose up -d
```

Images are rebuilt on every push to `main`, but only after all tests pass (`latest` tag). For a stable setup, pin a [release](https://github.com/Jeansy91/budgie/releases) with `BUDGIE_VERSION` in `.env`, e.g. `0.1.0` for the release `v0.1.0` (or `0.1` to follow its patch releases), or `sha-89f1785` for a specific commit. What changed between versions is listed in the [changelog](CHANGELOG.md).

To build the images yourself instead: `docker compose up -d --build`.

## Configuration

All settings are read from `.env` (see [`.env.example`](.env.example)). Credentials and keys are never baked into the images.

| Variable | Default | Description |
| --- | --- | --- |
| `BUDGIE_VERSION` | `latest` | Image tag to pull. |
| `POSTGRES_PASSWORD` | – (required) | Password of the PostgreSQL user. |
| `BUDGIE_HOST` | – (required) | Hostname Traefik serves Budgie on. |
| `TRAEFIK_NETWORK` | `traefik` | External Docker network Traefik is attached to. |
| `TRAEFIK_ENTRYPOINT` | `websecure` | Traefik entrypoint for the routers. |
| `TRAEFIK_TLS` | `true` | Enable TLS on the Traefik routers. |
| `BUDGIE_COOKIE_SECURE` | `true` | Send the session cookie over HTTPS only. |
| `BUDGIE_SECRET_KEY` | – | Key for encrypting stored bank logins. Required for FinTS. |
| `BUDGIE_FINTS_PRODUCT_ID` | – | FinTS product ID. Required for FinTS. |
| `BUDGIE_FINTS_AUTO_SYNC` | `true` | Run the background scheduler for automatic FinTS fetches. Set to `false` to disable it for the whole installation. |
| `BUDGIE_FINTS_INSTITUTES_FILE` | – | Path to the official FinTS institute list (`fints_institute.csv`) inside the api container. Replaces the bundled bank directory. |
| `BUDGIE_AI_ENABLED` | `true` | Enable the local classifier. |
| `BUDGIE_AI_AUTO_THRESHOLD` | `0.6` | Confidence at which the AI assigns a category itself; below it only suggests one. |
| `BUDGIE_OLLAMA_URL` | – | Ollama base URL, e.g. `http://ollama:11434`. Empty disables the LLM. |
| `BUDGIE_OLLAMA_MODEL` | `qwen2.5:7b` | Ollama model used for uncertain cases. |

## Bank sync via FinTS

One-time setup:

1. **Register a FinTS product** with the Deutsche Kreditwirtschaft. Registration is free and also open to individuals: [hbci-zka.de/register](https://www.hbci-zka.de/register/prod_register.htm). Put the assigned product ID into `.env` as `BUDGIE_FINTS_PRODUCT_ID`.
2. **Generate an encryption key** with `openssl rand -base64 32` and set it as `BUDGIE_SECRET_KEY`. It encrypts the stored login name. Keep it safe: without it, stored bank connections cannot be decrypted.
3. Restart with `docker compose up -d`, then add your bank login under **Import → Direkt von der Bank abrufen**: search your bank by name, city, bank code (BLZ) or BIC, and enter the login name you use for online banking. The FinTS server address comes from the bank directory and can be changed under **Erweitert**, where you can also enter a separate customer ID if your bank requires one.

Syncing:

1. Click **Umsätze abrufen** and enter your online banking PIN. By default the PIN is **not stored**; it only lives in the API process memory for the duration of the sync. Only if you turn on automatic fetching (below) is it stored, encrypted.
2. On the first sync, Budgie selects the TAN mechanism: if the bank offers exactly one app approval mechanism, it is used; otherwise you choose from the list the bank reports. If the bank knows several TAN devices (e.g. two phones), you pick one as well. The choice is remembered and can be reset with **TAN-Verfahren ändern**.
3. If the bank asks for approval, Budgie waits until you confirm in your banking app and then continues automatically. For TAN mechanisms that require input (chipTAN, photoTAN, smsTAN), an input field with the challenge text or image is shown.
4. All accounts of the login are fetched and matched by IBAN; missing accounts are created. The first sync fetches the last 90 days, later syncs continue from the last one with a 14-day overlap. You can choose an earlier start date, but because of PSD2 banks often require an extra approval for older transactions.

FinTS and CSV can be mixed: transactions already imported from a CSV file are recognized during a FinTS sync (same day and amount) and vice versa. A common approach is to import the older history once via CSV and use FinTS from then on.

### Automatic fetch

Per bank login you can turn on **Automatischer Abruf**. Budgie then fetches new transactions in the background, imports them through the same path as a manual sync (duplicate detection, rules and AI categorization) and shows when the next fetch is due.

- **Intervals:** every 6, 12 or 24 hours. Under PSD2, access without the customer being present is limited; banks commonly allow about four such fetches per day, and many rate-limit FinTS dialogs. The scheduler adds a small random delay so it does not hit the bank at the same minute. Connections are fetched one after another, never in parallel.
- **PIN storage (opt-in, per login):** unattended fetches need the PIN, so turning the feature on stores it, encrypted with a key derived from `BUDGIE_SECRET_KEY`. Anyone who has both the database and the secret key (or can run code on the server) can read it. Turning automatic fetch off deletes the PIN, as does changing the login name or customer ID. If you do not want this trade-off, leave automatic fetch off and enter the PIN for every sync.
- **First fetch is manual:** Budgie has to learn your TAN method first, so run one manual fetch before automatic fetching starts.
- **TAN behaviour:** an automatic fetch never waits for you. If the bank asks for a TAN or an approval in the banking app, the fetch is aborted and automatic fetching is **paused** for that login (at most one prompt reaches your phone). Run a manual fetch once to resume. Whether your bank asks depends on the bank and on how old the requested transactions are.
- **Wrong PIN:** if the bank rejects the stored PIN, automatic fetching is paused and the PIN is deleted right away, so repeated attempts cannot lock your bank access. Enter the PIN again to resume. If the bank reports the access as locked, automatic fetching is paused until you unlock it and run a manual fetch.
- **Other errors** (e.g. the bank is unreachable) are retried with a growing delay: the interval doubles with every consecutive failure, up to 48 hours, and resets after a successful fetch.
- Set `BUDGIE_FINTS_AUTO_SYNC=false` to disable the scheduler completely. The scheduler runs inside the single API process.

A bank login always belongs to one user. Other household members see the synced accounts, but not the login itself.

### Supported banks

The bank directory (`backend/app/fints/directory.py`) is generated from the public domain dataset [fints-institute-db](https://github.com/jhermsmeier/fints-institute-db) and covers about 2,000 bank codes with a FinTS address, including Sparkassen, Volksbanken/Raiffeisenbanken (Atruvia), DKB, comdirect, Commerzbank, Deutsche Bank, Postbank, Consorsbank, HypoVereinsbank and Targobank. Server addresses that moved since the dataset was collected are corrected (e.g. the cooperative banks now use `fints1.atruvia.de` / `fints2.atruvia.de`). The dataset is a few years old, so an address can still be outdated; if a sync cannot connect, check your bank's FinTS/HBCI help page and edit the address. With a FinTS product registration you also receive the official institute list from the Deutsche Kreditwirtschaft; mount it and set `BUDGIE_FINTS_INSTITUTES_FILE` to use it instead.

Notes:

- **ING** is the bank Budgie was built for first. Like ING, all other banks have so far only been tested against a simulated FinTS client in the test suite, not against their real servers. Reports are welcome.
- **chipTAN optical (flicker code)** cannot be shown as an animation. Budgie shows the start code for manual entry; chipTAN QR and photoTAN images are displayed.
- **N26, Revolut and other banks without FinTS** can only be imported via CSV.

![Adding a bank connection](docs/screenshots/banks/bank-form.png)

## CSV import

1. Export the transactions of an account as CSV in your online banking.
2. Upload the file in Budgie under **Import**. The bank's layout is recognized from the header row; the account is detected by its IBAN and created on first import. Files without an IBAN (comdirect, N26) need a target account selected under **Importieren in**.
3. Transactions that were already imported are skipped, so overlapping periods are fine. Pending transactions in the export are left out.

Recognized layouts: ING ("Umsatzanzeige"), Sparkasse (CSV-CAMT and CSV-MT940), Volksbank/Raiffeisenbank (Atruvia), DKB (current and pre-2023), comdirect (first account section of the file), Commerzbank, Deutsche Bank and N26 (current and old). These were written from the banks' export layouts and are tested against made-up sample files in `backend/tests/data/csv`; real exports may differ in details. If a layout is not recognized, Budgie shows the first rows of the file and lets you assign the columns (date, amount or debit/credit, payee, purpose, …). Saved as a template, the mapping is applied automatically to files with the same header row.

![Column mapping for an unknown CSV layout](docs/screenshots/banks/csv-mapping.png)

## Categorization

- **AI:** during import (CSV and FinTS), a local classifier categorizes every transaction that no rule matches. At or above 60 % confidence it assigns the category itself (badge "KI 87 %"); below that it shows a **suggestion** you can accept with one click.
- **Learning:** every category you change and every AI assignment you confirm is a training example. A few seconds later Budgie retrains in the background and re-evaluates open transactions. Out of the box the model already knows typical German payees such as REWE, Aral or Netflix.
- **Review:** a filter under **Buchungen** shows all AI assignments and suggestions nobody has confirmed yet. **Einstellungen → KI-Kategorisierung** shows accuracy, training status and buttons to retrain immediately.
- **Rules** always win: create them from the transaction list ("Regeln lernen") or under **Regeln** (payee/purpose contains, equals, starts with, regex). Rules override AI assignments; manual assignments are never overwritten.
- Transfers between your own accounts count as neither income nor expense.

### Optional: local language model

Transactions the classifier cannot categorize confidently can be handed to a language model in [Ollama](https://ollama.com). It runs on the CPU inside your stack; a 7–8B model needs about 6–8 GB of RAM and a few seconds per transaction. The work happens in the background after an import.

```bash
docker compose --profile ai up -d
docker compose exec ollama ollama pull qwen2.5:7b
# set BUDGIE_OLLAMA_URL=http://ollama:11434 in .env, then
docker compose up -d api
```

Without `BUDGIE_OLLAMA_URL` the language model stays disabled. The Ollama service is only attached to the internal network and to a separate egress network for downloading models; it is not reachable from outside.

## Architecture

```
SvelteKit (web) ──/api──▶ FastAPI (api) ──▶ PostgreSQL (db)
                              │
                              ├── python-fints ──▶ bank FinTS server
                              ├── scikit-learn classifier (in-process)
                              └── Ollama (optional, internal network)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the data flow, the categorization pipeline and the default category scheme.

## Development

Requirements: Python 3.13, Node.js 26 and a PostgreSQL 16 database.

```bash
# Backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r requirements-dev.txt
export BUDGIE_DATABASE_URL=postgresql+psycopg://budgie:budgie@localhost:5432/budgie BUDGIE_COOKIE_SECURE=false
alembic upgrade head
uvicorn app.main:app --reload          # API docs: http://localhost:8000/api/docs

# Frontend
cd frontend
npm install
npm run dev                             # proxies /api to localhost:8000
```

A throwaway database for development:

```bash
docker run -d --name budgie-dev-db -p 5432:5432 \
  -e POSTGRES_USER=budgie -e POSTGRES_PASSWORD=budgie -e POSTGRES_DB=budgie postgres:16-alpine
```

**Schema changes:** update the models in `backend/app/models.py`, then create a migration with `alembic revision --autogenerate -m "<description>"`.

### Tests

```bash
# Backend: needs an empty test database in BUDGIE_DATABASE_URL
cd backend && pytest

# Frontend: type checks and production build
cd frontend && npm run check && npm run build
```

CI runs the same steps on every pull request, plus a migration round trip (`alembic upgrade head && alembic check && alembic downgrade base`).

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first, and report security issues as described in [SECURITY.md](SECURITY.md).

## Support

Budgie is free and open source. If it saves you time, you can support its development on [Ko-fi](https://ko-fi.com/jeansy91).

## License

Budgie is released under the [MIT License](LICENSE).

Budgie is not affiliated with ING or any other bank. Use it at your own risk and always keep your online banking credentials safe.

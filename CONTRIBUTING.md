# Contributing to Budgie

Thanks for your interest in Budgie! Bug reports, ideas and pull requests are welcome.

## Before you start

- **Bugs and feature requests:** open an issue using one of the templates. For larger changes, please open an issue first so we can agree on the approach before you invest time.
- **Security issues:** do **not** open a public issue. Follow [SECURITY.md](SECURITY.md) instead.
- **Never include real banking data** in issues, pull requests, test fixtures or screenshots: no IBANs, account numbers, login names, PINs, TANs, balances or transaction texts from real accounts. Use obviously fake data such as `DE89 3704 0044 0532 0130 00` and "REWE Markt GmbH".

## Development setup

See [Development](README.md#development) in the README. In short:

- Backend: Python 3.13, FastAPI, SQLAlchemy 2, Alembic, pytest against a real PostgreSQL 16 database.
- Frontend: Node.js 22, SvelteKit 2 with Svelte 5.

## Guidelines

### Code

- Keep changes focused. One pull request should address one topic.
- **Database schema changes** always go through a new Alembic revision (`alembic revision --autogenerate -m "<description>"`). Never edit a migration that has already been released.
- **Categorization invariants:** manual assignments are never overwritten automatically, and rules take precedence over AI assignments. Please keep it that way and cover changes with tests.
- **Credentials:** the online banking PIN must never be persisted or logged. Other bank data stored in the database must be encrypted via `app/crypto.py`.
- **UI:** the app uses its own form components in `frontend/src/lib/ui` instead of native selects, date pickers etc. Please reuse them. The UI language is currently German.
- Code, comments, commit messages and documentation are written in **English**.

### Tests

Run the checks that CI runs before opening a pull request:

```bash
cd backend && pytest
cd frontend && npm run check && npm run build
```

New features and bug fixes should come with tests. FinTS code is tested against a fake bank client (`backend/tests/test_fints.py`); tests must never talk to a real bank.

### Commits and pull requests

- Write commit messages in the imperative mood ("Add CSV import for …", not "Added …"), with a short summary line and an optional body explaining *why*.
- Fill in the pull request template, link related issues and add screenshots for UI changes (with fake data).
- CI must be green before a pull request is merged.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).

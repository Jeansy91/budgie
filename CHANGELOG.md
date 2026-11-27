# Changelog

All notable changes to Budgie are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the version is below 1.0.0, minor releases may contain breaking changes; they are called out in the release notes.

## [Unreleased]

### Added

- Transfers between own accounts are detected automatically: a transaction whose counterparty IBAN belongs to another account of the household, or to an additional own IBAN entered in the settings, is assigned to the transfer category. Detection runs before rules and AI and never overrides manual assignments; existing transactions are backfilled on upgrade. CSV exports without counterparty IBAN are not affected.
- A "Hide transfers" switch on the transactions page (on by default) and a "Mark as transfer" quick action in the transaction details.

## [0.2.0] - 2026-11-27

### Added

- Automatic FinTS fetch per bank login (opt-in): every 6, 12 or 24 hours a background scheduler fetches new transactions through the normal import path. The PIN is stored encrypted only while it is enabled. It never waits for a TAN: if the bank asks for one, automatic fetching pauses until the next manual sync. New setting `BUDGIE_FINTS_AUTO_SYNC`.
- Rules can match on the sender (incoming transactions only) or the recipient (outgoing transactions only). The existing payee field still matches both directions and is labelled accordingly.
- CI runs linters (ruff, mypy, prettier, eslint) and tests with coverage reports, and scans the container images with Trivy on every pull request and push.
- CodeQL, dependency review and OpenSSF Scorecard workflows, a CODEOWNERS file and pre-commit hooks.
- CI, CodeQL and OpenSSF Scorecard badges in the README and a "Security tooling" section in the security policy.

### Changed

- The app uses the full width of wide screens: content grows up to 1920px and is centred next to the sidebar. On wide screens the monthly overview shows the category breakdown, income and the 12-month chart side by side. Settings and import keep a readable maximum width.
- Backend dependencies are hash-locked with pip-compile (`requirements.in` and `requirements-dev.in` are the sources) and installed with `--require-hashes` in the Dockerfile and CI. The workflow is documented in the contributing guide.
- Docker base images are pinned by digest.
- CodeQL configuration moved to `.github/codeql/codeql-config.yml` and ignores the Alembic revision files, whose module variables are read by Alembic.
- Log output no longer contains IBANs.
- Fixed CodeQL findings: side effects in test assertions, unused imports and an unused variable.
- All GitHub Actions are pinned to commit SHAs, and workflows run with least-privilege permissions.
- Contributing guide and pull request template list the new lint and test commands.
- Dependabot now keeps GitHub Actions, Python and npm dependencies and Docker base images up to date.
- CI uses the latest major versions of all GitHub Actions.
- The license copyright holder is now Jeansy91.
- Runtime images no longer ship pip, setuptools and wheel (backend) or npm, npx and corepack (frontend), and apply pending OS package updates at build time. This clears the Trivy findings in the base images.
- Frontend runs on Node.js 26 (Active LTS) in the container image and in CI.
- Frontend upgraded to SvelteKit 3 with `@sveltejs/adapter-node` 6, `@sveltejs/vite-plugin-svelte` 7, Vite 8 and TypeScript 6. SvelteKit is configured in `vite.config.ts`, `$lib` imports became `#lib` imports, and the `cookie` dependency is updated (fixes the Dependabot security alerts).
- Minor and patch updates of backend (FastAPI, SQLAlchemy, cryptography) and frontend dependencies.
- Dependabot ignores major TypeScript updates until SvelteKit, svelte-check and typescript-eslint support TypeScript 7.

### Fixed

- Segmented controls give their labels more room: segments share an equal width sized by the widest label, and the active segment no longer clips its bold label.

## [0.1.0] - 2026-11-19

First public release.

### Added

- Bank sync via FinTS/HBCI with a built-in bank directory, TAN mechanism and TAN medium selection, app approval (decoupled TAN) and classic TAN entry. The PIN is never stored.
- CSV import with automatic detection for ING, Sparkasse, Volksbank/Raiffeisenbank, DKB, comdirect, Commerzbank, Deutsche Bank and N26, plus reusable column mappings for any other bank. Duplicates are detected across FinTS and CSV.
- Local categorization with a scikit-learn classifier that retrains on every correction, and optional fallback to a local language model via Ollama.
- Rules (contains, equals, starts with, regex) that take precedence over the classifier.
- Transaction detail view with all fields delivered by the bank, notes, category and budget month changes, and rule creation.
- Budget month: salary paid at the end of a month counts towards the following month.
- Multi-user households with shared or private accounts and 14 editable default main categories with subcategories.
- German and English user interface, light and dark mode, mobile layout.
- Prebuilt `linux/amd64` images on GHCR (`budgie-api`, `budgie-web`) and a Docker Compose setup for Traefik.

[Unreleased]: https://github.com/Jeansy91/budgie/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Jeansy91/budgie/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Jeansy91/budgie/releases/tag/v0.1.0

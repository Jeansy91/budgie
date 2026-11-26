# Changelog

All notable changes to Budgie are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the version is below 1.0.0, minor releases may contain breaking changes; they are called out in the release notes.

## [Unreleased]

### Added

- CI runs linters (ruff, mypy, prettier, eslint) and tests with coverage reports, and scans the container images with Trivy on every pull request and push.
- CodeQL, dependency review and OpenSSF Scorecard workflows, a CODEOWNERS file and pre-commit hooks.
- CI, CodeQL and OpenSSF Scorecard badges in the README and a "Security tooling" section in the security policy.

### Changed

- Backend dependencies are hash-locked with pip-compile (`requirements.in` and `requirements-dev.in` are the sources) and installed with `--require-hashes` in the Dockerfile and CI. The workflow is documented in the contributing guide.
- Docker base images are pinned by digest.
- CodeQL configuration moved to `.github/codeql/codeql-config.yml` and ignores the Alembic revision files, whose module variables are read by Alembic.
- IBANs are masked in log output.
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

[Unreleased]: https://github.com/Jeansy91/budgie/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Jeansy91/budgie/releases/tag/v0.1.0

# Changelog

All notable changes to Budgie are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the version is below 1.0.0, minor releases may contain breaking changes; they are called out in the release notes.

## [Unreleased]

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

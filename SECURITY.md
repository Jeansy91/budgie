# Security Policy

Budgie handles sensitive financial data, so security reports are taken seriously.

## Reporting a vulnerability

Please **do not** report security vulnerabilities through public GitHub issues, discussions or pull requests.

Instead, use GitHub's [private vulnerability reporting](https://github.com/Jeansy91/budgie/security/advisories/new) for this repository. Please include:

- a description of the issue and its impact,
- steps to reproduce or a proof of concept,
- the affected version (image tag or commit).

Never include real banking credentials or account data in a report.

You can expect an initial response within a few days. Once the issue is confirmed, a fix will be prepared and released, and you will be credited in the advisory unless you prefer otherwise.

## Supported versions

Only the latest release and the current `main` branch receive security fixes.

## How Budgie protects banking data

- **The online banking PIN is never stored**, neither in plain text nor encrypted. It is entered for every sync, kept in the memory of the API process only for the duration of that sync, and never logged.
- **TANs** are passed through to the bank and not stored.
- **Stored bank data** (login name, customer ID and the cached FinTS client state) is encrypted with Fernet (AES-128-CBC + HMAC-SHA256). The key is derived from `BUDGIE_SECRET_KEY`, which lives only in your environment and never in the database. A database backup alone does not reveal it.
- **Bank logins are personal:** other users in the same household can see synced accounts, but not the login used to sync them.
- **User passwords** are hashed with scrypt; only a hash of each session token is stored.
- **Everything runs locally.** Categorization uses a local classifier and, optionally, a local LLM via Ollama. No transaction data is sent to third-party services.
- The database and the optional Ollama service are attached to an internal Docker network without published ports.

## Security tooling

The repository is continuously checked with:

- **CodeQL** code scanning for Python, JavaScript/TypeScript and the GitHub Actions workflows.
- **Secret scanning with push protection**, plus gitleaks in the pre-commit hooks.
- **Dependabot** updates for Python and npm packages, Docker base images and GitHub Actions (which are pinned to commit SHAs).
- **Dependency review** on pull requests, which blocks newly introduced vulnerable dependencies.
- **Trivy** scans of the container images; fixable critical and high findings fail the build.
- **OpenSSF Scorecard** for overall supply-chain hygiene.

## Recommendations for operators

- Do not expose Budgie directly to the internet. Access it on your local network or through a VPN, behind a reverse proxy with TLS.
- Generate `BUDGIE_SECRET_KEY` with `openssl rand -base64 32`, keep it out of version control and back it up separately from the database.
- Use a long random `POSTGRES_PASSWORD`.
- Keep `BUDGIE_COOKIE_SECURE=true` whenever Budgie is served over HTTPS.
- Pin image versions with `BUDGIE_VERSION` and update regularly.

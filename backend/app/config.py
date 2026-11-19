from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BUDGIE_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://budgie:budgie@db:5432/budgie"
    # Session lifetime in days
    session_days: int = 30
    # Send the session cookie over HTTPS only. Set to false when serving without TLS.
    cookie_secure: bool = True
    # Maximum size of an uploaded CSV file in bytes
    max_upload_bytes: int = 10 * 1024 * 1024

    # Key used to encrypt stored FinTS credentials in the database.
    # Generate one with: openssl rand -base64 32
    secret_key: str = ""
    # FinTS product ID from the registration with the Deutsche Kreditwirtschaft
    fints_product_id: str = ""
    # How long a sync waits for a TAN or the approval in the banking app (seconds)
    fints_tan_timeout: int = 300
    # Optional path to the official FinTS institute list (fints_institute.csv) of the
    # Deutsche Kreditwirtschaft. Without it, Budgie uses its bundled bank directory.
    fints_institutes_file: str = ""

    # --- AI categorization (fully local) ---
    # Local classifier, learns from manual assignments and rules
    ai_enabled: bool = True
    # Minimum confidence (0–1) at which the AI assigns a category on its own
    ai_auto_threshold: float = 0.6
    # Minimum confidence at which the category is at least shown as a suggestion
    ai_suggest_threshold: float = 0.2
    # Optional language model via Ollama for uncertain cases. Empty = disabled.
    # Example inside the Docker Compose stack: http://ollama:11434
    ollama_url: str = ""
    ollama_model: str = "qwen2.5:7b"
    # Response timeout per transaction in seconds (CPU inference is slow)
    ollama_timeout: float = 180
    # Maximum number of transactions sent to the language model per run
    ollama_max_per_run: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()

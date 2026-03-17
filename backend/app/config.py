"""Application configuration via environment variables (12-factor compliant)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve paths relative to the backend directory
_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All configuration is read from environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required
    anthropic_api_key: str

    # Voice input (optional — falls back to browser SpeechRecognition)
    deepgram_api_key: str = ""

    # Voice output / TTS (Tier 2)
    cartesia_api_key: str = ""
    cartesia_voice_id: str = "2f251ac3-89a9-4a77-a452-704b474ccd01"

    # Paths
    database_path: str = str(_BACKEND_DIR / "data" / "frontdesk.db")
    handbook_pdf_path: str = str(_BACKEND_DIR / "data" / "handbook.pdf")
    handbook_index_path: str = str(_BACKEND_DIR / "data" / "handbook_index")

    # LLM
    claude_model: str = "claude-sonnet-4-20250514"

    # Logging
    log_level: str = "INFO"

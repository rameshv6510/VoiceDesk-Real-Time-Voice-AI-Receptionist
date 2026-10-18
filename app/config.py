"""Application configuration and settings."""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 7860
    ENVIRONMENT: str = "development"

    # Provider configurations
    STT_PROVIDER: str = "deepgram"
    TTS_PROVIDER: str = "deepgram"
    LLM_PROVIDER: str = "openai"

    # API Keys
    OPENAI_API_KEY: str = ""
    DEEPGRAM_API_KEY: str = ""
    SARVAM_API_KEY: str = ""
    CARTESIA_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # Models & Voice Configurations
    OPENAI_MODEL: str = "gpt-4o-mini"
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    DEEPGRAM_STT_MODEL: str = "nova-3"
    DEEPGRAM_STT_LANGUAGE: str = "multi"
    DEEPGRAM_TTS_VOICE: str = "aura-athena-en"
    SARVAM_TTS_VOICE: str = "kavya"
    SARVAM_TTS_MODEL: str = "bulbul:v3"
    SARVAM_TTS_LANGUAGE: str = "kn-IN"

    # Database
    DATABASE_URL: str = "sqlite:///./voice_desk.db"
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    CLINIC_CONFIG_PATH: str = "./config/clinic.yaml"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

def load_clinic_config() -> Dict[str, Any]:
    config_path = Path(settings.CLINIC_CONFIG_PATH)
    if not config_path.exists():
        # Fallback search
        config_path = Path(__file__).resolve().parent.parent / "config" / "clinic.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

clinic_config = load_clinic_config()

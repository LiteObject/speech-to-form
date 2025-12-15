"""
Application configuration settings.

Centralized configuration management using environment variables.
"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application configuration settings."""

    # AI Provider Configuration
    # Priority order: demo (regex - instant), ollama, openai
    # Use demo first for fastest parsing, AI providers as backup for complex cases
    AI_PROVIDER_PRIORITY: List[str] = [
        provider.strip()
        for provider in os.getenv("AI_PROVIDER_PRIORITY", "demo,ollama,openai").split(
            ","
        )
    ]

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "150"))

    # Ollama Configuration
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "30"))
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))
    OLLAMA_MAX_TOKENS: int = int(os.getenv("OLLAMA_MAX_TOKENS", "150"))

    # Local Whisper Configuration
    USE_WHISPER: bool = os.getenv("USE_WHISPER", "true").lower() == "true"
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base")
    WHISPER_LANGUAGE: str = os.getenv("WHISPER_LANGUAGE", "en")
    WHISPER_TASK: str = os.getenv(
        "WHISPER_TASK", "transcribe"
    )  # transcribe or translate

    # Application Configuration
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5000"))

    # Input Validation
    MAX_INPUT_LENGTH: int = int(os.getenv("MAX_INPUT_LENGTH", "2000"))

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_FILE: str = os.getenv("LOG_FILE", "speech_to_form.log")

    # Flask Configuration (using same as app config for consistency)
    FLASK_HOST: str = os.getenv("HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.getenv("PORT", "5000"))
    FLASK_DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Required form fields configuration
    REQUIRED_FIELDS = {
        "name": "Full Name",
        "email": "Email Address",
        "phone": "Phone Number",
        "address": "Address",
    }


# Global settings instance
settings = Settings()

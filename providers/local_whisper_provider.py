"""
Local Whisper provider implementation for speech-to-text transcription.

This module provides an adapter for OpenAI's Whisper model running locally,
implementing a clean interface for audio transcription.
"""

import logging
import tempfile
import os
from typing import Dict, Optional, Any

try:
    import whisper
except ImportError as e:
    raise ImportError(
        "openai-whisper package is required for LocalWhisperProvider"
    ) from e

from .base import AIProvider

logger = logging.getLogger(__name__)


class LocalWhisperProvider(AIProvider):
    """
    Local Whisper provider for speech-to-text transcription.

    Uses OpenAI's Whisper model running locally for high-quality
    speech transcription without external API calls.
    """

    def __init__(self, model_size: str = "base", **kwargs):
        """
        Initialize Local Whisper provider.

        Args:
            model_size (str): Whisper model size (tiny, base, small, medium, large)
                             - tiny: ~39 MB, fastest, lowest accuracy
                             - base: ~74 MB, good balance (recommended)
                             - small: ~244 MB, better accuracy
                             - medium: ~769 MB, high accuracy
                             - large: ~1550 MB, highest accuracy
            **kwargs: Additional configuration options
        """
        super().__init__(f"whisper-{model_size}", **kwargs)
        self.model_size = model_size
        self.model = None
        self._is_loaded = False

        # Configuration
        self.language = kwargs.get(
            "language", "en"
        )  # Language hint for better accuracy
        self.task = kwargs.get("task", "transcribe")  # transcribe or translate

        logger.info("Local Whisper provider initialized with model: %s", model_size)

    def _load_model(self) -> bool:
        """Load the Whisper model if not already loaded."""
        if self._is_loaded and self.model is not None:
            return True

        try:
            logger.info("Loading Whisper model: %s", self.model_size)
            self.model = whisper.load_model(self.model_size)
            self._is_loaded = True
            logger.info("Whisper model loaded successfully")
            return True
        except (RuntimeError, OSError, FileNotFoundError) as e:
            logger.error("Failed to load Whisper model: %s", str(e))
            self._is_loaded = False
            return False

    def transcribe_audio(self, audio_file_path: str) -> Optional[str]:
        """
        Transcribe audio file to text using local Whisper.

        Args:
            audio_file_path (str): Path to audio file

        Returns:
            Optional[str]: Transcribed text or None if transcription fails
        """
        if not self._load_model():
            logger.error("Whisper model not available")
            return None

        try:
            logger.info("Starting transcription of: %s", audio_file_path)

            # Transcribe with options
            result = self.model.transcribe(
                audio_file_path,
                language=self.language if self.language != "auto" else None,
                task=self.task,
                verbose=False,
            )

            transcribed_text = result["text"].strip()

            if transcribed_text:
                logger.info("Transcription successful: %s", transcribed_text[:100])
                return transcribed_text
            else:
                logger.warning("Transcription returned empty text")
                return None

        except FileNotFoundError as e:
            if "ffmpeg" in str(
                e
            ).lower() or "The system cannot find the file specified" in str(e):
                logger.error(
                    "FFmpeg not found. Please install FFmpeg to use Whisper audio transcription."
                )
                logger.error(
                    "Install FFmpeg: winget install 'FFmpeg (Essentials Build)'"
                )
            else:
                logger.error("File not found during transcription: %s", str(e))
            return None
        except (RuntimeError, ValueError, OSError) as e:
            logger.error("Transcription failed: %s", str(e), exc_info=True)
            return None

    def transcribe_from_bytes(
        self, audio_bytes: bytes, file_extension: str = "wav"
    ) -> Optional[str]:
        """
        Transcribe audio from bytes using a temporary file.

        Args:
            audio_bytes (bytes): Audio data as bytes
            file_extension (str): File extension (wav, mp3, etc.)

        Returns:
            Optional[str]: Transcribed text or None if transcription fails
        """
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f".{file_extension.lstrip('.')}"
            ) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_file_path = tmp_file.name

            # Transcribe and clean up
            try:
                result = self.transcribe_audio(tmp_file_path)
                return result
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)

        except (OSError, IOError, RuntimeError) as e:
            logger.error("Failed to transcribe from bytes: %s", str(e))
            return None

    def is_available(self) -> bool:
        """
        Check if Local Whisper is available.

        Returns:
            bool: True if Whisper can be loaded, False otherwise
        """
        try:
            return self._load_model()
        except (RuntimeError, ImportError) as e:
            logger.error("Whisper availability check failed: %s", str(e))
            return False

    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get provider information and status.

        Returns:
            Dict[str, Any]: Provider information including model details
        """
        return {
            "provider": "LocalWhisper",
            "model": f"whisper-{self.model_size}",
            "model_size": self.model_size,
            "language": self.language,
            "task": self.task,
            "available": self.is_available(),
            "status": "ready" if self.is_available() else "not_available",
            "description": f"Local Whisper {self.model_size} model for speech-to-text",
            "capabilities": {
                "transcription": True,
                "translation": True,
                "language_detection": True,
                "offline": True,
            },
            "model_info": {
                "tiny": "~39 MB, fastest, basic accuracy",
                "base": "~74 MB, balanced speed/accuracy",
                "small": "~244 MB, good accuracy",
                "medium": "~769 MB, high accuracy",
                "large": "~1550 MB, highest accuracy",
            }.get(self.model_size, f"Model size: {self.model_size}"),
        }

    def extract_information(
        self, user_input: str, prompt: Optional[str] = None
    ) -> Optional[Dict]:
        """
        This provider is for transcription only, not information extraction.

        Args:
            user_input (str): Not used - this provider handles audio files
            prompt (str): Not used

        Returns:
            None: This provider doesn't extract information from text
        """
        logger.warning(
            "LocalWhisperProvider is for audio transcription, not text extraction"
        )
        return None

    def get_supported_formats(self) -> list:
        """
        Get list of supported audio formats.

        Returns:
            list: Supported audio file formats
        """
        return [
            "wav",
            "mp3",
            "m4a",
            "ogg",
            "flac",
            "webm",
            "mp4",
            "mpeg",
            "mpga",
            "oga",
            "3gp",
        ]

    def get_model_sizes(self) -> Dict[str, str]:
        """
        Get available Whisper model sizes and descriptions.

        Returns:
            Dict[str, str]: Model sizes with descriptions
        """
        return {
            "tiny": "~39 MB - Fastest, basic accuracy",
            "base": "~74 MB - Balanced speed/accuracy (recommended)",
            "small": "~244 MB - Good accuracy",
            "medium": "~769 MB - High accuracy",
            "large": "~1550 MB - Highest accuracy",
        }

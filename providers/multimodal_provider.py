"""
Multimodal provider implementation for single-stage audio-to-fields extraction.

This module provides a single-stage approach where audio is sent directly to
a multimodal LLM that handles both transcription and field extraction in one step.

Supports:
- Cloud: OpenAI GPT-4o with audio input
- Local: Ollama/vLLM with audio-capable models (Qwen2-Audio, MiniCPM-O, etc.)
         or hybrid approach using local Whisper + local LLM
"""

import base64
import json
import os
from typing import Dict, Optional, Literal
import logging
import subprocess
import tempfile

try:
    import openai
except ImportError:
    openai = None

try:
    import requests
except ImportError:
    requests = None

from .base import AIProvider

logger = logging.getLogger(__name__)

# Extraction prompt shared across backends
EXTRACTION_PROMPT = """Listen to this audio and extract the following information.
Return a JSON object with these exact keys:
- transcript: The full transcription of what was said
- name: The person's full name (or null if not mentioned)
- email: The email address (or null if not mentioned)
- phone: The phone number (or null if not mentioned)
- address: The address (or null if not mentioned)

Convert speech patterns like "at" to "@" and "dot" to "." for emails.
Return ONLY valid JSON, no other text."""

TEXT_EXTRACTION_PROMPT = """Extract the following information from this text.
Return a JSON object with these exact keys:
- name: The person's full name (or null if not mentioned)
- email: The email address (or null if not mentioned)
- phone: The phone number (or null if not mentioned)
- address: The address (or null if not mentioned)

Convert speech patterns like "at" to "@" and "dot" to "." for emails.
Return ONLY valid JSON, no other text.

Text: {text}"""


class MultimodalProvider(AIProvider):
    """
    Multimodal provider for single-stage audio processing.

    Supports multiple backends:
    - 'openai': GPT-4o with native audio support (cloud)
    - 'ollama': Local Ollama models with Whisper + LLM (hybrid local)
    - 'vllm': vLLM with audio-capable models like Ultravox (local)
    """

    def __init__(
        self,
        model_name: str = "gpt-4o-audio-preview",
        backend: Literal["openai", "ollama", "vllm"] = "openai",
        **kwargs
    ):
        """
        Initialize Multimodal provider.

        Args:
            model_name (str): Model name (default: gpt-4o-audio-preview for OpenAI)
            backend (str): Backend to use - 'openai', 'ollama', or 'vllm'
            **kwargs: Additional configuration options
        """
        super().__init__(model_name, **kwargs)
        self.backend = backend
        self.api_key = kwargs.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.ollama_url = kwargs.get("ollama_url") or os.getenv(
            "OLLAMA_URL", "http://localhost:11434"
        )
        self.vllm_url = kwargs.get("vllm_url") or os.getenv(
            "VLLM_URL", "http://localhost:8000"
        )
        self.ollama_model = kwargs.get("ollama_model") or os.getenv(
            "OLLAMA_MODEL", "gpt-oss:20b"
        )

        # Initialize clients based on backend
        self._openai_client = None
        self._whisper_model = None

        if backend == "openai":
            self._init_openai_client()
        elif backend == "ollama":
            self._init_ollama()
        elif backend == "vllm":
            self._init_vllm()

    def _init_openai_client(self):
        """Initialize OpenAI client for cloud backend."""
        if self.api_key and self.api_key != "your-actual-openai-api-key-here":
            if openai is None:
                logger.error("OpenAI library not installed. Run: pip install openai")
            else:
                try:
                    self._openai_client = openai.OpenAI(api_key=self.api_key)
                    logger.info("Multimodal OpenAI client initialized successfully")
                except (ValueError, TypeError, RuntimeError) as e:
                    logger.error("Failed to initialize OpenAI client: %s", e)

    def _init_ollama(self):
        """Initialize Ollama backend with local Whisper."""
        try:
            # Lazy load whisper for local transcription
            import whisper

            self._whisper_model = whisper.load_model("base")
            logger.info("Ollama multimodal initialized with local Whisper + Ollama LLM")
        except ImportError:
            logger.warning(
                "Whisper not available - install with: pip install openai-whisper"
            )
        except Exception as e:
            logger.error("Failed to load Whisper model: %s", e)

    def _init_vllm(self):
        """Initialize vLLM backend."""
        # vLLM uses OpenAI-compatible API
        logger.info("vLLM multimodal initialized at %s", self.vllm_url)

    def extract_from_audio(self, audio_path: str) -> Optional[Dict]:
        """
        Extract form fields directly from audio file.

        Routes to appropriate backend based on configuration.

        Args:
            audio_path (str): Path to the audio file

        Returns:
            Optional[Dict]: Dictionary with 'transcript' and 'form_data' keys
        """
        if not self.is_available():
            logger.warning("Multimodal provider not available (backend: %s)", self.backend)
            return None

        if self.backend == "openai":
            return self._extract_with_openai(audio_path)
        elif self.backend == "ollama":
            return self._extract_with_ollama(audio_path)
        elif self.backend == "vllm":
            return self._extract_with_vllm(audio_path)
        else:
            logger.error("Unknown backend: %s", self.backend)
            return None

    def _extract_with_openai(self, audio_path: str) -> Optional[Dict]:
        """Extract using OpenAI GPT-4o with native audio support."""
        try:
            with open(audio_path, "rb") as audio_file:
                audio_data = audio_file.read()

            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
            ext = audio_path.rsplit(".", 1)[-1].lower()

            logger.info("Sending audio to OpenAI multimodal model: %s", self.model_name)

            response = self._openai_client.chat.completions.create(
                model=self.model_name,
                modalities=["text"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": EXTRACTION_PROMPT},
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": audio_base64,
                                    "format": ext if ext in ["wav", "mp3"] else "wav",
                                },
                            },
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=500,
            )

            return self._parse_response(response.choices[0].message.content.strip())

        except Exception as e:
            logger.error("OpenAI multimodal extraction error: %s", e)
            return None

    def _extract_with_ollama(self, audio_path: str) -> Optional[Dict]:
        """Extract using local Whisper + Ollama LLM (hybrid local approach)."""
        try:
            # Step 1: Transcribe with local Whisper
            logger.info("Transcribing audio with local Whisper...")
            result = self._whisper_model.transcribe(audio_path)
            transcript = result.get("text", "").strip()
            logger.info("Whisper transcription: %s", transcript[:100])

            if not transcript:
                logger.warning("Empty transcription from Whisper")
                return None

            # Step 2: Extract fields with Ollama
            logger.info("Extracting fields with Ollama model: %s", self.ollama_model)

            prompt = TEXT_EXTRACTION_PROMPT.format(text=transcript)

            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=60,
            )
            response.raise_for_status()

            response_text = response.json().get("response", "").strip()
            result = self._parse_json_response(response_text)

            if result:
                result["transcript"] = transcript
                return result

            # If JSON parsing failed, try to extract with regex as fallback
            logger.warning("Ollama JSON parse failed, returning transcript only")
            return {
                "transcript": transcript,
                "form_data": {},
                "missing_fields": ["name", "email", "phone", "address"],
            }

        except Exception as e:
            logger.error("Ollama multimodal extraction error: %s", e)
            return None

    def _extract_with_vllm(self, audio_path: str) -> Optional[Dict]:
        """Extract using vLLM with audio-capable model (e.g., Ultravox)."""
        try:
            with open(audio_path, "rb") as audio_file:
                audio_data = audio_file.read()

            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
            ext = audio_path.rsplit(".", 1)[-1].lower()

            logger.info("Sending audio to vLLM model: %s", self.model_name)

            # vLLM uses OpenAI-compatible API
            response = requests.post(
                f"{self.vllm_url}/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": EXTRACTION_PROMPT},
                                {
                                    "type": "audio_url",
                                    "audio_url": {
                                        "url": f"data:audio/{ext};base64,{audio_base64}"
                                    },
                                },
                            ],
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500,
                },
                timeout=120,
            )
            response.raise_for_status()

            response_text = response.json()["choices"][0]["message"]["content"].strip()
            return self._parse_response(response_text)

        except Exception as e:
            logger.error("vLLM multimodal extraction error: %s", e)
            return None

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse JSON response from model."""
        result = self._parse_json_response(response_text)
        if not result:
            return None

        transcript = result.get("transcript", "")
        form_data = {
            "name": result.get("name"),
            "email": result.get("email"),
            "phone": result.get("phone"),
            "address": result.get("address"),
        }

        # Remove None values
        form_data = {k: v for k, v in form_data.items() if v}

        logger.info("Multimodal extraction successful: %s", form_data)

        return {
            "transcript": transcript,
            "form_data": form_data,
            "missing_fields": [
                f for f in ["name", "email", "phone", "address"] if f not in form_data
            ],
        }

    def _parse_json_response(self, response_text: str) -> Optional[Dict]:
        """Parse JSON from response, handling markdown code blocks."""
        try:
            logger.info("Parsing response: %s", response_text[:200])

            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", e)
            return None

    def extract_information(
        self, user_input: str, prompt: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Extract information from text (falls back to standard extraction).

        For multimodal, use extract_from_audio() instead.
        This method is here for interface compatibility.
        """
        logger.warning(
            "Multimodal provider called with text - use extract_from_audio for audio"
        )
        return None

    def is_available(self) -> bool:
        """Check if the multimodal provider is available."""
        if self.backend == "openai":
            return self._openai_client is not None
        elif self.backend == "ollama":
            return self._whisper_model is not None
        elif self.backend == "vllm":
            # Check if vLLM server is reachable
            try:
                response = requests.get(f"{self.vllm_url}/health", timeout=5)
                return response.status_code == 200
            except Exception:
                return False
        return False

    def get_provider_info(self) -> Dict:
        """Get multimodal provider information."""
        backend_desc = {
            "openai": "GPT-4o with native audio support (cloud)",
            "ollama": "Local Whisper + Ollama LLM (local)",
            "vllm": "vLLM with audio-capable model (local)",
        }
        return {
            "provider": "Multimodal",
            "model": self.model_name,
            "backend": self.backend,
            "available": self.is_available(),
            "type": "single-stage",
            "description": backend_desc.get(self.backend, "Unknown backend"),
        }

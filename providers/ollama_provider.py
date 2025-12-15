"""
Ollama provider implementation using the Adapter pattern.

This module provides an adapter for Ollama's local API, implementing the common
AIProvider interface for consistent integration.
"""

import json
import os
from typing import Dict, Optional
import logging

try:
    import requests
except ImportError as e:
    raise ImportError("requests library is required for Ollama provider") from e

from .base import AIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
    """
    Ollama provider implementation.

    Provides access to local Ollama models through a consistent interface.
    """

    def __init__(self, model_name: str = "gpt-oss:20b", **kwargs):
        """
        Initialize Ollama provider.

        Args:
            model_name (str): Ollama model to use (default: gpt-oss:20b)
            **kwargs: Additional configuration options
        """
        super().__init__(model_name, **kwargs)
        self.base_url = kwargs.get("base_url") or os.getenv(
            "OLLAMA_URL", "http://localhost:11434"
        )
        self.timeout = kwargs.get("timeout", 30)

        logger.info("Ollama provider initialized with URL: %s", self.base_url)

    def extract_information(
        self, user_input: str, prompt: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Extract information using Ollama's API.

        Args:
            user_input (str): Raw text input from the user
            prompt (str): Optional custom prompt (uses default if None)

        Returns:
            Optional[Dict]: Extracted information or None if extraction fails
        """
        if not self.is_available():
            logger.warning("Ollama provider not available")
            return None

        if prompt is None:
            prompt = self.get_extraction_prompt(user_input)

        logger.info("Starting Ollama extraction with model: %s", self.model_name)

        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": self.config.get("temperature", 0.1),
                    "num_predict": self.config.get("max_tokens", 150),
                },
            }

            response = requests.post(
                f"{self.base_url}/api/generate", json=payload, timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "").strip()

                if response_text:
                    # Try to parse JSON response
                    try:
                        extracted_data = json.loads(response_text)
                        logger.info("Ollama extraction successful")
                        return extracted_data
                    except json.JSONDecodeError as e:
                        logger.error("Invalid JSON from Ollama: %s", e)
                        logger.debug("Raw response: %s", response_text)
                        return None
                else:
                    logger.error("Empty response from Ollama")
                    return None
            else:
                logger.error("Ollama API error: Status %s", response.status_code)
                return None

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama at %s", self.base_url)
            return None
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out after %s seconds", self.timeout)
            return None
        except (
            requests.exceptions.RequestException,
            json.JSONDecodeError,
            KeyError,
        ) as e:
            logger.error("Ollama extraction error: %s", e)
            return None

    def is_available(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            # Check if Ollama is running
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                # Check if our model is available
                models = response.json().get("models", [])
                available_models = [model["name"] for model in models]
                return self.model_name in available_models
            return False
        except (requests.exceptions.RequestException, ConnectionError, TimeoutError):
            return False

    def get_provider_info(self) -> Dict:
        """Get Ollama provider information."""
        info = {
            "provider": "Ollama",
            "model": self.model_name,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "available": False,
            "status": "unknown",
        }

        try:
            # Check Ollama service status
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models_data = response.json().get("models", [])
                available_models = [model["name"] for model in models_data]

                info.update(
                    {
                        "available": self.model_name in available_models,
                        "status": "running",
                        "available_models": available_models,
                        "model_available": self.model_name in available_models,
                    }
                )

                # Get specific model info if available
                for model in models_data:
                    if model["name"] == self.model_name:
                        info["model_info"] = {
                            "size": model.get("size", "unknown"),
                            "modified_at": model.get("modified_at", "unknown"),
                        }
                        break
            else:
                info["status"] = f"error: HTTP {response.status_code}"

        except requests.exceptions.ConnectionError:
            info["status"] = "not_running"
        except requests.exceptions.Timeout:
            info["status"] = "timeout"
        except (requests.exceptions.RequestException, KeyError) as e:
            info["status"] = f"error: {str(e)}"

        return info

    def pull_model(self) -> bool:
        """
        Pull the model if it's not available locally.

        Returns:
            bool: True if model was pulled successfully, False otherwise
        """
        try:
            logger.info("Attempting to pull model: %s", self.model_name)

            payload = {"name": self.model_name}
            response = requests.post(
                f"{self.base_url}/api/pull",
                json=payload,
                timeout=300,  # 5 minute timeout for model pulling
            )

            if response.status_code == 200:
                logger.info("Model %s pulled successfully", self.model_name)
                return True
            else:
                logger.error(
                    "Failed to pull model %s: HTTP %s",
                    self.model_name,
                    response.status_code,
                )
                return False

        except (
            requests.exceptions.RequestException,
            ConnectionError,
            TimeoutError,
        ) as e:
            logger.error("Error pulling model %s: %s", self.model_name, e)
            return False

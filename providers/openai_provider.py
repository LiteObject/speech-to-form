"""
OpenAI provider implementation using the Adapter pattern.

This module provides an adapter for OpenAI's API, implementing the common
AIProvider interface for consistent integration.
"""

import json
import os
from typing import Dict, Optional
import logging

try:
    import openai
except ImportError:
    openai = None

from .base import AIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """
    OpenAI provider implementation.

    Provides access to OpenAI's GPT models through a consistent interface.
    """

    def __init__(self, model_name: str = "gpt-4o-mini", **kwargs):
        """
        Initialize OpenAI provider.

        Args:
            model_name (str): OpenAI model to use (default: gpt-4o-mini)
            **kwargs: Additional configuration options
        """
        super().__init__(model_name, **kwargs)
        self.api_key = kwargs.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.fallback_models = kwargs.get(
            "fallback_models", ["gpt-4o-mini", "gpt-3.5-turbo"]
        )

        # Initialize OpenAI client
        self._client = None
        if self.api_key and self.api_key != "your-actual-openai-api-key-here":
            if openai is None:
                logger.error("OpenAI library not installed. Run: pip install openai")
            else:
                try:
                    self._client = openai.OpenAI(api_key=self.api_key)
                    logger.info("OpenAI client initialized successfully")
                except (ValueError, TypeError, RuntimeError) as e:
                    logger.error("Failed to initialize OpenAI client: %s", e)

    def extract_information(
        self, user_input: str, prompt: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Extract information using OpenAI's API.

        Args:
            user_input (str): Raw text input from the user
            prompt (str): Optional custom prompt (uses default if None)

        Returns:
            Optional[Dict]: Extracted information or None if extraction fails
        """
        if not self.is_available():
            logger.warning("OpenAI provider not available")
            return None

        if prompt is None:
            prompt = self.get_extraction_prompt(user_input)

        logger.info("Starting OpenAI extraction with model: %s", self.model_name)

        # Try primary model first, then fallbacks
        models_to_try = [self.model_name] + [
            m for m in self.fallback_models if m != self.model_name
        ]

        for model in models_to_try:
            try:
                logger.debug("Attempting extraction with model: %s", model)

                if not self._client:
                    logger.error("OpenAI client not initialized")
                    continue

                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful assistant that extracts "
                                "structured information from natural language "
                                "and returns it as valid JSON. Only return the "
                                "JSON object, no additional text or formatting."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.config.get("temperature", 0.1),
                    max_tokens=self.config.get("max_tokens", 150),
                    response_format={"type": "json_object"},
                )

                response_text = response.choices[0].message.content
                if response_text:
                    response_text = response_text.strip()

                    # Handle potential markdown formatting
                    if response_text.startswith("```json"):
                        response_text = (
                            response_text.replace("```json", "")
                            .replace("```", "")
                            .strip()
                        )
                    elif response_text.startswith("```"):
                        response_text = response_text.replace("```", "").strip()

                    extracted_data = json.loads(response_text)
                    logger.info("OpenAI extraction successful with model: %s", model)
                    return extracted_data

            except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as e:
                logger.warning("Model %s failed: %s", model, e)
                if model == models_to_try[-1]:
                    logger.error("All OpenAI models failed. Last error: %s", e)
                continue

        return None

    def is_available(self) -> bool:
        """Check if OpenAI provider is available."""
        return bool(
            self._client is not None
            and self.api_key
            and self.api_key != "your-actual-openai-api-key-here"
        )

    def get_provider_info(self) -> Dict:
        """Get OpenAI provider information."""
        info = {
            "provider": "OpenAI",
            "model": self.model_name,
            "fallback_models": self.fallback_models,
            "available": self.is_available(),
            "api_key_configured": bool(
                self.api_key and self.api_key != "your-actual-openai-api-key-here"
            ),
        }

        # Test connectivity if available
        if self.is_available() and self._client:
            try:
                # Simple test call
                test_response = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": "Say 'OK'"}],
                    max_tokens=5,
                )
                info["status"] = "connected"
                info["test_response"] = test_response.choices[0].message.content
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                info["status"] = f"error: {str(e)}"
        else:
            info["status"] = "not_configured"

        return info

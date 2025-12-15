"""
AI Provider Factory using the Factory pattern.

This module implements the Factory pattern to create appropriate AI provider instances
based on configuration, enabling easy swapping between different AI services.
"""

import os
from typing import Dict, List, Optional, Type
import logging

from .base import AIProvider
from .openai_provider import OpenAIProvider
from .ollama_provider import OllamaProvider
from .demo_provider import DemoProvider

try:
    from config import settings
except ImportError:
    settings = None

logger = logging.getLogger(__name__)


class AIProviderFactory:
    """
    Factory class for creating AI provider instances.

    This class implements the Factory pattern to instantiate the appropriate
    AI provider based on configuration and availability.
    """

    # Registry of available providers
    _providers: Dict[str, Type[AIProvider]] = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
        "demo": DemoProvider,
        "regex": DemoProvider,  # Alias for demo
        "fallback": DemoProvider,  # Alias for demo
    }

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[AIProvider]) -> None:
        """
        Register a new provider type.

        Args:
            name (str): Name identifier for the provider
            provider_class (Type[AIProvider]): Provider class that implements AIProvider interface
        """
        cls._providers[name.lower()] = provider_class
        logger.info("Registered new provider: %s -> %s", name, provider_class.__name__)

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of registered provider names.

        Returns:
            List[str]: List of available provider names
        """
        return list(cls._providers.keys())

    @classmethod
    def create_provider(
        cls, provider_type: str, model_name: Optional[str] = None, **kwargs
    ) -> AIProvider:
        """
        Create an AI provider instance.

        Args:
            provider_type (str): Type of provider to create ('openai', 'ollama', 'demo')
            model_name (str, optional): Model name to use
            **kwargs: Additional configuration for the provider

        Returns:
            AIProvider: Configured provider instance

        Raises:
            ValueError: If provider_type is not supported
        """
        provider_type = provider_type.lower()

        if provider_type not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unsupported provider type '{provider_type}'. Available: {available}"
            )

        provider_class = cls._providers[provider_type]

        # Set default model names if not provided
        if model_name is None:
            model_name = cls._get_default_model(provider_type)

        logger.info("Creating %s provider with model: %s", provider_type, model_name)

        try:
            provider = provider_class(model_name=model_name, **kwargs)
            logger.info("Successfully created %s provider", provider_type)
            return provider
        except Exception as e:
            logger.error("Failed to create %s provider: %s", provider_type, e)
            raise

    @classmethod
    def create_from_config(cls, config: Optional[Dict] = None) -> AIProvider:
        """
        Create a provider based on configuration priority.

        Args:
            config (Dict, optional): Configuration dictionary

        Returns:
            AIProvider: Best available provider instance
        """
        if config is None:
            config = cls._load_config_from_env()

        # Define provider priority order
        priority_order = config.get("priority", ["ollama", "openai", "demo"])

        logger.info(
            "Attempting to create provider with priority order: %s", priority_order
        )

        for provider_type in priority_order:
            try:
                provider = cls.create_provider(
                    provider_type=provider_type,
                    model_name=config.get(f"{provider_type}_model"),
                    **config.get(f"{provider_type}_config", {}),
                )

                # Check if provider is actually available
                if provider.is_available():
                    logger.info(
                        "Successfully created and verified %s provider", provider_type
                    )
                    return provider
                else:
                    logger.warning(
                        "%s provider created but not available, trying next",
                        provider_type,
                    )

            except (ImportError, ValueError, RuntimeError, TypeError) as e:
                logger.warning(
                    "Failed to create %s provider: %s, trying next", provider_type, e
                )
                continue

        # Fallback to demo provider if all others fail
        logger.warning("All configured providers failed, falling back to demo provider")
        return cls.create_provider("demo")

    @classmethod
    def create_chain(cls, provider_types: List[str], **kwargs) -> List[AIProvider]:
        """
        Create a chain of providers for fallback processing.

        Args:
            provider_types (List[str]): List of provider types in order of preference
            **kwargs: Common configuration for all providers

        Returns:
            List[AIProvider]: List of provider instances
        """
        providers = []

        for provider_type in provider_types:
            try:
                provider = cls.create_provider(provider_type, **kwargs)
                providers.append(provider)
                logger.info("Added %s to provider chain", provider_type)
            except (ImportError, ValueError, RuntimeError, TypeError) as e:
                logger.warning("Failed to add %s to chain: %s", provider_type, e)

        return providers

    @classmethod
    def _get_default_model(cls, provider_type: str) -> str:
        """Get default model name for a provider type."""
        defaults = {
            "openai": "gpt-4o-mini",
            "ollama": "gpt-oss:20b",
            "demo": "regex-patterns",
        }
        return defaults.get(provider_type, "default")

    @classmethod
    def _load_config_from_env(cls) -> Dict:
        """Load configuration from environment variables."""
        if settings is not None:
            config = {
                "priority": settings.AI_PROVIDER_PRIORITY,
                # OpenAI configuration
                "openai_model": settings.OPENAI_MODEL,
                "openai_config": {
                    "api_key": settings.OPENAI_API_KEY,
                    "temperature": settings.OPENAI_TEMPERATURE,
                    "max_tokens": settings.OPENAI_MAX_TOKENS,
                },
                # Ollama configuration
                "ollama_model": settings.OLLAMA_MODEL,
                "ollama_config": {
                    "base_url": settings.OLLAMA_URL,
                    "timeout": settings.OLLAMA_TIMEOUT,
                    "temperature": settings.OLLAMA_TEMPERATURE,
                    "max_tokens": settings.OLLAMA_MAX_TOKENS,
                },
                # Demo configuration
                "demo_config": {},
            }
        else:
            # Fallback to direct environment variable access
            config = {
                "priority": os.getenv(
                    "AI_PROVIDER_PRIORITY", "ollama,openai,demo"
                ).split(","),
                # OpenAI configuration
                "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "openai_config": {
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.1")),
                    "max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", "150")),
                },
                # Ollama configuration
                "ollama_model": os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
                "ollama_config": {
                    "base_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
                    "timeout": int(os.getenv("OLLAMA_TIMEOUT", "30")),
                    "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.1")),
                    "max_tokens": int(os.getenv("OLLAMA_MAX_TOKENS", "150")),
                },
                # Demo configuration
                "demo_config": {},
            }

        return config


class ProviderChain:
    """
    A chain of AI providers that tries each one in sequence until one succeeds.

    This class provides a convenient way to use multiple providers with automatic fallback.
    """

    def __init__(self, providers: List[AIProvider]):
        """
        Initialize provider chain.

        Args:
            providers (List[AIProvider]): List of providers in order of preference
        """
        self.providers = providers
        logger.info("Created provider chain with %d providers", len(providers))

    def extract_information(
        self, user_input: str, prompt: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Extract information using the provider chain.

        Tries each provider in sequence until one succeeds or all fail.

        Args:
            user_input (str): Raw text input from the user
            prompt (str, optional): Custom prompt to use

        Returns:
            Optional[Dict]: Extracted information or None if all providers fail
        """
        for i, provider in enumerate(self.providers):
            try:
                logger.info(
                    "Trying provider %d: %s", i + 1, provider.__class__.__name__
                )

                if not provider.is_available():
                    logger.warning(
                        "Provider %s not available, skipping",
                        provider.__class__.__name__,
                    )
                    continue

                result = provider.extract_information(user_input, prompt)
                if result:
                    logger.info(
                        "Successfully extracted with %s", provider.__class__.__name__
                    )
                    return result
                else:
                    logger.warning(
                        "Provider %s returned no results", provider.__class__.__name__
                    )

            except (AttributeError, ValueError, RuntimeError, TypeError) as e:
                logger.error(
                    "Provider %s failed with error: %s", provider.__class__.__name__, e
                )
                continue

        logger.error("All providers in chain failed")
        return None

    def get_chain_status(self) -> List[Dict]:
        """
        Get status of all providers in the chain.

        Returns:
            List[Dict]: Status information for each provider
        """
        return [provider.get_provider_info() for provider in self.providers]

"""
Abstract base class for AI providers using the Adapter pattern.

This module defines the common interface that all AI providers must implement,
ensuring consistent behavior across different AI services.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    This class defines the interface that all AI providers must implement,
    following the Adapter pattern to ensure consistent behavior.
    """

    def __init__(self, model_name: str, **kwargs):
        """
        Initialize the AI provider.

        Args:
            model_name (str): Name of the model to use
            **kwargs: Additional provider-specific configuration
        """
        self.model_name = model_name
        self.config = kwargs
        logger.info(
            "Initializing %s with model: %s", self.__class__.__name__, model_name
        )

    @abstractmethod
    def extract_information(
        self, user_input: str, prompt: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Extract structured information from user input.

        Args:
            user_input (str): Raw text input from the user
            prompt (str): Optional formatted prompt for the AI model

        Returns:
            Optional[Dict]: Extracted information as a dictionary, or None if extraction fails
        """
        raise NotImplementedError(
            "Subclasses must implement extract_information method"
        )

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available and properly configured.

        Returns:
            bool: True if the provider is available, False otherwise
        """
        raise NotImplementedError("Subclasses must implement is_available method")

    @abstractmethod
    def get_provider_info(self) -> Dict:
        """
        Get information about the provider and its status.

        Returns:
            Dict: Provider information including status, model, etc.
        """
        raise NotImplementedError("Subclasses must implement get_provider_info method")

    def get_extraction_prompt(self, user_input: str) -> str:
        """
        Generate a standardized prompt for information extraction.

        Args:
            user_input (str): Raw text input from the user

        Returns:
            str: Formatted prompt for the AI model
        """
        return f"""
        Extract the following information from the user's input and return as a JSON object:
        - name: full name (string)
        - email: email address (string)
        - phone: phone number (string)
        - address: full address (string)

        User input: "{user_input}"

        Return a JSON object with only the fields that are mentioned. If a field is not mentioned, do not include it in the response.

        Example response format: {{"name": "John Doe", "email": "john@example.com"}}
        """

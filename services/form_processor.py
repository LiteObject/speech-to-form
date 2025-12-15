"""
Business logic services for form processing.

This module contains the core business logic separated from HTTP concerns.
"""

import logging
from typing import Dict, List, Optional, Any

from providers import AIProviderFactory, ProviderChain
from schemas import form_schema
from config import settings

logger = logging.getLogger(__name__)


class FormProcessor:
    """
    Service class for processing and managing form data extraction.

    This class handles the extraction of structured information from user input,
    tracks form completion status, and manages missing field detection.
    """

    def __init__(self):
        """Initialize the FormProcessor with empty form data and create provider chain."""
        self.form_data: Dict[str, str] = {}
        self.missing_fields: List[str] = form_schema.get_required_fields()
        self.provider_chain: ProviderChain = self._create_provider_chain()

        logger.info(
            "FormProcessor initialized with required fields: %s", self.missing_fields
        )
        logger.info(
            "Provider chain status: %s",
            [p.get_provider_info()["provider"] for p in self.provider_chain.providers],
        )

    def _create_provider_chain(self) -> ProviderChain:
        """
        Create a chain of AI providers based on configuration.

        Returns:
            ProviderChain: Configured chain of providers
        """
        try:
            providers = []
            for provider_type in settings.AI_PROVIDER_PRIORITY:
                provider_type = provider_type.strip()
                try:
                    provider = AIProviderFactory.create_provider(provider_type)
                    providers.append(provider)
                    logger.info("Added %s provider to chain", provider_type)
                except (ImportError, ValueError, RuntimeError, TypeError) as e:
                    logger.warning("Failed to create %s provider: %s", provider_type, e)

            # Ensure we always have at least the demo provider
            if not providers:
                logger.warning(
                    "No providers available, adding demo provider as fallback"
                )
                providers.append(AIProviderFactory.create_provider("demo"))

            return ProviderChain(providers)

        except (ImportError, ValueError, RuntimeError) as e:
            logger.error("Error creating provider chain: %s", e)
            # Fallback to demo provider only
            demo_provider = AIProviderFactory.create_provider("demo")
            return ProviderChain([demo_provider])

    def process_input(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input and return comprehensive result.

        Args:
            user_input (str): Raw text input from the user

        Returns:
            Dict[str, Any]: Processing result with form data, status, and messages
        """
        logger.info("Processing user input: %s", user_input[:100])

        # Extract information from input
        extracted_data = self.extract_information(user_input)

        # Update form data if extraction was successful
        if extracted_data:
            self.update_form_data(extracted_data)

        # Generate response
        result = {
            "form_data": self.form_data.copy(),
            "missing_fields": self.missing_fields.copy(),
            "is_complete": self.is_complete(),
            "completion_percentage": self._get_completion_percentage(),
            "extraction_method": self.get_extraction_method_used(),
            "extracted_this_time": extracted_data,
        }

        # Add appropriate message
        if self.is_complete():
            result["message"] = "Great! All required information has been collected."
        else:
            missing_msg = self.get_missing_fields_message()
            if extracted_data:
                result["message"] = (
                    f"Thank you! {missing_msg}"
                    if missing_msg
                    else "Information updated."
                )
            else:
                result["message"] = (
                    "I couldn't extract any form information from your input. "
                    f"{missing_msg if missing_msg else 'Please try again.'}"
                )

        return result

    def _get_completion_percentage(self) -> float:
        """Calculate form completion percentage."""
        total_fields = len(form_schema.get_required_fields())
        completed_fields = total_fields - len(self.missing_fields)
        return (
            round((completed_fields / total_fields) * 100, 1)
            if total_fields > 0
            else 0.0
        )

    def extract_information(self, user_input: str) -> Dict[str, str]:
        """
        Extract structured information from user input using the provider chain.

        Args:
            user_input (str): Raw text input from the user containing form information

        Returns:
            Dict[str, str]: Dictionary containing extracted field values
        """
        logger.info("Starting information extraction for input: '%s'", user_input)

        try:
            # Use the provider chain to extract information
            extracted_data = self.provider_chain.extract_information(user_input)

            if extracted_data:
                logger.info("Successfully extracted data: %s", extracted_data)
                return extracted_data
            else:
                logger.warning("No data extracted from any provider")
                return {}

        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Error during extraction: %s", e, exc_info=True)
            return {}

    def get_extraction_method_used(self) -> str:
        """
        Get the name of the last successful extraction method.

        Returns:
            str: Name of the extraction method used
        """
        # Check which providers are available and return the first available one
        for provider in self.provider_chain.providers:
            if provider.is_available():
                return provider.get_provider_info()["provider"]

        return "Demo"  # Fallback

    def update_form_data(self, extracted_data: Dict[str, str]) -> None:
        """
        Update the internal form data with newly extracted information.

        This method validates, normalizes, and merges extracted field values
        into the existing form data.

        Args:
            extracted_data (Dict[str, str]): Dictionary containing extracted field values
        """
        logger.info("Updating form data with: %s", extracted_data)
        logger.debug("Current form data before update: %s", self.form_data)
        logger.debug("Missing fields before update: %s", self.missing_fields)

        # Validate and normalize the extracted data
        validated_data = form_schema.validate_data(extracted_data)

        for field, value in validated_data.items():
            if field in form_schema.get_required_fields() and value:
                old_value = self.form_data.get(field)
                self.form_data[field] = value
                if field in self.missing_fields:
                    self.missing_fields.remove(field)
                    logger.info(
                        "Field '%s' filled with value: '%s' (was missing)", field, value
                    )
                else:
                    logger.info(
                        "Field '%s' updated from '%s' to '%s'", field, old_value, value
                    )

        logger.info("Form data after update: %s", self.form_data)
        logger.info("Missing fields after update: %s", self.missing_fields)

    def get_missing_fields_message(self) -> Optional[str]:
        """
        Generate a user-friendly message requesting missing form information.

        Returns:
            Optional[str]: Formatted message requesting missing fields,
                          or None if form is complete
        """
        if not self.missing_fields:
            return None

        field_labels = form_schema.get_field_labels()
        missing_labels = [field_labels[field] for field in self.missing_fields]

        if len(missing_labels) == 1:
            return f"I still need your {missing_labels[0]}. Please provide it."
        elif len(missing_labels) == 2:
            return (
                f"I still need your {missing_labels[0]} and "
                f"{missing_labels[1]}. Please provide them."
            )
        else:
            return (
                f"I still need your {', '.join(missing_labels[:-1])}, "
                f"and {missing_labels[-1]}. Please provide them."
            )

    def is_complete(self) -> bool:
        """
        Check if all required form fields have been filled.

        Returns:
            bool: True if all required fields are complete, False otherwise
        """
        return len(self.missing_fields) == 0

    def reset(self) -> None:
        """Reset the form processor to initial state."""
        self.form_data = {}
        self.missing_fields = form_schema.get_required_fields()
        logger.info("Form processor reset successfully")

    def get_provider_chain_status(self) -> List[Dict]:
        """
        Get status of all providers in the chain.

        Returns:
            List[Dict]: Status information for each provider
        """
        return self.provider_chain.get_chain_status()

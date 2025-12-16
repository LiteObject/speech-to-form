"""
Business logic services for form processing.

This module contains the core business logic separated from HTTP concerns.
"""

import logging
from typing import Dict, List, Optional, Any

from providers import AIProviderFactory, ProviderChain
from schemas import form_schema
from config import settings
from .pattern_cache import pattern_cache
from .confidence_scorer import ConfidenceScorer

logger = logging.getLogger(__name__)


class FormProcessor:
    """
    Service class for processing and managing form data extraction.

    This class handles the extraction of structured information from user input,
    tracks form completion status, and manages missing field detection.

    Enhanced features:
    - Pattern caching for faster repeat extractions
    - Confidence scoring for extracted values
    - Context-aware extraction using filled fields
    """

    # Minimum confidence threshold for auto-accepting values
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(self):
        """Initialize the FormProcessor with empty form data and create provider chain."""
        self.form_data: Dict[str, str] = {}
        self.field_confidence: Dict[str, float] = {}  # Confidence scores per field
        self.missing_fields: List[str] = form_schema.get_required_fields()
        self.provider_chain: ProviderChain = self._create_provider_chain()
        self.last_provider_used: str = ""
        self.last_transcript: str = ""

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
        self.last_transcript = user_input

        # Try pattern cache first for faster extraction
        cached_pattern = pattern_cache.find_similar_pattern(user_input)
        if cached_pattern:
            logger.info("Found cached pattern, will boost confidence")

        # Extract information from input (context-aware)
        extracted_data = self.extract_information(user_input)

        # Add confidence scores
        extraction_with_confidence = {}
        if extracted_data:
            extraction_with_confidence = ConfidenceScorer.add_confidence_to_extraction(
                extracted_data, provider=self.last_provider_used, transcript=user_input
            )

            # Boost confidence for cached patterns
            if cached_pattern:
                for field in extraction_with_confidence:
                    extraction_with_confidence[field]["confidence"] = min(
                        1.0, extraction_with_confidence[field]["confidence"] + 0.1
                    )
                    extraction_with_confidence[field]["cached"] = True

        # Update form data if extraction was successful
        if extracted_data:
            self.update_form_data(extracted_data, extraction_with_confidence)

            # Learn from successful extraction
            pattern_cache.learn_from_success(
                transcript=user_input,
                extracted_fields=extracted_data,
                provider=self.last_provider_used,
            )

        # Generate response
        result = {
            "form_data": self.form_data.copy(),
            "missing_fields": self.missing_fields.copy(),
            "is_complete": self.is_complete(),
            "completion_percentage": self._get_completion_percentage(),
            "extraction_method": self.get_extraction_method_used(),
            "extracted_this_time": extracted_data,
            "field_confidence": self.field_confidence.copy(),
            "extraction_details": extraction_with_confidence,
            "low_confidence_fields": self._get_low_confidence_fields(),
        }

        # Add appropriate message
        if self.is_complete():
            result["message"] = "Great! All required information has been collected."
        else:
            missing_msg = self.get_missing_fields_message()
            low_conf_msg = self._get_low_confidence_message()
            if extracted_data:
                if low_conf_msg:
                    result["message"] = f"Thank you! {low_conf_msg}"
                elif missing_msg:
                    result["message"] = f"Thank you! {missing_msg}"
                else:
                    result["message"] = "Information updated."
            else:
                result["message"] = (
                    "I couldn't extract any form information from your input. "
                    f"{missing_msg if missing_msg else 'Please try again.'}"
                )

        return result

    def _get_low_confidence_fields(self) -> List[str]:
        """Get list of fields with confidence below threshold."""
        return [
            field
            for field, conf in self.field_confidence.items()
            if conf < self.CONFIDENCE_THRESHOLD
        ]

    def _get_low_confidence_message(self) -> Optional[str]:
        """Generate message for low confidence fields."""
        low_conf = self._get_low_confidence_fields()
        if not low_conf:
            return None

        field_labels = form_schema.get_field_labels()
        labels = [field_labels.get(f, f) for f in low_conf]

        if len(labels) == 1:
            return f"Please verify your {labels[0]} - I'm not fully confident about it."
        else:
            return f"Please verify these fields: {', '.join(labels)}."

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

        Uses context-aware extraction when form already has data.

        Args:
            user_input (str): Raw text input from the user containing form information

        Returns:
            Dict[str, str]: Dictionary containing extracted field values
        """
        logger.info("Starting information extraction for input: '%s'", user_input)

        try:
            # Use context-aware extraction if we have existing data
            if self.form_data:
                extracted_data = self.provider_chain.extract_with_context(
                    user_input=user_input,
                    filled_fields=self.form_data,
                    target_fields=self.missing_fields,
                )
            else:
                # Standard extraction for empty form
                extracted_data = self.provider_chain.extract_information(user_input)

            if extracted_data:
                # Track which provider was used
                self.last_provider_used = self.get_extraction_method_used()
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

    def update_form_data(
        self,
        extracted_data: Dict[str, str],
        confidence_data: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """
        Update the internal form data with newly extracted information.

        This method validates, normalizes, and merges extracted field values
        into the existing form data. Also tracks confidence scores per field.

        Args:
            extracted_data (Dict[str, str]): Dictionary containing extracted field values
            confidence_data (Optional[Dict]): Confidence information for each field
        """
        logger.info("Updating form data with: %s", extracted_data)
        logger.debug("Current form data before update: %s", self.form_data)
        logger.debug("Missing fields before update: %s", self.missing_fields)

        # Validate and normalize the extracted data
        validated_data = form_schema.validate_data(extracted_data)

        for field, value in validated_data.items():
            if field in form_schema.get_required_fields() and value:
                # Get confidence for this field
                field_conf = 0.7  # Default confidence
                if confidence_data and field in confidence_data:
                    field_conf = confidence_data[field].get("confidence", 0.7)

                # Store confidence
                self.field_confidence[field] = field_conf

                old_value = self.form_data.get(field)
                self.form_data[field] = value
                if field in self.missing_fields:
                    self.missing_fields.remove(field)
                    logger.info(
                        "Field '%s' filled with value: '%s' (confidence: %.2f)",
                        field,
                        value,
                        field_conf,
                    )
                else:
                    logger.info(
                        "Field '%s' updated from '%s' to '%s' (confidence: %.2f)",
                        field,
                        old_value,
                        value,
                        field_conf,
                    )

        logger.info("Form data after update: %s", self.form_data)
        logger.info("Missing fields after update: %s", self.missing_fields)
        logger.info("Field confidence: %s", self.field_confidence)

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
        """Reset the form processor to initial state, clearing all data and confidence scores."""
        self.form_data = {}
        self.missing_fields = form_schema.get_required_fields()
        self.field_confidence = {}
        self.last_provider_used = "Demo"
        logger.info("Form processor reset successfully")

    def get_provider_chain_status(self) -> List[Dict]:
        """
        Get status of all providers in the chain.

        Returns:
            List[Dict]: Status information for each provider
        """
        return self.provider_chain.get_chain_status()

"""
Data schemas and validation for form processing.

This module provides data validation and normalization for extracted form data.
"""

import re
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class FormField:
    """Represents a form field with validation rules."""

    def __init__(self, name: str, label: str, validator=None):
        self.name = name
        self.label = label
        self.validator = validator or self._default_validator

    def validate(self, value: Any) -> Optional[str]:
        """
        Validate and normalize a field value.

        Args:
            value: Raw value to validate

        Returns:
            Optional[str]: Normalized value or None if invalid
        """
        if not value:
            return None

        return self.validator(str(value).strip())

    def _default_validator(self, value: str) -> Optional[str]:
        """Default validator that just checks for non-empty strings."""
        return value if value else None


class EmailValidator:
    """Email field validator."""

    @staticmethod
    def validate(value: str) -> Optional[str]:
        """Validate and normalize email address."""
        if not value:
            return None

        # Basic email regex pattern
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        # Clean the value
        cleaned = value.lower().strip()

        if re.match(email_pattern, cleaned):
            return cleaned

        logger.warning("Invalid email format: %s", value)
        return None


class PhoneValidator:
    """Phone number field validator."""

    @staticmethod
    def validate(value: str) -> Optional[str]:
        """Validate and normalize phone number."""
        if not value:
            return None

        # Remove all non-digit characters
        digits_only = re.sub(r"\D", "", value)

        # Check for valid length (10-15 digits, accommodate international)
        if 10 <= len(digits_only) <= 15:
            # Format as (XXX) XXX-XXXX for 10-digit US numbers
            if len(digits_only) == 10:
                return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
            # Return as-is for international numbers
            return f"+{digits_only}"

        logger.warning("Invalid phone number format: %s", value)
        return None


class NameValidator:
    """Name field validator."""

    @staticmethod
    def validate(value: str) -> Optional[str]:
        """Validate and normalize name."""
        if not value:
            return None

        # Clean and title case
        cleaned = " ".join(value.strip().split())

        # Basic validation - should contain only letters, spaces, hyphens, apostrophes
        if re.match(r"^[a-zA-Z\s\-']+$", cleaned) and len(cleaned) >= 2:
            return cleaned.title()

        logger.warning("Invalid name format: %s", value)
        return None


class AddressValidator:
    """Address field validator."""

    @staticmethod
    def validate(value: str) -> Optional[str]:
        """Validate and normalize address."""
        if not value:
            return None

        # Clean up spacing and capitalization
        cleaned = " ".join(value.strip().split())

        # Basic validation - should contain letters and numbers
        if (
            len(cleaned) >= 5
            and re.search(r"\d", cleaned)
            and re.search(r"[a-zA-Z]", cleaned)
        ):
            return cleaned.title()

        logger.warning("Invalid address format: %s", value)
        return None


class FormSchema:
    """Schema definition for form fields with validation."""

    def __init__(self):
        self.fields = {
            "name": FormField("name", "Full Name", NameValidator.validate),
            "email": FormField("email", "Email Address", EmailValidator.validate),
            "phone": FormField("phone", "Phone Number", PhoneValidator.validate),
            "address": FormField("address", "Address", AddressValidator.validate),
        }

    def validate_data(self, raw_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate and normalize extracted form data.

        Args:
            raw_data: Raw extracted data dictionary

        Returns:
            Dict[str, str]: Validated and normalized data
        """
        validated = {}

        for field_name, field in self.fields.items():
            if field_name in raw_data:
                normalized_value = field.validate(raw_data[field_name])
                if normalized_value:
                    validated[field_name] = normalized_value
                    logger.info("Validated %s: %s", field_name, normalized_value)
                else:
                    logger.warning(
                        "Failed to validate %s: %s", field_name, raw_data[field_name]
                    )

        return validated

    def get_field_labels(self) -> Dict[str, str]:
        """Get mapping of field names to user-friendly labels."""
        return {name: field.label for name, field in self.fields.items()}

    def get_required_fields(self) -> list:
        """Get list of required field names."""
        return list(self.fields.keys())


# Global form schema instance
form_schema = FormSchema()

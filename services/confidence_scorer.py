"""
Confidence scoring for extracted field values.

This module provides confidence scoring based on extraction method,
pattern matching strength, and value validation.
"""

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """
    Calculates confidence scores for extracted field values.

    Confidence scores range from 0.0 to 1.0 where:
    - 1.0 = High confidence (strong pattern match, validated format)
    - 0.7-0.9 = Good confidence (clear extraction, reasonable format)
    - 0.4-0.7 = Medium confidence (partial match, uncertain format)
    - 0.0-0.4 = Low confidence (weak match, needs verification)
    """

    # Base confidence by provider type
    PROVIDER_BASE_CONFIDENCE = {
        "openai": 0.85,
        "ollama": 0.75,
        "demo": 0.70,
        "regex": 0.70,
        "multimodal": 0.80,
        "cached": 0.90,  # High confidence for cached patterns
    }

    # Validation patterns for each field
    VALIDATION_PATTERNS = {
        "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "phone": r"^[\d\-\(\)\s\.]{7,20}$",
        "name": r"^[A-Za-z][A-Za-z\s\.\-\']{1,50}$",
        "address": r"^[\d\w\s\,\.\-\#]{5,200}$",
    }

    @classmethod
    def calculate_confidence(
        cls,
        field: str,
        value: str,
        provider: str = "unknown",
        transcript: Optional[str] = None,
        extraction_context: Optional[
            Dict[str, Any]
        ] = None,  # pylint: disable=unused-argument
    ) -> float:
        """
        Calculate confidence score for an extracted field value.

        Args:
            field: Field name (name, email, phone, address)
            value: Extracted value
            provider: Name of the provider that extracted the value
            transcript: Original transcript text (for context matching)
            extraction_context: Additional extraction context

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not value or not value.strip():
            return 0.0

        # Start with base confidence for provider
        base = cls.PROVIDER_BASE_CONFIDENCE.get(provider.lower(), 0.6)

        # Calculate modifiers
        format_modifier = cls._format_validation_score(field, value)
        length_modifier = cls._length_score(field, value)
        context_modifier = cls._context_score(field, value, transcript)

        # Combine scores (weighted average)
        confidence = (
            base * 0.4
            + format_modifier * 0.3
            + length_modifier * 0.1
            + context_modifier * 0.2
        )

        # Clamp to valid range
        confidence = max(0.0, min(1.0, confidence))

        logger.debug(
            "Confidence for %s='%s': base=%.2f, format=%.2f, length=%.2f, context=%.2f -> %.2f",
            field,
            value[:20],
            base,
            format_modifier,
            length_modifier,
            context_modifier,
            confidence,
        )

        return round(confidence, 2)

    @classmethod
    def _format_validation_score(cls, field: str, value: str) -> float:
        """Score based on format validation."""
        pattern = cls.VALIDATION_PATTERNS.get(field)
        if not pattern:
            return 0.7  # Default for unknown fields

        if re.match(pattern, value.strip()):
            return 1.0

        # Partial match scoring
        if field == "email":
            if "@" in value and "." in value:
                return 0.7
            elif "@" in value:
                return 0.4
            return 0.2

        elif field == "phone":
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 10:
                return 0.9
            elif len(digits) >= 7:
                return 0.6
            return 0.3

        elif field == "name":
            if len(value.split()) >= 2:  # Has first and last name
                return 0.9
            elif len(value) >= 2:
                return 0.6
            return 0.3

        elif field == "address":
            # Check for common address components
            has_number = bool(re.search(r"\d+", value))
            has_street_word = bool(
                re.search(
                    r"\b(street|st|avenue|ave|road|rd|drive|dr|lane|ln|blvd|court|ct)\b",
                    value.lower(),
                )
            )

            if has_number and has_street_word:
                return 0.9
            elif has_number:
                return 0.6
            return 0.4

        return 0.5

    @classmethod
    def _length_score(cls, field: str, value: str) -> float:
        """Score based on value length appropriateness."""
        length = len(value.strip())

        expected_ranges = {
            "name": (3, 60),
            "email": (5, 100),
            "phone": (7, 20),
            "address": (10, 200),
        }

        min_len, max_len = expected_ranges.get(field, (1, 100))

        if min_len <= length <= max_len:
            return 1.0
        elif length < min_len:
            return length / min_len
        else:
            # Penalize very long values
            return max(0.5, 1.0 - (length - max_len) / max_len)

    @classmethod
    def _context_score(cls, field: str, value: str, transcript: Optional[str]) -> float:
        """Score based on context matching in transcript."""
        if not transcript:
            return 0.7  # Default when no transcript available

        transcript_lower = transcript.lower()
        value_lower = value.lower()

        # Check if value appears in transcript
        if value_lower in transcript_lower:
            return 1.0

        # Check for keyword context
        field_keywords = {
            "name": ["name", "i'm", "i am", "my name", "call me"],
            "email": ["email", "mail", "address", "@", "at"],
            "phone": ["phone", "number", "call", "cell", "mobile"],
            "address": ["address", "live", "street", "house", "apartment"],
        }

        keywords = field_keywords.get(field, [])
        keyword_found = any(kw in transcript_lower for kw in keywords)

        if keyword_found:
            return 0.8

        return 0.5

    @classmethod
    def add_confidence_to_extraction(
        cls,
        extracted_data: Dict[str, str],
        provider: str = "unknown",
        transcript: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Add confidence scores to all extracted fields.

        Args:
            extracted_data: Dictionary of field -> value
            provider: Provider name
            transcript: Original transcript

        Returns:
            Dictionary of field -> {value, confidence}
        """
        result = {}

        for field, value in extracted_data.items():
            if value:
                confidence = cls.calculate_confidence(
                    field=field, value=value, provider=provider, transcript=transcript
                )
                result[field] = {
                    "value": value,
                    "confidence": confidence,
                    "provider": provider,
                }

        return result

    @classmethod
    def should_accept_value(cls, confidence: float, threshold: float = 0.5) -> bool:
        """
        Determine if a value should be automatically accepted.

        Args:
            confidence: Confidence score
            threshold: Minimum threshold for auto-acceptance

        Returns:
            True if value should be accepted
        """
        return confidence >= threshold

    @classmethod
    def get_confidence_label(cls, confidence: float) -> str:
        """Get human-readable label for confidence level."""
        if confidence >= 0.9:
            return "high"
        elif confidence >= 0.7:
            return "good"
        elif confidence >= 0.5:
            return "medium"
        else:
            return "low"


# Convenience instance
confidence_scorer = ConfidenceScorer()

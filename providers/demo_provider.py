"""
Demo provider implementation using regex patterns.

This module provides a fallback extraction system using regular expressions,
implementing the common AIProvider interface for consistent integration.
"""

import re
from typing import Dict, Optional
import logging

from .base import AIProvider

logger = logging.getLogger(__name__)


class DemoProvider(AIProvider):
    """
    Demo provider implementation using regex patterns.

    Provides regex-based information extraction as a fallback when AI providers are unavailable.
    """

    def __init__(self, model_name: str = "regex-patterns", **kwargs):
        """
        Initialize Demo provider.

        Args:
            model_name (str): Identifier for the regex extraction (default: regex-patterns)
            **kwargs: Additional configuration options
        """
        super().__init__(model_name, **kwargs)
        logger.info("Demo provider initialized with regex patterns")

    def extract_information(
        self, user_input: str, prompt: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Extract information using regex patterns.

        Args:
            user_input (str): Raw text input from the user
            prompt (str): Not used in regex extraction, kept for interface consistency

        Returns:
            Optional[Dict]: Extracted information or None if extraction fails
        """
        logger.info("Starting demo extraction for: '%s'", user_input)
        extracted = {}
        text = user_input.lower()
        logger.debug("Lowercased text: '%s'", text)

        # Extract name (look for "my name is" or "I'm" patterns)
        logger.debug("Attempting name extraction")
        name_patterns = [
            # Stop at next field
            r"my name is ([a-zA-Z\s]+?)(?:\s+email|\s+phone|\s+i\s|$)",
            r"i'm ([a-zA-Z\s]+?)(?:\s+email|\s+phone|\s+my\s|$)",
            r"i am ([a-zA-Z\s]+?)(?:\s+email|\s+phone|\s+my\s|$)",
            r"name[:\s]*([a-zA-Z\s]+?)(?:\s+email|\s+phone|$)",
            r"my name is ([a-zA-Z\s]+)",  # Fallback
        ]

        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["name"] = match.group(1).strip().title()
                logger.info(
                    "Name extracted: '%s' using pattern: %s", extracted["name"], pattern
                )
                break
        else:
            logger.debug("No name pattern matched")

        # Extract email
        logger.debug("Attempting email extraction")
        # Handle both standard email format and speech-to-text variations
        # Pre-process: fix common speech-to-text errors
        processed_input = user_input
        # "ad" often transcribed instead of "at"
        processed_input = re.sub(
            r"(\w+)(ad)(\w+)\.com", r"\1@\3.com", processed_input, flags=re.IGNORECASE
        )
        processed_input = re.sub(
            r"(\w+)\s*ad\s*(\w+)\s*dot\s*com",
            r"\1@\2.com",
            processed_input,
            flags=re.IGNORECASE,
        )
        processed_input = re.sub(
            r"(\w+)\s*ad\s*(\w+)\.com",
            r"\1@\2.com",
            processed_input,
            flags=re.IGNORECASE,
        )

        email_patterns = [
            # Standard email
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            # "email john at example.com" (already has .com)
            r"email\s+([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?=\s|$)",
            # "email john at example com" (needs .com added)
            r"email\s+([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+)(?!\.[A-Za-z])(?=\s|$)",
            # "john at example.com" (already has .com)
            r"([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?=\s|$)",
            # "john at example com" (needs .com added)
            r"([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+)(?!\.[A-Za-z])(?=\s|$)",
            # Handle "ad" instead of "at" (common transcription error)
            r"([A-Za-z0-9._%+-]+)\s*ad\s*([A-Za-z0-9.-]+)\.([A-Za-z]{2,})(?=\s|$)",
        ]

        for pattern in email_patterns:
            email_match = re.search(pattern, processed_input, re.IGNORECASE)
            if email_match:
                if len(email_match.groups()) == 3:  # "ad" format with extension
                    local = email_match.group(1).replace(" ", "").lower()
                    domain = email_match.group(2).replace(" ", "").lower()
                    ext = email_match.group(3).lower()
                    extracted["email"] = f"{local}@{domain}.{ext}"
                elif len(email_match.groups()) == 2:  # Speech format
                    local = email_match.group(1).replace(" ", "").lower()
                    domain = email_match.group(2).replace(" ", "").lower()
                    if "." in domain:  # Already has extension
                        extracted["email"] = f"{local}@{domain}"
                    else:  # Needs .com added
                        extracted["email"] = f"{local}@{domain}.com"
                else:  # Standard format
                    extracted["email"] = email_match.group(0).replace(" ", "").lower()
                logger.info(
                    "Email extracted: '%s' using pattern: %s",
                    extracted["email"],
                    pattern,
                )
                break
        else:
            logger.debug("No email pattern matched")

        # Extract phone
        logger.debug("Attempting phone extraction")
        phone_patterns = [
            # Standard format with separators
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            r"phone\s+(\d{9,10})\b",  # "phone 555123467" or "phone 5551234567"
            r"\b(\d{10})\b",  # Just 10 consecutive digits
            r"\b(\d{9})\b",  # Just 9 consecutive digits
            r"\b(\d{3})\s*(\d{3})\s*(\d{4})\b",  # Separated by spaces
        ]

        for pattern in phone_patterns:
            phone_match = re.search(pattern, user_input)
            if phone_match:
                if len(phone_match.groups()) == 3:  # Format: "555 123 4567"
                    extracted["phone"] = (
                        f"{phone_match.group(1)}-{phone_match.group(2)}-{phone_match.group(3)}"
                    )
                elif (
                    len(phone_match.groups()) == 1
                ):  # Format: "5551234567" or "555123467"
                    phone_num = phone_match.group(1)
                    if len(phone_num) == 10:
                        extracted["phone"] = (
                            f"{phone_num[:3]}-{phone_num[3:6]}-{phone_num[6:]}"
                        )
                    elif len(phone_num) == 9:
                        # Assume first 3 are area code, next 3 are prefix, last 3 are suffix
                        extracted["phone"] = (
                            f"{phone_num[:3]}-{phone_num[3:6]}-{phone_num[6:]}"
                        )
                    else:
                        extracted["phone"] = phone_num
                else:  # Already formatted
                    extracted["phone"] = phone_match.group(0)
                logger.info(
                    "Phone extracted: '%s' using pattern: %s",
                    extracted["phone"],
                    pattern,
                )
                break
        else:
            logger.debug("No phone pattern matched")

        # Extract address (look for street, city patterns)
        logger.debug("Attempting address extraction")

        # Pre-process address: convert spoken numbers to digits
        address_text = text
        number_words = {
            "zero": "0",
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
            "ten": "10",
            "eleven": "11",
            "twelve": "12",
            "to": "2",
            "too": "2",
            "for": "4",
            "won": "1",
            "ate": "8",
        }
        # Replace spoken numbers with digits for address matching
        for word, digit in number_words.items():
            address_text = re.sub(
                rf"\b{word}\b", digit, address_text, flags=re.IGNORECASE
            )
        # Clean up multiple spaces
        address_text = re.sub(r"\s+", " ", address_text)

        address_patterns = [
            # Match "address" followed by a number (street address pattern)
            r"(?:my\s+)?address(?:\s+is)?[:\s]+(\d+[^.]*?)(?:\.|$)",
            # Match "address" at start of sentence or after period
            r"(?:^|\.)\s*address[:\s]+([^.]+)",
            # Match "live at" followed by street address
            r"live at\s+(\d+[^.]+?)(?:\.|$)",
            # Match "I live at" pattern
            r"i live at\s+([^.]+?)(?:\.|$)",
            # Match "addresses" (common transcription of "address is")
            r"addresses\s+(\d+[^.]*?)(?:\.|$)",
        ]

        for pattern in address_patterns:
            match = re.search(pattern, address_text, re.IGNORECASE)
            if match:
                address_value = match.group(1).strip()
                # Make sure we didn't accidentally capture "email address" pattern
                if not re.match(
                    r"^[a-z\-]+\s*@|^[a-z\-]+\s+at\s+[a-z]",
                    address_value,
                    re.IGNORECASE,
                ):
                    extracted["address"] = address_value.title()
                    logger.info(
                        "Address extracted: '%s' using pattern: %s",
                        extracted["address"],
                        pattern,
                    )
                    break
        else:
            logger.debug("No address pattern matched")

        logger.info("Demo extraction completed with: %s", extracted)
        return extracted if extracted else None

    def is_available(self) -> bool:
        """Demo provider is always available."""
        return True

    def get_provider_info(self) -> Dict:
        """Get Demo provider information."""
        return {
            "provider": "Demo",
            "model": self.model_name,
            "available": True,
            "status": "ready",
            "description": "Regex-based fallback extraction",
            "patterns": {
                "name": len([p for p in ["my name is", "i'm", "i am"] if p]),
                "email": len([p for p in ["@", "at", "email"] if p]),
                "phone": len([p for p in ["phone", r"\d{10}", r"\d{9}"] if p]),
                "address": len(
                    [p for p in ["live at", "address", "my address is"] if p]
                ),
            },
        }

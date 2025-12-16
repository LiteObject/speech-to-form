"""
Pattern cache service for learning and reusing successful extraction patterns.

This module provides caching of successful extraction patterns to speed up
repeat extractions and improve accuracy over time.
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PatternCache:
    """
    Cache for successful extraction patterns.

    Stores patterns from successful extractions to enable faster processing
    of similar inputs in the future.
    """

    def __init__(
        self, cache_file: str = "pattern_cache.json", max_patterns: int = 1000
    ):
        """
        Initialize the pattern cache.

        Args:
            cache_file: Path to the JSON file for persistent storage
            max_patterns: Maximum number of patterns to store
        """
        self.cache_file = cache_file
        self.max_patterns = max_patterns
        self.patterns: Dict[str, Dict[str, Any]] = {}
        self.field_patterns: Dict[str, List[Dict[str, Any]]] = {
            "name": [],
            "email": [],
            "phone": [],
            "address": [],
        }
        self._index = {}  # Add hash index for O(1) lookups
        self._load_cache()
        self._build_index()
        logger.info("Pattern cache initialized with %d patterns", len(self.patterns))

    def _build_index(self):
        """Build hash index for faster lookups."""
        self._index = {}
        for key, pattern in self.patterns.items():
            transcript = pattern.get("transcript", "")
            idx_key = self._get_pattern_key(transcript)
            if idx_key not in self._index:
                self._index[idx_key] = []
            self._index[idx_key].append(pattern)

    @lru_cache(maxsize=128)
    def _get_pattern_key(self, transcript: str) -> str:
        """Generate hash key for transcript."""
        # Use first 50 chars for key to group similar transcripts
        normalized = transcript.lower().strip()[:50]
        return hashlib.md5(normalized.encode()).hexdigest()[:8]

    def _load_cache(self) -> None:
        """Load patterns from disk if available."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.patterns = data.get("patterns", {})
                    self.field_patterns = data.get(
                        "field_patterns", self.field_patterns
                    )
                logger.info("Loaded %d patterns from cache", len(self.patterns))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load pattern cache: %s", e)

    def _save_cache(self) -> None:
        """Save patterns to disk."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "patterns": self.patterns,
                        "field_patterns": self.field_patterns,
                        "updated_at": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                )
        except IOError as e:
            logger.warning("Failed to save pattern cache: %s", e)

    def _normalize_input(self, text: str) -> str:
        """Normalize input text for pattern matching."""
        # Lowercase and remove extra whitespace
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _create_pattern_key(self, text: str) -> str:
        """Create a hash key for the input pattern."""
        normalized = self._normalize_input(text)
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def _extract_pattern_template(self, text: str, extracted: Dict[str, str]) -> str:
        """
        Create a pattern template by replacing extracted values with placeholders.

        Args:
            text: Original input text
            extracted: Dictionary of extracted field values

        Returns:
            Pattern template with placeholders
        """
        template = self._normalize_input(text)

        for field, value in extracted.items():
            if value:
                # Escape special regex characters in the value
                escaped_value = re.escape(value.lower())
                # Replace the value with a placeholder
                template = re.sub(
                    escaped_value, f"{{{field}}}", template, flags=re.IGNORECASE
                )

        return template

    def learn_from_success(
        self,
        transcript: str,
        extracted_fields: Dict[str, str],
        provider: str = "unknown",
    ) -> None:
        """
        Learn from a successful extraction.

        Args:
            transcript: The original transcript text
            extracted_fields: Successfully extracted field values
            provider: Name of the provider that extracted the data
        """
        if not extracted_fields:
            return

        pattern_key = self._create_pattern_key(transcript)
        template = self._extract_pattern_template(transcript, extracted_fields)

        pattern_entry = {
            "template": template,
            "fields": list(extracted_fields.keys()),
            "provider": provider,
            "success_count": 1,
            "last_used": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "transcript": transcript,  # Store transcript for better matching
        }

        if pattern_key in self.patterns:
            # Update existing pattern
            self.patterns[pattern_key]["success_count"] += 1
            self.patterns[pattern_key]["last_used"] = datetime.now().isoformat()
        else:
            # Add new pattern
            self.patterns[pattern_key] = pattern_entry

            # Update index
            idx_key = self._get_pattern_key(transcript)
            if idx_key not in self._index:
                self._index[idx_key] = []
            self._index[idx_key].append(pattern_entry)

            # Also store field-specific patterns
            for field, value in extracted_fields.items():
                if field in self.field_patterns and value:
                    self._add_field_pattern(field, transcript, value)

        # Prune if too many patterns
        if len(self.patterns) > self.max_patterns:
            self._prune_old_patterns()

        self._save_cache()
        logger.debug("Learned pattern %s from successful extraction", pattern_key)

    def _add_field_pattern(self, field: str, text: str, value: str) -> None:
        """Add a field-specific pattern."""
        # Find the context around the extracted value
        text_lower = text.lower()
        value_lower = value.lower()

        idx = text_lower.find(value_lower)
        if idx == -1:
            return

        # Get surrounding context (20 chars before and after)
        start = max(0, idx - 30)
        end = min(len(text), idx + len(value) + 30)
        context = text_lower[start:end]

        # Create pattern
        pattern = context.replace(value_lower, f"{{{field}}}")

        # Check if similar pattern already exists
        for existing in self.field_patterns[field]:
            if self._patterns_similar(existing["pattern"], pattern):
                existing["count"] += 1
                return

        self.field_patterns[field].append(
            {"pattern": pattern, "count": 1, "created_at": datetime.now().isoformat()}
        )

        # Keep only top 20 patterns per field
        if len(self.field_patterns[field]) > 20:
            self.field_patterns[field].sort(key=lambda x: x["count"], reverse=True)
            self.field_patterns[field] = self.field_patterns[field][:20]

    def _patterns_similar(self, p1: str, p2: str) -> bool:
        """Check if two patterns are similar."""
        # Simple similarity: same structure after removing placeholders
        clean1 = re.sub(r"\{[^}]+\}", "", p1)
        clean2 = re.sub(r"\{[^}]+\}", "", p2)
        return clean1 == clean2

    def find_similar_pattern(self, transcript: str) -> Optional[Dict[str, Any]]:
        """
        Find a similar pattern for the given transcript.

        Args:
            transcript: Input transcript text

        Returns:
            Matching pattern dictionary or None
        """
        # Try hash index first for O(1) lookup
        key = self._get_pattern_key(transcript)
        if key in self._index:
            candidates = self._index[key]

            # Find best match in bucket
            best_match = None
            best_score = 0

            for pattern in candidates:
                # Reconstruct transcript from template if not stored directly
                # Note: This is an approximation since we don't store original transcript in pattern
                # But we can check template similarity
                score = self._calculate_similarity(
                    transcript.lower(), pattern.get("template", "").lower()
                )
                if score > best_score and score > 0.7:
                    best_score = score
                    best_match = pattern

            if best_match:
                logger.info("Pattern cache hit (index) with score %.2f", best_score)
                return best_match

        # Fallback to broader search
        return self._fallback_search(transcript)

    def _fallback_search(self, transcript: str) -> Optional[Dict[str, Any]]:
        """Broader search when hash lookup fails."""
        normalized_input = self._normalize_input(transcript)
        best_match = None
        best_score = 0.0

        # Only search recent patterns for efficiency if we have many
        patterns_to_search = list(self.patterns.values())
        if len(patterns_to_search) > 100:
            # Sort by last used and take top 100
            patterns_to_search.sort(key=lambda x: x.get("last_used", ""), reverse=True)
            patterns_to_search = patterns_to_search[:100]

        for pattern in patterns_to_search:
            template = pattern.get("template", "")
            # Simple similarity check (Jaccard similarity on words)
            score = self._calculate_similarity(normalized_input, template)

            if score > best_score and score > 0.6:  # Threshold for similarity
                best_score = score
                best_match = pattern

        if best_match:
            logger.info("Pattern cache hit (fallback) with score %.2f", best_score)
            return best_match

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts."""
        set1 = set(text1.split())
        set2 = set(text2.split())
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0.0

    def _matches_template(self, text: str, template: str) -> bool:
        """Check if text matches a pattern template."""
        # Convert template to regex
        regex_pattern = template
        for field in ["name", "email", "phone", "address"]:
            regex_pattern = regex_pattern.replace(f"{{{field}}}", r"(.+?)")

        try:
            return bool(re.match(regex_pattern, text))
        except re.error:
            return False

    def get_field_patterns(self, field: str) -> List[str]:
        """
        Get learned patterns for a specific field.

        Args:
            field: Field name (name, email, phone, address)

        Returns:
            List of pattern strings for the field
        """
        if field not in self.field_patterns:
            return []
        return [p["pattern"] for p in self.field_patterns[field]]

    def _prune_old_patterns(self) -> None:
        """Remove oldest/least used patterns to stay under max."""
        # Sort by success_count * recency
        sorted_patterns = sorted(
            self.patterns.items(),
            key=lambda x: x[1].get("success_count", 0),
            reverse=True,
        )
        # Keep top max_patterns
        self.patterns = dict(sorted_patterns[: self.max_patterns])

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "total_patterns": len(self.patterns),
            "field_patterns": {
                field: len(patterns) for field, patterns in self.field_patterns.items()
            },
            "top_patterns": sorted(
                [(k, v.get("success_count", 0)) for k, v in self.patterns.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }

    def clear(self) -> None:
        """Clear all cached patterns."""
        self.patterns = {}
        self.field_patterns = {field: [] for field in self.field_patterns}
        self._save_cache()
        logger.info("Pattern cache cleared")


# Global pattern cache instance
pattern_cache = PatternCache()

"""
Stream processing service for real-time audio transcription and extraction.
"""

import asyncio
import json
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
import whisper
import numpy as np
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class AudioBuffer:
    """Manages audio chunks for streaming processing."""

    sample_rate: int = 16000
    chunk_duration: float = 1.0  # Process every 1 second
    buffer: deque = field(default_factory=lambda: deque(maxlen=10))

    def add_chunk(self, audio_data: np.ndarray) -> None:
        """Add audio chunk to buffer."""
        self.buffer.append(audio_data)

    def get_processable_audio(self) -> Optional[np.ndarray]:
        """Get audio ready for processing."""
        if len(self.buffer) >= 2:  # Need at least 2 chunks
            # Concatenate recent chunks
            return np.concatenate(list(self.buffer))
        return None

    def clear(self) -> None:
        """Clear the buffer."""
        self.buffer.clear()


class StreamProcessor:
    """Handles streaming audio transcription with partial results."""

    def __init__(self, whisper_model: Optional[whisper.Whisper] = None):
        """Initialize stream processor."""
        self.model = whisper_model or whisper.load_model("base")
        self.audio_buffer = AudioBuffer()
        self.last_transcript = ""
        self.extraction_cache = {}

    def process_audio_chunk(self, audio_chunk: bytes) -> Dict[str, Any]:
        """Process a single audio chunk and return partial results."""
        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_chunk, dtype=np.float32)
        self.audio_buffer.add_chunk(audio_array)

        # Get processable audio
        audio_data = self.audio_buffer.get_processable_audio()
        if audio_data is None:
            return {"partial": True, "transcript": "", "fields": {}}

        # Transcribe the audio
        result = self.model.transcribe(audio_data, fp16=False)
        transcript = result.get("text", "")

        # Extract fields from partial transcript
        fields = self._extract_fields_from_partial(transcript)

        return {
            "partial": True,
            "transcript": transcript,
            "fields": fields,
            "confidence": self._calculate_confidence(transcript, fields),
        }

    async def _transcribe_async(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Asynchronously transcribe audio."""
        # Run transcription in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.model.transcribe(audio_data, fp16=False)
        )

    def _extract_fields_from_partial(self, transcript: str) -> Dict[str, str]:
        """Extract fields from partial transcript using progressive patterns."""
        fields = {}

        # Progressive field extraction patterns
        patterns = {
            "name": [
                r"(?:my name is|i'm|i am|this is)\s+([A-Z][a-z]+ [A-Z][a-z]+)",
                r"^([A-Z][a-z]+ [A-Z][a-z]+)",
            ],
            "email": [
                r"([a-zA-Z0-9._%+-]+)\s*at\s*([a-zA-Z0-9.-]+)\s*dot\s*([a-zA-Z]{2,})",
                r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            ],
            "phone": [
                r"(\d{3})[\s-]?(\d{3})[\s-]?(\d{4})",
                r"phone.*?(\d{10})",
            ],
        }

        import re

        for field_name, field_patterns in patterns.items():
            for pattern in field_patterns:
                match = re.search(pattern, transcript, re.IGNORECASE)
                if match:
                    if field_name == "email" and "@" not in match.group(0):
                        # Reconstruct email from parts
                        fields[field_name] = (
                            f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
                        )
                    elif field_name == "phone" and len(match.groups()) == 3:
                        fields[field_name] = (
                            f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                        )
                    else:
                        fields[field_name] = (
                            match.group(0) if match.lastindex == 0 else match.group(1)
                        )
                    break

        return fields

    def _calculate_confidence(self, transcript: str, fields: Dict[str, str]) -> float:
        """Calculate confidence for partial results."""
        if not transcript:
            return 0.0

        # Base confidence on transcript length and field count
        base_confidence = min(len(transcript) / 100, 0.5)  # Max 0.5 for partial
        field_confidence = len(fields) * 0.1  # 0.1 per field found

        return min(base_confidence + field_confidence, 0.9)  # Cap at 0.9 for partial

    async def stream_transcribe(
        self, audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream transcription results as audio comes in."""
        async for audio_chunk in audio_stream:
            result = await self.process_audio_chunk(audio_chunk)
            if result["transcript"] != self.last_transcript:
                self.last_transcript = result["transcript"]
                yield result

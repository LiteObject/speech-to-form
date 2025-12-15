"""
AI Providers Package

This package implements the Adapter and Factory patterns for AI provider integration.
It provides a consistent interface for different AI services (OpenAI, Ollama, regex fallback).
"""

from .base import AIProvider
from .factory import AIProviderFactory, ProviderChain
from .openai_provider import OpenAIProvider
from .ollama_provider import OllamaProvider
from .demo_provider import DemoProvider

__all__ = [
    "AIProvider",
    "AIProviderFactory",
    "ProviderChain",
    "OpenAIProvider",
    "OllamaProvider",
    "DemoProvider",
]

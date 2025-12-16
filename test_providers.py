"""
Test script for the new modular AI provider architecture.

This script tests the Factory and Adapter patterns implementation.
"""

import os
import sys

from providers import AIProviderFactory, ProviderChain

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def test_provider_creation():
    """Test creating different types of providers."""
    print("🔧 Testing Provider Creation...")

    # Test Demo Provider (should always work)
    try:
        demo_provider = AIProviderFactory.create_provider("demo")
        print(f"✅ Demo Provider: {demo_provider.get_provider_info()}")
    except (ImportError, ValueError, RuntimeError, TypeError) as e:
        print(f"❌ Demo Provider failed: {e}")

    # Test OpenAI Provider
    try:
        openai_provider = AIProviderFactory.create_provider("openai")
        print(f"✅ OpenAI Provider: {openai_provider.get_provider_info()}")
    except (ImportError, ValueError, RuntimeError, TypeError) as e:
        print(f"❌ OpenAI Provider failed: {e}")

    # Test Ollama Provider
    try:
        ollama_provider = AIProviderFactory.create_provider("ollama")
        print(f"✅ Ollama Provider: {ollama_provider.get_provider_info()}")
    except (ImportError, ValueError, RuntimeError, TypeError) as e:
        print(f"❌ Ollama Provider failed: {e}")


def test_provider_chain():
    """Test provider chain functionality."""
    print("\n🔗 Testing Provider Chain...")

    try:
        # Create a chain with all providers
        providers = AIProviderFactory.create_chain(["ollama", "openai", "demo"])
        chain = ProviderChain(providers)

        print(f"✅ Created chain with {len(providers)} providers")

        # Test extraction
        test_input = "My name is John Doe and my email is john@example.com"
        result = chain.extract_information(test_input)

        if result:
            print(f"✅ Extraction successful: {result}")
        else:
            print("❌ Extraction failed")

    except (ImportError, ValueError, RuntimeError, TypeError, AttributeError) as e:
        print(f"❌ Provider chain test failed: {e}")


def test_factory_from_config():
    """Test creating provider from configuration."""
    print("\n⚙️ Testing Factory from Config...")

    try:
        provider = AIProviderFactory.create_from_config()
        print(f"✅ Created provider from config: {provider.get_provider_info()}")

        # Test extraction
        test_input = "Hi, I'm Jane Smith, phone 555-123-4567"
        result = provider.extract_information(test_input)

        if result:
            print(f"✅ Config provider extraction: {result}")
        else:
            print("❌ Config provider extraction failed")

    except (ImportError, ValueError, RuntimeError, TypeError, AttributeError) as e:
        print(f"❌ Config provider test failed: {e}")


if __name__ == "__main__":
    print("🚀 Testing Modular AI Provider Architecture\n")

    # Show available providers
    available = AIProviderFactory.get_available_providers()
    print(f"📋 Available providers: {available}\n")

    # Run tests
    test_provider_creation()
    test_provider_chain()
    test_factory_from_config()

    print("\n✨ Testing completed!")

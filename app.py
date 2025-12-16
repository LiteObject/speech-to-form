"""
Speech-to-Form Flask Application

A web application that processes speech input and extracts structured information
to automatically fill form fields using natural lan        })

    except (ValueError, RuntimeError) as e:ge processing.

Now using modular AI provider architecture with Adapter and Factory patterns.
"""

import logging
from datetime import datetime
import tempfile
import os

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from config import settings
from services import FormProcessor
from providers.local_whisper_provider import LocalWhisperProvider

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(settings.LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global form processor instance
form_processor = FormProcessor()

# Whisper provider storage (using dict to avoid global statement)
_whisper_state: dict = {"provider": None}


def get_whisper_provider():
    """Get or create whisper provider instance."""
    if _whisper_state["provider"] is None:
        model_size = getattr(settings, "WHISPER_MODEL_SIZE", "base")
        _whisper_state["provider"] = LocalWhisperProvider(model_size=model_size)
    return _whisper_state["provider"]


@app.route("/")
def index():
    """
    Render the main form page.

    Returns:
        str: Rendered HTML template with current form data and missing fields
    """
    logger.info("Index page accessed")
    return render_template(
        "index.html",
        form_data=form_processor.form_data,
        missing_fields=form_processor.missing_fields,
        required_fields_list=list(settings.REQUIRED_FIELDS.keys()),
    )


@app.route("/process", methods=["POST"])
def process_text():
    """
    Process incoming text/speech data and update form fields.

    Expected JSON payload:
        {
            "text": "User input text to process"
        }

    Returns:
        JSON: Updated form data, missing fields, and processing messages
    """
    try:
        logger.info("Processing request received")

        # Get JSON data from request
        if not request.is_json:
            logger.error("Request is not JSON")
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        if not data or "text" not in data:
            logger.error("Missing 'text' field in request data")
            return jsonify({"error": "Missing 'text' field"}), 400

        user_input = data["text"].strip()
        if not user_input:
            logger.error("Empty text input received")
            return jsonify({"error": "Text input cannot be empty"}), 400

        logger.info(
            "Processing text input: %s", user_input[:100]
        )  # Log first 100 chars

        # Process the input using the form processor
        result = form_processor.process_input(user_input)

        logger.info("Processing completed successfully")
        logger.info("Current form data: %s", form_processor.form_data)
        logger.info("Missing fields: %s", form_processor.missing_fields)

        return jsonify(result)

    except (ValueError, RuntimeError, KeyError, TypeError) as e:
        logger.error("Error processing text: %s", str(e), exc_info=True)
        return (
            jsonify(
                {
                    "error": "An error occurred while processing your text",
                    "details": str(e),
                }
            ),
            500,
        )


@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    """
    Transcribe uploaded audio file using local Whisper.

    Expected form data:
        - audio: Audio file (wav, mp3, m4a, etc.)

    Returns:
        JSON: Transcription result and processing status
    """
    try:
        logger.info("Audio transcription request received")

        # Check if audio file is provided
        if "audio" not in request.files:
            logger.error("No audio file in request")
            return jsonify({"success": False, "error": "No audio file provided"}), 400

        audio_file = request.files["audio"]
        if audio_file.filename == "":
            logger.error("Empty audio filename")
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Validate file type
        allowed_extensions = {"wav", "mp3", "m4a", "ogg", "flac", "webm", "mp4"}
        filename = audio_file.filename or "audio"
        file_ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""

        if file_ext not in allowed_extensions:
            logger.warning("Unsupported file type: %s", file_ext)
            return (
                jsonify(
                    {"success": False, "error": f"Unsupported file type: {file_ext}"}
                ),
                400,
            )

        # Get Whisper provider
        whisper_instance = get_whisper_provider()
        if not whisper_instance.is_available():
            logger.error("Whisper provider not available")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Speech recognition service not available",
                    }
                ),
                503,
            )

        # Create secure temporary file
        secure_fname = secure_filename(filename)
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{file_ext}"
        ) as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_file_path = tmp_file.name

        try:
            # Transcribe audio
            logger.info("Starting transcription of file: %s", secure_fname)
            transcript = whisper_instance.transcribe_audio(tmp_file_path)

            if transcript:
                logger.info("Transcription successful: %s", transcript[:100])

                # Process the transcript through the form processor
                result = form_processor.process_input(transcript)

                return jsonify(
                    {
                        "success": True,
                        "transcript": transcript,
                        "form_data": result.get("form_data", {}),
                        "missing_fields": result.get("missing_fields", []),
                        "message": result.get("message", "Transcription completed"),
                        "method": "local_whisper",
                        "model": whisper_instance.model_size,
                    }
                )
            else:
                logger.warning("Transcription returned empty result")
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Could not transcribe audio - please try speaking more clearly",
                        }
                    ),
                    422,
                )

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except (ValueError, RuntimeError, OSError) as e:
        logger.error("Error transcribing audio: %s", str(e), exc_info=True)
        return (
            jsonify(
                {"success": False, "error": "Transcription failed", "details": str(e)}
            ),
            500,
        )


@app.route("/transcribe_simple", methods=["POST"])
def transcribe_audio_simple():
    """
    Simple transcribe endpoint that returns only the raw transcript without form processing.
    Designed for field-specific recording where we just need the raw text.

    Expected form data:
        - audio: Audio file (wav, mp3, m4a, etc.)

    Returns:
        JSON: Raw transcription result only
    """
    try:
        logger.info("Simple audio transcription request received")

        # Check if audio file is provided
        if "audio" not in request.files:
            logger.error("No audio file in request")
            return jsonify({"success": False, "error": "No audio file provided"}), 400

        audio_file = request.files["audio"]
        if audio_file.filename == "":
            logger.error("Empty audio filename")
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Validate file type
        allowed_extensions = {"wav", "mp3", "m4a", "ogg", "flac", "webm", "mp4"}
        filename = audio_file.filename or "audio"
        file_ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""

        if file_ext not in allowed_extensions:
            logger.warning("Unsupported file type: %s", file_ext)
            return (
                jsonify(
                    {"success": False, "error": f"Unsupported file type: {file_ext}"}
                ),
                400,
            )

        # Get Whisper provider
        whisper_instance = get_whisper_provider()
        if not whisper_instance.is_available():
            logger.error("Whisper provider not available")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Speech recognition service not available",
                    }
                ),
                503,
            )

        # Create secure temporary file
        secure_fname = secure_filename(filename)
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{file_ext}"
        ) as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_file_path = tmp_file.name

        try:
            # Transcribe audio
            logger.info("Starting simple transcription of file: %s", secure_fname)
            transcript = whisper_instance.transcribe_audio(tmp_file_path)

            if transcript:
                logger.info("Simple transcription successful: %s", transcript[:100])

                # Return just the raw transcript without form processing
                return jsonify(
                    {
                        "success": True,
                        "transcript": transcript,
                        "method": "local_whisper",
                        "model": whisper_instance.model_size,
                    }
                )
            else:
                logger.warning("Simple transcription returned empty result")
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Could not transcribe audio - please try speaking more clearly",
                        }
                    ),
                    422,
                )

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except (ValueError, RuntimeError, OSError) as e:
        logger.error("Error in simple transcription: %s", str(e), exc_info=True)
        return (
            jsonify(
                {"success": False, "error": "Transcription failed", "details": str(e)}
            ),
            500,
        )


# Global multimodal provider instances (initialize lazily per backend)
multimodal_providers = {}


def get_multimodal_provider(backend: str = "openai"):
    """Get or create multimodal provider instance for specified backend."""
    # multimodal_providers is module-level dict, accessed directly
    if backend not in multimodal_providers:
        from providers.multimodal_provider import MultimodalProvider

        if backend == "openai":
            multimodal_providers[backend] = MultimodalProvider(
                model_name="gpt-4o-audio-preview", backend="openai"
            )
        elif backend == "ollama":
            multimodal_providers[backend] = MultimodalProvider(
                model_name="gpt-oss:20b",  # Uses local Whisper + Ollama LLM
                backend="ollama",
            )
        elif backend == "vllm":
            multimodal_providers[backend] = MultimodalProvider(
                model_name="fixie-ai/ultravox-v0_4",  # Audio-capable model
                backend="vllm",
            )
        else:
            logger.warning("Unknown backend '%s', falling back to openai", backend)
            return get_multimodal_provider("openai")

    return multimodal_providers[backend]


@app.route("/transcribe_multimodal", methods=["POST"])
def transcribe_audio_multimodal():
    """
    Single-stage multimodal transcription and extraction.

    Supports multiple backends:
    - openai: GPT-4o with native audio support (cloud)
    - ollama: Local Whisper + Ollama LLM (local)
    - vllm: vLLM with audio-capable model (local)

    Expected form data:
        - audio: Audio file (wav, mp3, m4a, etc.)
        - backend: Backend to use (openai, ollama, vllm) - default: openai

    Returns:
        JSON: Transcription and extracted form data
    """
    try:
        # Get backend from form data (default to openai for cloud)
        backend = request.form.get("backend", "openai")
        logger.info(
            "Multimodal audio processing request received (backend: %s)", backend
        )

        # Check if audio file is provided
        if "audio" not in request.files:
            logger.error("No audio file in request")
            return jsonify({"success": False, "error": "No audio file provided"}), 400

        audio_file = request.files["audio"]
        if audio_file.filename == "":
            logger.error("Empty audio filename")
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Validate file type
        allowed_extensions = {"wav", "mp3", "m4a", "ogg", "flac", "webm", "mp4"}
        filename = audio_file.filename or "audio"
        file_ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""

        if file_ext not in allowed_extensions:
            logger.warning("Unsupported file type: %s", file_ext)
            return (
                jsonify(
                    {"success": False, "error": f"Unsupported file type: {file_ext}"}
                ),
                400,
            )

        # Get multimodal provider for specified backend
        multimodal = get_multimodal_provider(backend)
        if not multimodal.is_available():
            # Provide helpful error message based on backend
            error_messages = {
                "openai": "OpenAI service not available. Check OPENAI_API_KEY.",
                "ollama": "Ollama service not available. Ensure Ollama is running and Whisper is installed.",
                "vllm": "vLLM service not available. Ensure vLLM server is running.",
            }
            error_msg = error_messages.get(backend, "Multimodal service not available.")
            logger.error("Multimodal provider not available (backend: %s)", backend)
            return (
                jsonify({"success": False, "error": error_msg}),
                503,
            )

        # Create secure temporary file
        secure_fname = secure_filename(filename)
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{file_ext}"
        ) as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_file_path = tmp_file.name

        try:
            # Process audio with multimodal provider (single-stage)
            logger.info(
                "Starting multimodal processing of file: %s (backend: %s)",
                secure_fname,
                backend,
            )
            result = multimodal.extract_from_audio(tmp_file_path)

            if result:
                logger.info("Multimodal processing successful (backend: %s)", backend)

                return jsonify(
                    {
                        "success": True,
                        "transcript": result.get("transcript", ""),
                        "form_data": result.get("form_data", {}),
                        "missing_fields": result.get("missing_fields", []),
                        "message": f"Single-stage processing completed ({backend})",
                        "method": "multimodal",
                        "backend": backend,
                        "model": multimodal.model_name,
                    }
                )
            else:
                logger.warning("Multimodal processing returned empty result")
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Could not process audio - please try again",
                        }
                    ),
                    422,
                )

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except (ValueError, RuntimeError, OSError) as e:
        logger.error("Error in multimodal processing: %s", str(e), exc_info=True)
        return (
            jsonify(
                {"success": False, "error": "Processing failed", "details": str(e)}
            ),
            500,
        )


@app.route("/status", methods=["GET"])
def get_status():
    """
    Get current form processing status.

    Returns:
        JSON: Current form data, completion status, and provider information
    """
    try:
        logger.info("Status request received")

        # Calculate completion percentage
        total_fields = len(settings.REQUIRED_FIELDS)
        completed_fields = total_fields - len(form_processor.missing_fields)
        completion_percentage = (
            (completed_fields / total_fields) * 100 if total_fields > 0 else 0
        )

        status_data = {
            "form_data": form_processor.form_data,
            "missing_fields": form_processor.missing_fields,
            "required_fields": settings.REQUIRED_FIELDS,
            "completion_percentage": round(completion_percentage, 1),
            "is_complete": len(form_processor.missing_fields) == 0,
            "total_fields": total_fields,
            "completed_fields": completed_fields,
            "provider_info": [
                provider.get_provider_info()
                for provider in form_processor.provider_chain.providers
            ],
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            "Status retrieved: %d/%d fields completed", completed_fields, total_fields
        )
        return jsonify(status_data)

    except (ValueError, RuntimeError, KeyError) as e:
        logger.error("Error getting status: %s", str(e), exc_info=True)
        return (
            jsonify(
                {"error": "An error occurred while getting status", "details": str(e)}
            ),
            500,
        )


@app.route("/reset", methods=["POST"])
def reset_form():
    """
    Reset all form data and start over.

    Returns:
        JSON: Confirmation message and reset form state
    """
    try:
        logger.info("Form reset requested")

        # Reset the form processor
        form_processor.reset()

        logger.info("Form reset completed")
        return jsonify(
            {
                "message": "Form has been reset successfully",
                "form_data": form_processor.form_data,
                "missing_fields": form_processor.missing_fields,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except (ValueError, RuntimeError) as e:
        logger.error("Error resetting form: %s", str(e), exc_info=True)
        return (
            jsonify(
                {
                    "error": "An error occurred while resetting the form",
                    "details": str(e),
                }
            ),
            500,
        )


@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        JSON: Application health status and provider availability
    """
    try:
        # Check provider health
        provider_health = []
        for provider in form_processor.provider_chain.providers:
            provider_info = provider.get_provider_info()
            provider_health.append(
                {
                    "provider": provider_info["provider"],
                    "status": provider_info["status"],
                    "available": provider_info["status"] == "available",
                }
            )

        # Overall health
        healthy_providers = sum(1 for p in provider_health if p["available"])
        overall_health = "healthy" if healthy_providers > 0 else "degraded"

        health_data = {
            "status": overall_health,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "providers": provider_health,
            "total_providers": len(provider_health),
            "healthy_providers": healthy_providers,
            "app_settings": {
                "log_level": settings.LOG_LEVEL,
                "required_fields_count": len(settings.REQUIRED_FIELDS),
            },
        }

        status_code = 200 if overall_health == "healthy" else 503
        return jsonify(health_data), status_code

    except (ValueError, RuntimeError, AttributeError) as e:
        logger.error("Error in health check: %s", str(e), exc_info=True)
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            500,
        )


# Error handlers
@app.errorhandler(404)
def not_found_error(_error):
    """Handle 404 errors."""
    logger.warning("404 error: %s", request.url)
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed_error(_error):
    """Handle 405 errors."""
    logger.warning("405 error: %s %s", request.method, request.url)
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error("500 error: %s", str(error))
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    logger.info("Starting Speech-to-Form application")
    logger.info("Configuration loaded from: %s", "environment variables")
    logger.info(
        "Available providers: %s",
        [
            provider.get_provider_info()["provider"]
            for provider in form_processor.provider_chain.providers
        ],
    )

    # Preload Whisper model to eliminate first-call delay
    logger.info("Preloading Whisper model for faster first transcription...")
    try:
        whisper_loader = get_whisper_provider()
        if whisper_loader.preload_model():
            logger.info("Whisper model preloaded successfully")
        else:
            logger.warning("Whisper model preload failed - first call will be slower")
    except (ValueError, RuntimeError, OSError) as e:
        logger.warning("Whisper preload error: %s - first call will be slower", str(e))

    app.run(
        host=settings.FLASK_HOST, port=settings.FLASK_PORT, debug=settings.FLASK_DEBUG
    )

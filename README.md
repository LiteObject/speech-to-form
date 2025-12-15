# Voice-Enabled Form Demo Application

This is a Flask web application that demonstrates intelligent voice-enabled form filling using speech recognition and AI-powered text processing with real-time field highlighting and step-by-step guidance.

## Architecture Overview

The application uses a two-stage pipeline to convert speech into structured form data:

```
Audio Input --> [Speech-to-Text] --> Text --> [Text Extraction] --> Form Fields
                   (Whisper)                   (Regex/LLM)
```

### Stage 1: Speech-to-Text (Whisper)

Local Whisper model transcribes audio to text. This runs entirely on your machine.

### Stage 2: Text Extraction

Configurable extractors parse the transcribed text into structured form fields. The system tries extractors in priority order until one succeeds.

## Extraction Approaches

The application supports multiple extraction strategies, each with different trade-offs:

### Approach 1: Regex-First (Default)

```
AI_PROVIDER_PRIORITY=demo,ollama,openai
```

| Aspect | Details |
|--------|---------|
| Speed | Instant (less than 1ms) |
| Accuracy | Good for predictable patterns |
| Offline | Yes |
| Cost | Free |

**How it works**: Uses regular expressions to match patterns like "my name is [NAME]" or "[EMAIL] at [DOMAIN] dot com".

**Pros**:
- Extremely fast response time
- Works completely offline
- No API costs
- Predictable behavior

**Cons**:
- Requires users to speak in expected patterns
- May fail on unusual phrasing
- Needs manual pattern updates for new speech variations

**Best for**: Applications where users follow guided prompts and speed is critical.

### Approach 2: LLM-First (Ollama)

```
AI_PROVIDER_PRIORITY=ollama,demo,openai
```

| Aspect | Details |
|--------|---------|
| Speed | 2-10 seconds (depends on model size) |
| Accuracy | High, handles varied phrasing |
| Offline | Yes (local inference) |
| Cost | Free (requires GPU for best performance) |

**How it works**: Sends the transcribed text to a local LLM (via Ollama) with a prompt requesting structured JSON output.

**Pros**:
- Understands natural language variations
- Handles complex or ambiguous input
- No cloud API dependency
- Can extract from unstructured speech

**Cons**:
- Slower than regex (seconds vs milliseconds)
- Requires Ollama running locally
- GPU recommended for acceptable speed
- Model quality affects accuracy

**Best for**: Applications requiring flexibility in how users speak.

### Approach 3: Cloud API (OpenAI)

```
AI_PROVIDER_PRIORITY=openai,demo
```

| Aspect | Details |
|--------|---------|
| Speed | 1-3 seconds |
| Accuracy | Highest |
| Offline | No |
| Cost | Pay per request |

**How it works**: Sends transcribed text to OpenAI API for extraction.

**Pros**:
- Best accuracy and language understanding
- No local compute requirements
- Handles edge cases well
- Consistent performance

**Cons**:
- Requires internet connection
- API costs accumulate with usage
- Privacy considerations for sensitive data
- Rate limits may apply

**Best for**: Production applications where accuracy is paramount and cost is acceptable.

### Approach 4: Single-Stage Multimodal (Implemented)

The application supports multiple backends for single-stage processing:

#### Backend Options

| Backend | Audio Processing | Extraction | Requirements |
|---------|-----------------|------------|--------------|
| **OpenAI GPT-4o** | Cloud (native audio) | Cloud | OPENAI_API_KEY |
| **Ollama** | Local Whisper | Local LLM | Ollama running |
| **vLLM** | Local (Ultravox) | Local | NVIDIA GPU + vLLM server |

#### OpenAI GPT-4o (Cloud)

```
Audio --> [GPT-4o Audio API] --> Form Fields
          (transcribe + extract in one call)
```

| Aspect | Details |
|--------|---------|
| Speed | 2-5 seconds |
| Accuracy | Highest (audio context preserved) |
| Offline | No |
| Cost | Higher (audio tokens) |

**How it works**: Audio is sent directly to GPT-4o which handles both transcription and field extraction in a single API call.

**Pros**:
- Single model handles everything
- Audio context preserved (tone, emphasis)
- Best accuracy for ambiguous speech
- Simpler architecture (one API call)

**Cons**:
- Requires OpenAI API key with audio model access
- Higher cost per request (audio tokens)
- Audio must be uploaded to cloud
- Requires internet connection

#### Ollama Backend (Local)

```
Audio --> [Local Whisper] --> Text --> [Ollama LLM] --> Form Fields
```

| Aspect | Details |
|--------|---------|
| Speed | 3-15 seconds (depends on model) |
| Accuracy | Good (depends on LLM quality) |
| Offline | Yes |
| Cost | Free |

**How it works**: Uses local Whisper for transcription, then sends text to your local Ollama model for extraction.

**Pros**:
- Completely offline and private
- No API costs
- Uses your existing Ollama setup
- Works on CPU (slower) or GPU

**Cons**:
- Slower than cloud options
- Accuracy depends on local model quality
- Requires Ollama to be running

#### vLLM Backend (Local GPU)

```
Audio --> [vLLM + Ultravox] --> Form Fields
          (native audio model)
```

| Aspect | Details |
|--------|---------|
| Speed | 2-5 seconds |
| Accuracy | High |
| Offline | Yes |
| Cost | Free (but requires GPU) |

**How it works**: Uses vLLM with audio-capable models like Ultravox for native audio processing.

**Pros**:
- True single-stage local processing
- No cloud dependency
- High throughput with GPU

**Cons**:
- **Requires NVIDIA GPU** (compute capability 7.0+)
- Requires vLLM server running
- Large model downloads
- Not suitable for CPU-only systems

## Recommendations

### Choose Your Setup Based On:

| Your Situation | Recommended Setup |
|----------------|-------------------|
| **No GPU, want speed** | Two-Stage with regex-first (`demo,ollama,openai`) |
| **No GPU, want accuracy** | Two-Stage with Ollama-first (`ollama,demo,openai`) |
| **Have OpenAI API key** | Single-Stage with OpenAI GPT-4o |
| **Privacy-focused, no cloud** | Two-Stage with Ollama or Single-Stage Ollama backend |
| **Have NVIDIA GPU** | Single-Stage with vLLM + Ultravox |
| **Production app** | Single-Stage OpenAI (most reliable) |

### Quick Decision Guide

```
Do you have an OpenAI API key?
├── Yes --> Use Single-Stage: OpenAI GPT-4o (best accuracy)
└── No
    ├── Do you need high accuracy?
    │   ├── Yes --> Use Two-Stage: Ollama-first
    │   └── No --> Use Two-Stage: Regex-first (fastest)
    └── Do you have an NVIDIA GPU?
        ├── Yes --> Consider Single-Stage: vLLM
        └── No --> Use Two-Stage or Single-Stage: Ollama
```

### Performance Expectations

| Mode | Backend | Typical Latency | Accuracy |
|------|---------|-----------------|----------|
| Two-Stage | Demo (regex) | < 2 sec | Good (pattern-dependent) |
| Two-Stage | Ollama | 3-15 sec | Good-High |
| Single-Stage | OpenAI | 2-5 sec | Highest |
| Single-Stage | Ollama | 3-15 sec | Good-High |
| Single-Stage | vLLM | 2-5 sec | High |

## User Interface Mode Selection

The application provides a UI toggle to switch between processing modes:

### Processing Modes

| Mode | Description | When to Use |
|------|-------------|-------------|
| **Two-Stage (Local)** | Whisper + local extraction | Fast, offline, free |
| **Single-Stage** | Direct audio-to-fields | Most accurate |

### Single-Stage Backend Options

When Single-Stage is selected, you can choose from:

| Backend | Description | Requirements |
|---------|-------------|--------------|
| **OpenAI GPT-4o** | Cloud processing with native audio | `OPENAI_API_KEY` in `.env` |
| **Ollama** | Local Whisper + Ollama LLM | Ollama server running |
| **vLLM** | Local GPU with Ultravox | NVIDIA GPU + vLLM server |

Users can select their preferred mode and backend from the form interface before recording.

## Choosing an Approach

| Priority | Use Case |
|----------|----------|
| Speed | Use regex-first (demo,ollama,openai) |
| Accuracy | Use LLM-first (ollama,demo,openai) or cloud (openai,demo) |
| Privacy | Use regex or local Ollama (no cloud) |
| Cost | Use regex or Ollama (no API fees) |
| Simplicity | Use cloud API (openai) for easiest setup |

## Configuration

Set the extraction priority in your `.env` file:

```env
# Fast regex, fallback to LLM
AI_PROVIDER_PRIORITY=demo,ollama,openai

# Accurate LLM, fallback to regex
AI_PROVIDER_PRIORITY=ollama,demo,openai

# Cloud API only
AI_PROVIDER_PRIORITY=openai,demo
```

## Features

### Core Functionality
- **Smart Web Form**: Interactive form with fields for name, email, phone, and address
- **Speech Recognition**: Uses browser's Web Speech API for real-time voice input
- **AI-Powered Processing**: OpenAI GPT-4o-mini integration with intelligent regex fallback
- **Step-by-Step Guidance**: Highlights current field and guides users through form completion
- **Real-time Field Highlighting**: Visual feedback showing which field to fill next

### Advanced Features  
- **Intelligent Email Extraction**: Converts speech patterns like "john at example dot com" to valid email format
- **Flexible Phone Number Processing**: Handles various phone number formats and speech variations
- **Missing Information Detection**: Automatically identifies and requests incomplete fields
- **Comprehensive Logging**: Debug-level logging for development and troubleshooting
- **Health Check Endpoint**: Monitor application and OpenAI API connectivity status
- **Graceful Fallback**: Seamless switch to regex extraction when OpenAI is unavailable

## Quick Start

### 1. Project Structure
```
speech-to-form/
├── app.py                 # Main Flask application with OpenAI integration
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables (create from .env.example)
├── .env.example          # Example environment configuration
├── speech_to_form.log    # Application logs (auto-generated)
└── templates/
    └── index.html        # Frontend with step-by-step field highlighting
```

### 2. Installation
```bash
# Clone the repository
git clone <repository-url>
cd speech-to-form

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env file with your OpenAI API key (optional)
```

### 3. Environment Setup
Create a `.env` file with your OpenAI API key (optional - the app works without it):
```env
OPENAI_API_KEY=your-actual-openai-api-key-here
```

**Note**: If no OpenAI API key is provided, the application automatically uses intelligent regex-based extraction as a fallback.

### 4. Run the Application
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## How to Use

### Step-by-Step Voice Form Filling
1. **Open the Application**: Navigate to `http://localhost:5000` in your browser
2. **Grant Microphone Permission**: Allow the browser to access your microphone when prompted
3. **Follow Visual Guidance**: The first field (name) will be highlighted automatically
4. **Start Recording**: Click "Start Recording" and speak your information for the highlighted field
5. **Field-by-Field Progress**: After each successful extraction, the next empty field will be highlighted
6. **Complete the Form**: Continue until all fields are filled

### Example Speech Patterns
The application intelligently handles various speech patterns:

**Natural Speech Examples:**
- "My name is John Doe"
- "My email is john at example dot com" *(converts to john@example.com)*
- "Phone number is five five five one two three four five six seven"
- "I live at 123 Main Street, New York"

**Combined Information:**
- "Hi, I'm Sarah Johnson, my email is sarah at gmail dot com, phone 555-987-6543, and I live at 456 Oak Avenue, Chicago"

## Technical Details

### Speech Recognition
- **Web Speech API**: Real-time continuous speech recognition
- **Browser Support**: Chrome, Edge, Safari (best), Firefox (limited)
- **Language**: English (US) with interim results
- **Error Handling**: Automatic recovery and restart on connection issues

### AI Processing Architecture
- **Primary**: OpenAI GPT-4o-mini with structured JSON output
- **Fallback**: Intelligent regex patterns for offline operation
- **Dual Model Support**: Falls back from GPT-4o-mini to GPT-3.5-turbo if needed
- **Smart Extraction**: Handles speech-to-text variations (e.g., "at" → "@", "dot" → ".")

### Form Management
- **Required Fields**: name, email, phone, address *(age field removed in latest version)*
- **Real-time Validation**: Tracks completion status for each field
- **Progressive Highlighting**: Visual guidance through form completion
- **Missing Field Detection**: Automatic prompts for incomplete information

### Enhanced Features
- **Comprehensive Logging**: Debug-level logging to `speech_to_form.log`
- **Health Check**: `/health` endpoint for monitoring system status
- **Reset Functionality**: Clean form state reset with field re-highlighting
- **Error Recovery**: Graceful handling of API failures and network issues

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main application interface |
| `/process_speech` | POST | Process voice input and extract form data |
| `/reset_form` | POST | Reset form to initial state |
| `/health` | GET | System health check and OpenAI connectivity status |

## Customization

### Adding New Form Fields
1. Update `REQUIRED_FIELDS` dictionary in `app.py`
2. Add corresponding HTML input fields in `templates/index.html`
3. Update the field highlighting logic in JavaScript
4. Modify extraction patterns (regex or OpenAI prompt)

### Switching AI Providers
Replace the `extract_information` method in the `FormProcessor` class with your preferred AI service integration.

### Customizing Speech Patterns
Modify the regex patterns in the `_demo_extraction` method to handle your specific speech variations or language requirements.

### Styling and UI
- Modify CSS in `templates/index.html` for visual customization
- Update field highlighting styles via `.field-highlight` class
- Customize status messages and user guidance text

## Security Considerations

For production deployment, implement:
- **Input Validation**: Sanitize and validate all user inputs
- **Rate Limiting**: Protect API endpoints from abuse
- **API Key Security**: Use environment variables and secure key management
- **HTTPS**: Required for microphone access in production
- **Authentication**: Add user authentication for sensitive applications
- **Content Security Policy**: Prevent XSS attacks
- **Logging Security**: Ensure logs don't contain sensitive information

## Troubleshooting

### Speech Recognition Issues
- **Not Working**: Ensure you're using a supported browser (Chrome, Edge, Safari)
- **No Permission**: Check microphone permissions in browser settings
- **HTTPS Required**: Microphone access requires HTTPS in production environments
- **Network Issues**: Check internet connection for real-time processing

### OpenAI API Issues
- **Invalid API Key**: Verify your OpenAI API key in `.env` file
- **Quota Exceeded**: Check your OpenAI account billing and usage limits
- **Model Unavailable**: App automatically falls back to GPT-3.5-turbo, then regex
- **Network Timeout**: App gracefully switches to offline regex extraction

### Form and UI Issues
- **Fields Not Highlighting**: Check browser console for JavaScript errors
- **Form Not Updating**: Verify Flask server is running and responding
- **Extraction Failures**: Review logs in `speech_to_form.log` for debugging

### Debugging Tools
- **Log Files**: Check `speech_to_form.log` for detailed processing information
- **Health Check**: Visit `/health` endpoint to verify system status
- **Browser Console**: Monitor for JavaScript errors and network issues
- **Network Tab**: Inspect API requests and responses in browser dev tools

## Dependencies

```txt
Flask==2.3.3
openai==1.3.0
python-dotenv==1.0.0
```

## Browser Compatibility

| Browser | Support Level | Notes |
|---------|---------------|-------|
| Chrome | Excellent | Full Web Speech API support |
| Edge | Excellent | Full Web Speech API support |
| Safari | Good | Web Speech API supported |
| Firefox | Limited | May require additional configuration |
| IE | Not Supported | Use modern browser |

## Recent Updates

- **Field Highlighting**: Added step-by-step visual guidance
- **Email Intelligence**: Improved speech-to-email conversion patterns
- **Enhanced Logging**: Comprehensive debug logging throughout application
- **Age Field Removal**: Simplified form to essential fields only
- **Error Recovery**: Better handling of API failures and network issues
- **Health Monitoring**: Added system health check endpoint
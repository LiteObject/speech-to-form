# Voice-Enabled Form Demo Application

This is a Flask web application that demonstrates voice-enabled form filling using speech recognition and AI text processing.

## Features

- **Web Form**: Simple form with fields for name, email, phone, age, and address
- **Speech Recognition**: Uses browser's Web Speech API to capture audio input
- **AI Processing**: Simulates OpenAI text processing to extract structured information
- **Missing Information Handling**: Automatically detects missing fields and requests them
- **Real-time Updates**: Form fields update in real-time as information is extracted

## Setup Instructions

### 1. Project Structure
Create the following directory structure:
```
voice-form-app/
├── app.py
├── requirements.txt
├── templates/
│   └── index.html
└── .env (optional)
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. OpenAI API Setup (Optional)
If you want to use real OpenAI processing instead of the demo extraction:

1. Get an OpenAI API key from https://platform.openai.com/
2. Create a `.env` file in the project root:
```
OPENAI_API_KEY=your-api-key-here
```
3. Uncomment the OpenAI code in `app.py` and comment out the demo extraction

### 4. Run the Application
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## How to Use

1. **Open the Application**: Navigate to `http://localhost:5000` in your browser
2. **Grant Microphone Permission**: Allow the browser to access your microphone when prompted
3. **Start Recording**: Click "Start Recording" and speak your information
4. **Example Speech**: "My name is John Doe, my email is john@example.com, phone number is 555-123-4567, I'm 30 years old, and I live at 123 Main Street, New York"
5. **Follow Prompts**: The system will ask for any missing information
6. **View Results**: Once complete, the form will show all extracted data

## Technical Details

### Speech Recognition
- Uses Web Speech API (supported in Chrome, Edge, Safari)
- Continuous recognition with interim results
- Automatic error handling and recovery

### AI Processing
- **Demo Mode**: Uses regex patterns to extract information
- **OpenAI Mode**: Uses GPT models for more accurate extraction
- Structured JSON output for form field mapping

### Form Validation
- Tracks required fields: name, email, phone, age, address
- Automatically detects missing information
- Provides natural language prompts for missing data

### Browser Compatibility
- **Best Support**: Chrome, Edge, Safari
- **Limited Support**: Firefox (may require additional setup)
- **Not Supported**: Internet Explorer

## Customization

### Adding New Fields
1. Update `REQUIRED_FIELDS` in `app.py`
2. Add corresponding HTML input fields
3. Update the extraction logic (regex patterns or OpenAI prompt)

### Changing AI Processing
Replace the `extract_information` method in the `FormProcessor` class with your preferred AI service or processing logic.

### Styling
Modify the CSS in `templates/index.html` to match your design requirements.

## Security Considerations

For production use, consider:
- Input validation and sanitization
- Rate limiting for API calls
- Secure API key management
- HTTPS for microphone access
- User authentication if needed

## Troubleshooting

### Speech Recognition Not Working
- Ensure you're using a supported browser
- Check microphone permissions
- Verify HTTPS connection (required for production)

### OpenAI API Issues
- Verify API key is correctly set
- Check API quota and billing
- Review OpenAI API documentation for updates

### Form Not Updating
- Check browser console for JavaScript errors
- Verify Flask server is running
- Ensure proper JSON response format
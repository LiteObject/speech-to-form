"""
Speech-to-Form Flask Application

A web application that processes speech input and extracts structured information
to automatically fill form fields using natural language processing.
"""

import json
import re
import os
import logging
from datetime import datetime

import openai
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('speech_to_form.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Sample form fields that need to be filled
REQUIRED_FIELDS = {
    'name': 'Full name',
    'email': 'Email address',
    'phone': 'Phone number',
    'address': 'Address'
}


class FormProcessor:
    """
    A class to process and manage form data extraction from natural language input.

    This class handles the extraction of structured information from user speech/text input,
    tracks form completion status, and manages missing field detection.

    Attributes:
        form_data (dict): Dictionary containing extracted form field values
        missing_fields (list): List of field names that still need to be filled
    """

    def __init__(self):
        """
        Initialize the FormProcessor with empty form data and all required fields as missing.
        """
        self.form_data = {}
        self.missing_fields = list(REQUIRED_FIELDS.keys())
        logger.info(
            "FormProcessor initialized with required fields: %s", self.missing_fields)

    def extract_information(self, user_input):
        """
        Extract structured information from user input using OpenAI (or demo simulation).

        Args:
            user_input (str): Raw text input from the user containing form information

        Returns:
            dict: Dictionary containing extracted field values (e.g., {'name': 'John', 'email': 'john@email.com'})
        """
        logger.info(
            "Starting information extraction for input: '%s'", user_input)
        logger.debug("API key configured: %s", bool(openai.api_key))
        logger.debug(
            "API key valid (not placeholder): %s", openai.api_key != 'your-actual-openai-api-key-here' if openai.api_key else False)

        prompt = f"""
        Extract the following information from the user's input and return as a JSON object:
        - name: full name (string)
        - email: email address (string)
        - phone: phone number (string)
        - address: full address (string)

        User input: "{user_input}"

        Return a JSON object with only the fields that are mentioned. If a field is not mentioned, do not include it in the response.

        Example response format: {{"name": "John Doe", "email": "john@example.com"}}
        """

        logger.debug("Generated prompt: %s", prompt)

        try:
            # Try OpenAI first if API key is available
            if openai.api_key and openai.api_key != "your-actual-openai-api-key-here":
                logger.info("Attempting OpenAI extraction with valid API key")
                from openai import OpenAI
                client = OpenAI(api_key=openai.api_key)

                # Try GPT-4o Mini first, fallback to GPT-3.5-turbo if needed
                models_to_try = ["gpt-4o-mini", "gpt-3.5-turbo"]
                logger.debug("Models to try: %s", models_to_try)
                response = None

                for model in models_to_try:
                    try:
                        logger.info(
                            "Attempting OpenAI request with model: %s", model)
                        response = client.chat.completions.create(
                            model=model,
                            messages=[
                                {
                                    "role": "system",
                                    "content": "You are a helpful assistant that extracts structured information from natural language and returns it as valid JSON. Only return the JSON object, no additional text or formatting."
                                },
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.1,  # Lower temperature for more consistent results
                            max_tokens=150,   # Reduced since we only need JSON
                            # Ensure JSON response
                            response_format={"type": "json_object"}
                        )

                        # If we get here, the request was successful
                        logger.info(
                            "Successfully used OpenAI model: %s", model)
                        logger.debug("Response received: %s", response)
                        break

                    except openai.OpenAIError as model_error:
                        logger.warning("Model %s failed with OpenAIError: %s",
                                       model, model_error)
                        if model == models_to_try[-1]:
                            logger.error(
                                "All OpenAI models failed. Last error: %s", model_error)
                            raise model_error
                        continue
                    except ConnectionError as model_error:
                        logger.warning("Model %s failed with ConnectionError: %s",
                                       model, model_error)
                        if model == models_to_try[-1]:
                            logger.error(
                                "All OpenAI models failed. Last error: %s", model_error)
                            raise model_error
                        continue

                # Extract JSON from response
                if response:
                    logger.debug("Processing OpenAI response")
                    response_text = response.choices[0].message.content
                    logger.debug("Raw response text: '%s'", response_text)

                    if response_text:
                        response_text = response_text.strip()

                        # With JSON mode, response should already be valid JSON
                        # But we'll still handle potential markdown formatting
                        if response_text.startswith('```json'):
                            logger.debug("Removing JSON markdown formatting")
                            response_text = response_text.replace(
                                '```json', '').replace('```', '').strip()
                        elif response_text.startswith('```'):
                            logger.debug("Removing markdown formatting")
                            response_text = response_text.replace(
                                '```', '').strip()

                        logger.debug(
                            "Cleaned response text: '%s'", response_text)
                        extracted_data = json.loads(response_text)
                        logger.info(
                            "OpenAI successfully extracted: %s", extracted_data)
                        return extracted_data
                    else:
                        logger.warning(
                            "OpenAI returned empty response, using demo extraction")
                else:
                    logger.error(
                        "All OpenAI models failed, using demo extraction")
            else:
                logger.info(
                    "OpenAI API key not found or is placeholder, using demo extraction")

        except json.JSONDecodeError as e:
            logger.error(
                "JSON decode error from OpenAI response: %s, falling back to demo extraction", e)
        except (openai.OpenAIError, ConnectionError, json.JSONDecodeError) as e:
            logger.error(
                "Error with OpenAI extraction: %s, falling back to demo extraction", e)

        # Fallback to demo extraction
        logger.info("Using demo extraction as fallback")
        extracted_data = self._demo_extraction(user_input)
        logger.info("Demo extraction completed: %s", extracted_data)
        return extracted_data

    def _demo_extraction(self, user_input):
        """
        Demo extraction function that simulates OpenAI processing using regex patterns.

        This method uses regular expressions to extract common form fields from natural
        language input. It's designed as a fallback when OpenAI API is not available.

        Args:
            user_input (str): Raw text input from the user

        Returns:
            dict: Dictionary containing extracted field values
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
                extracted['name'] = match.group(1).strip().title()
                logger.info(
                    "Name extracted: '%s' using pattern: %s", extracted['name'], pattern)
                break
        else:
            logger.debug("No name pattern matched")

        # Extract email
        logger.debug("Attempting email extraction")
        # Handle both standard email format and speech-to-text variations
        email_patterns = [
            # Standard email
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            # "email john at example.com" (already has .com)
            r'email\s+([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?=\s|$)',
            # "email john at example com" (needs .com added)
            r'email\s+([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+)(?!\.[A-Za-z])(?=\s|$)',
            # "john at example.com" (already has .com)
            r'([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?=\s|$)',
            # "john at example com" (needs .com added)
            r'([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+)(?!\.[A-Za-z])(?=\s|$)',
        ]

        for pattern in email_patterns:
            email_match = re.search(pattern, user_input, re.IGNORECASE)
            if email_match:
                if len(email_match.groups()) == 2:  # Speech format
                    local = email_match.group(1).replace(' ', '').lower()
                    domain = email_match.group(2).replace(' ', '').lower()
                    if '.' in domain:  # Already has extension
                        extracted['email'] = f"{local}@{domain}"
                    else:  # Needs .com added
                        extracted['email'] = f"{local}@{domain}.com"
                else:  # Standard format
                    extracted['email'] = email_match.group(
                        0).replace(' ', '').lower()
                logger.info(
                    "Email extracted: '%s' using pattern: %s", extracted['email'], pattern)
                break
        else:
            logger.debug("No email pattern matched")

        # Extract phone
        logger.debug("Attempting phone extraction")
        phone_patterns = [
            # Standard format with separators
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            r'phone\s+(\d{9,10})\b',  # "phone 555123467" or "phone 5551234567"
            r'\b(\d{10})\b',  # Just 10 consecutive digits
            r'\b(\d{9})\b',   # Just 9 consecutive digits (like your case)
            r'\b(\d{3})\s*(\d{3})\s*(\d{4})\b',  # Separated by spaces
        ]

        for pattern in phone_patterns:
            phone_match = re.search(pattern, user_input)
            if phone_match:
                if len(phone_match.groups()) == 3:  # Format: "555 123 4567"
                    extracted['phone'] = f"{phone_match.group(1)}-{phone_match.group(2)}-{phone_match.group(3)}"
                elif len(phone_match.groups()) == 1:  # Format: "5551234567" or "555123467"
                    phone_num = phone_match.group(1)
                    if len(phone_num) == 10:
                        extracted['phone'] = f"{phone_num[:3]}-{phone_num[3:6]}-{phone_num[6:]}"
                    elif len(phone_num) == 9:
                        # Assume first 3 are area code, next 3 are prefix, last 3 are suffix (missing 1 digit)
                        extracted['phone'] = f"{phone_num[:3]}-{phone_num[3:6]}-{phone_num[6:]}"
                    else:
                        extracted['phone'] = phone_num
                else:  # Already formatted
                    extracted['phone'] = phone_match.group(0)
                logger.info(
                    "Phone extracted: '%s' using pattern: %s", extracted['phone'], pattern)
                break
        else:
            logger.debug("No phone pattern matched")

        # Extract address (look for street, city patterns)
        logger.debug("Attempting address extraction")
        address_patterns = [
            r"live at ([^,]+(?:,\s*[^,]+)*)",
            r"address[:\s]*([^,]+(?:,\s*[^,]+)*)",
            r"my address is ([^,]+(?:,\s*[^,]+)*)"
        ]
        for pattern in address_patterns:
            match = re.search(pattern, text)
            if match:
                extracted['address'] = match.group(1).strip()
                logger.info(
                    "Address extracted: '%s' using pattern: %s", extracted['address'], pattern)
                break
        else:
            logger.debug("No address pattern matched")

        logger.info("Demo extraction completed with: %s", extracted)
        return extracted

    def update_form_data(self, extracted_data):
        """
        Update the internal form data with newly extracted information.

        This method merges extracted field values into the existing form data
        and removes fields from the missing fields list when they are filled.

        Args:
            extracted_data (dict): Dictionary containing extracted field values
        """
        logger.info("Updating form data with: %s", extracted_data)
        logger.debug("Current form data before update: %s", self.form_data)
        logger.debug("Missing fields before update: %s", self.missing_fields)

        for field, value in extracted_data.items():
            if field in REQUIRED_FIELDS and value:
                old_value = self.form_data.get(field)
                self.form_data[field] = value
                if field in self.missing_fields:
                    self.missing_fields.remove(field)
                    logger.info(
                        "Field '%s' filled with value: '%s' (was missing)", field, value)
                else:
                    logger.info(
                        "Field '%s' updated from '%s' to '%s'", field, old_value, value)
            else:
                if field not in REQUIRED_FIELDS:
                    logger.warning(
                        "Extracted field '%s' is not a required field", field)
                if not value:
                    logger.warning(
                        "Extracted field '%s' has empty value", field)

        logger.info("Form data after update: %s", self.form_data)
        logger.info("Missing fields after update: %s", self.missing_fields)

    def get_missing_fields_message(self):
        """
        Generate a user-friendly message requesting missing form information.

        Creates a natural language prompt asking the user to provide any
        remaining required fields that haven't been filled yet.

        Returns:
            str or None: Formatted message requesting missing fields, or None if form is complete
        """
        if not self.missing_fields:
            return None

        missing_labels = [REQUIRED_FIELDS[field]
                          for field in self.missing_fields]

        if len(missing_labels) == 1:
            return f"I still need your {missing_labels[0]}. Please provide it."
        elif len(missing_labels) == 2:
            return f"I still need your {missing_labels[0]} and {missing_labels[1]}. Please provide them."
        else:
            return f"I still need your {', '.join(missing_labels[:-1])}, and {missing_labels[-1]}. Please provide them."

    def is_complete(self):
        """
        Check if all required form fields have been filled.

        Returns:
            bool: True if all required fields are complete, False otherwise
        """
        return len(self.missing_fields) == 0


# Global form processor instance
form_processor = FormProcessor()


@app.route('/')
def index():
    """
    Render the main application page.

    Returns:
        str: Rendered HTML template for the main interface
    """
    return render_template('index.html')


@app.route('/process_speech', methods=['POST'])
def process_speech():
    """
    Process speech input and extract form information.

    Accepts JSON data containing transcribed speech text, extracts structured
    information using the FormProcessor, and returns the current form status
    along with any missing field prompts.

    Expected JSON payload:
        {
            "text": "My name is John Doe and my email is john@example.com"
        }

    Returns:
        JSON response containing:
        - success (bool): Whether processing was successful
        - complete (bool): Whether all form fields are filled
        - message (str): Status message or prompt for missing fields
        - form_data (dict): Current form data
        - missing_fields (list): List of still-missing field names (if incomplete)
    """
    logger.info("=== Processing speech request ===")
    try:
        data = request.get_json()
        logger.debug("Received request data: %s", data)
        user_input = data.get('text', '') if data else ''
        logger.info("User input received: '%s'", user_input)

        if not user_input:
            logger.warning("No text provided in request")
            return jsonify({
                'success': False,
                'message': 'No text provided'
            })        # Extract information using OpenAI (with fallback to demo)
        extracted_data = form_processor.extract_information(user_input)
        logger.info("Extraction completed: %s", extracted_data)

        # Determine which extraction method was used based on actual API key validity
        extraction_method = "OpenAI" if (
            openai.api_key and openai.api_key != "your-actual-openai-api-key-here") else "Demo"
        logger.info("Extraction method used: %s", extraction_method)

        # Update form data
        form_processor.update_form_data(extracted_data)

        # Check if form is complete
        is_complete = form_processor.is_complete()
        logger.info("Form completion status: %s", is_complete)

        if is_complete:
            response = {
                'success': True,
                'complete': True,
                'message': 'Form completed successfully!',
                'form_data': form_processor.form_data,
                'extraction_method': extraction_method
            }
            logger.info("Form completed successfully")
        else:
            missing_message = form_processor.get_missing_fields_message()
            response = {
                'success': True,
                'complete': False,
                'message': missing_message,
                'form_data': form_processor.form_data,
                'missing_fields': form_processor.missing_fields,
                'extraction_method': extraction_method
            }
            logger.info(
                "Form incomplete. Missing: %s", form_processor.missing_fields)

        logger.debug("Sending response: %s", response)
        return jsonify(response)

    except Exception as e:
        logger.error("Error in process_speech: %s", str(e), exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error processing speech: {str(e)}'
        })


@app.route('/reset_form', methods=['POST'])
def reset_form():
    """
    Reset the form to start over with a fresh FormProcessor instance.

    Clears all form data and resets the missing fields list to include
    all required fields.

    Returns:
        JSON response containing:
        - success (bool): Always True for successful reset
        - message (str): Confirmation message
    """
    logger.info("=== Form reset requested ===")
    global form_processor
    logger.debug("Form data before reset: %s", form_processor.form_data)
    logger.debug(
        "Missing fields before reset: %s", form_processor.missing_fields)

    form_processor = FormProcessor()
    logger.info("Form processor reset successfully")

    return jsonify({'success': True, 'message': 'Form reset successfully'})


@app.route('/health', methods=['GET'])
def health_check():
    """
    Check the health of the application and OpenAI connectivity.

    Returns:
        JSON response with system status
    """
    logger.info("=== Health check requested ===")
    status = {
        'app_status': 'running',
        'openai_configured': bool(openai.api_key),
        'timestamp': datetime.now().isoformat()
    }
    logger.debug("Initial status: %s", status)

    if openai.api_key and openai.api_key != "your-actual-openai-api-key-here":
        logger.info("Testing OpenAI connectivity")
        try:
            # Test OpenAI connection with a simple request
            from openai import OpenAI
            client = OpenAI(api_key=openai.api_key)

            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'OK'"}],
                max_tokens=5
            )
            status['openai_status'] = 'connected'
            logger.info("OpenAI connectivity test successful")
        except openai.OpenAIError as e:
            status['openai_status'] = f'openai_error: {str(e)}'
            logger.error("OpenAI API error during connectivity test: %s", e)
        except ConnectionError as e:
            status['openai_status'] = f'connection_error: {str(e)}'
            logger.error(
                "Connection error during OpenAI connectivity test: %s", e)
        except Exception as e:
            status['openai_status'] = f'unknown_error: {str(e)}'
            logger.error(
                "Unknown error during OpenAI connectivity test: %s", e)
    else:
        status['openai_status'] = 'no_api_key'
        logger.warning("No valid OpenAI API key configured")

    logger.debug("Final health status: %s", status)
    return jsonify(status)


if __name__ == '__main__':
    logger.info("=== Starting Speech-to-Form Flask Application ===")
    logger.info("OpenAI API key configured: %s", bool(openai.api_key))
    logger.info("Required fields: %s", list(REQUIRED_FIELDS.keys()))
    logger.info("Application starting on http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)

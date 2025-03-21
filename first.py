import logging
import os
from flask import Flask, request, jsonify
import requests
from PIL import Image
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.error("OCR library not available. Install 'pytesseract' using 'pip install pytesseract'.")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure retry mechanism for API requests
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# Default home route to prevent 404 errors
@app.route('/')
def home():
    return jsonify({'message': 'Welcome to the AI Stock & Crypto Tool API!'}), 200

# Endpoint to extract text from an uploaded screenshot
@app.route('/extract-text', methods=['POST'])
def extract_text():
    if not OCR_AVAILABLE:
        logger.error("OCR library not available")
        return jsonify({'error': "OCR library not available. Install 'pytesseract'."}), 500
    
    if 'file' not in request.files:
        logger.warning("No file uploaded")
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    try:
        image = Image.open(file)
    except Exception as e:
        logger.error(f"Error opening image file: {e}")
        return jsonify({'error': 'Invalid image file'}), 400
    
    try:
        extracted_text = pytesseract.image_to_string(image, config='--psm 6 --oem 3')
        logger.info("OCR extraction successful")
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return jsonify({'error': 'OCR extraction failed', 'details': str(e)}), 500
    
    return jsonify({'extracted_text': extracted_text})

# Endpoint to fetch stock data from Alpha Vantage
@app.route('/stock-data', methods=['GET'])
def get_stock_data():
    symbol = request.args.get('symbol')
    if not symbol:
        return jsonify({'error': 'Stock symbol is required'}), 400
    
    api_key = os.getenv('ALPHAVANTAGE_API_KEY')
    if not api_key:
        logger.error("API key not set")
        return jsonify({'error': 'API key is missing. Set it as an environment variable or in a .env file.'}), 500
    
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=5min&apikey={api_key}'
    
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or "Time Series" not in data:
            raise ValueError("Invalid API response structure")
        logger.info(f"Successfully fetched stock data for {symbol}")
    except (requests.RequestException, ValueError) as e:
        logger.error(f"Error fetching stock data: {e}")
        return jsonify({'error': str(e)}), 500
    
    return jsonify(data)

if __name__ == '__main__':
    debug_mode = bool(os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes'])
    flask_host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    flask_port = os.getenv('FLASK_RUN_PORT', '5000')
    
    try:
        flask_port = int(flask_port)
    except ValueError:
        logger.error("Invalid port number")
        flask_port = 5000
    
    logger.info("Starting Flask application")
    try:
        app.run(host=flask_host, port=flask_port, debug=debug_mode)
    except SystemExit as e:
        logger.error(f"Flask application failed to start: {e}")

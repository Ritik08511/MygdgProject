from flask import Flask, render_template, request, jsonify
import logging
from datetime import datetime, timedelta
from route_finder import find_routes, print_routes  
from train_availability_scraper import scrape_train_data
from train_route_scraper import scrape_train_routes
from pyngrok import ngrok, conf
import os
import atexit
import signal
import sys
import requests
import json
import time
import re
from delay_prediction_module import TrainDelayPredictor, enhance_routes_with_predictions
from flask_cors import CORS
from orchestrator import TrainAnalysisDriver  # Import orchestrator

# Constants
NGROK_AUTH_TOKEN = "2s8AbCxwpLLc5wO0kEKsl1VaXGA_57VcrKmDYQuHdpheaigPJ"
AZURE_SPEECH_KEY = "4KKeuEtS2afH6xalV7mHMIrYngmODCXfW6Vgjiv57lsz2kCXzhabJQQJ99BCACYeBjFXJ3w3AAAYACOGSdmp"
AZURE_SPEECH_REGION = "eastus"

# Azure Language Service configuration
AZURE_LANGUAGE_KEY = "70366kZzATdU6OnYaDOerEKvZBpYIWGr9KWAOJbLsxdQwnnTwSi2JQQJ99BCACYeBjFXJ3w3AAAaACOGmzh8"
AZURE_LANGUAGE_ENDPOINT = "https://nlptrain.cognitiveservices.azure.com/language/analyze-text/jobs?api-version=2024-11-15-preview"
AZURE_LANGUAGE_PROJECT = "trainner"
AZURE_LANGUAGE_DEPLOYMENT = "train-booking-deployment"

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "OPTIONS"]
    }
})

# Global variable to store ngrok tunnel
tunnel = None

def cleanup_ngrok():
    """Cleanup function to kill ngrok process"""
    global tunnel
    if tunnel:
        try:
            ngrok.disconnect(tunnel.public_url)
        except:
            pass
    ngrok.kill()

def init_ngrok():
    """Initialize and start ngrok tunnel"""
    global tunnel
    
    try:
        # Clean up any existing ngrok processes
        cleanup_ngrok()
        
        # Configure ngrok
        conf.get_default().auth_token = NGROK_AUTH_TOKEN
        conf.get_default().region = 'us'
        
        # Set up the tunnel
        tunnel = ngrok.connect(
            addr=5000,
            proto='http',
            bind_tls=True
        )
        
        print(f"\n * Ngrok tunnel established successfully")
        print(f" * Public URL: {tunnel.public_url}")
        return tunnel
        
    except Exception as e:
        print(f"Error setting up ngrok: {str(e)}")
        return None

def signal_handler(sig, frame):
    """Handle cleanup on system signals"""
    cleanup_ngrok()
    sys.exit(0)

# Set up the credentials path
CREDENTIALS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "keys",
    "fast-tensor-455801-h0-7c50fd901145.json"
)

# Set the environment variable for Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH

# Verify credentials file exists
if not os.path.exists(CREDENTIALS_PATH):
    raise FileNotFoundError(f"Credentials file not found at: {CREDENTIALS_PATH}")

# NER Functions
def extract_booking_details(query):
    """
    Extract booking details from a natural language query using Azure Language Service
    """
    # Prepare the request headers
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": AZURE_LANGUAGE_KEY
    }
    
    # Prepare the request body
    body = {
        "analysisInput": {
            "documents": [
                {
                    "id": "1",
                    "text": query
                }
            ]
        },
        "tasks": [
            {
                "kind": "CustomEntityRecognition",
                "parameters": {
                    "projectName": AZURE_LANGUAGE_PROJECT,
                    "deploymentName": AZURE_LANGUAGE_DEPLOYMENT
                }
            }
        ]
    }
    
    # Submit the analysis job
    response = requests.post(AZURE_LANGUAGE_ENDPOINT, headers=headers, json=body)
    
    if response.status_code == 202:  # Accepted
        # Get the operation location for polling
        operation_location = response.headers["Operation-Location"]
        
        # Poll until the job is complete
        while True:
            poll_response = requests.get(operation_location, headers={"Ocp-Apim-Subscription-Key": AZURE_LANGUAGE_KEY})
            poll_result = poll_response.json()
            
            if poll_result["status"] == "succeeded":
                # Extract the results from the correct path in the response
                results = poll_result["tasks"]["items"][0]["results"]
                break
            elif poll_result["status"] == "failed":
                raise Exception(f"Analysis failed: {poll_result.get('error', {}).get('message', 'Unknown error')}")
            
            # Wait before polling again
            time.sleep(1)
        
        # Extract entities
        booking_details = {
            "origin": None, 
            "destination": None, 
            "journey_date": None,
            "journey_date_text": None,
            "formatted_date": None
        }
        
        for document in results["documents"]:
            for entity in document["entities"]:
                if entity["category"] == "Origin":
                    origin_text = entity["text"]
                    formatted_origin = get_station_code_and_name(origin_text)
                    booking_details["origin"] = formatted_origin
                elif entity["category"] == "Destination":
                    dest_text = entity["text"]
                    formatted_dest = get_station_code_and_name(dest_text)
                    booking_details["destination"] = formatted_dest
                elif entity["category"] == "JourneyDate":
                    booking_details["journey_date_text"] = entity["text"]
                    booking_details["journey_date"] = parse_date_expression(entity["text"])
                    if booking_details["journey_date"]:
                        # Format the date for display (YYYY-MM-DD)
                        date_obj = datetime.strptime(booking_details["journey_date"], "%Y%m%d")
                        booking_details["formatted_date"] = date_obj.strftime("%Y-%m-%d")
        
        return booking_details
    else:
        raise Exception(f"Request failed with status code {response.status_code}: {response.text}")

def get_station_code_and_name(station_text):
    """
    Convert a station name to the format CODE_Name
    
    Args:
        station_text (str): The station name or partial name
        
    Returns:
        str: Formatted station string in the format "CODE_Name" or original text if not found
    """
    # Define your station mapping
    # This should be replaced with your actual station data
    station_mapping = {
       "yesvantpur": "YPR_Yesvantpur",
}
    
    # Normalize the input text
    normalized_text = station_text.lower().strip()
    
    # Try direct match
    if normalized_text in station_mapping:
        return station_mapping[normalized_text]
    
    # Try partial match
    for key, value in station_mapping.items():
        if normalized_text in key or key in normalized_text:
            return value
    
    # No match found
    return station_text

def parse_date_expression(date_text):
    """
    Convert various date formats to YYYYMMDD format
    """
    today = datetime.now()
    date_text = date_text.lower().strip()
    
    # Handle "today" and "tomorrow"
    if "today" in date_text:
        return today.strftime("%Y%m%d")
    elif "tomorrow" in date_text:
        return (today + timedelta(days=1)).strftime("%Y%m%d")
    
    # Handle "this [day]" and "next [day]"
    days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, 
            "friday": 4, "saturday": 5, "sunday": 6}
    
    for day, day_num in days.items():
        if day in date_text:
            current_day_num = today.weekday()
            days_ahead = 0
            
            if "next" in date_text:
                # "Next [day]" means the [day] in the following week
                days_ahead = (day_num - current_day_num) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next same day means a week later
            else:
                # "This [day]" or just "[day]" means the coming day
                days_ahead = (day_num - current_day_num) % 7
                if days_ahead == 0 and "this" not in date_text:
                    days_ahead = 7  # Next week if just the day name
            
            target_date = today + timedelta(days=days_ahead)
            return target_date.strftime("%Y%m%d")
    
    # Try to parse formatted dates
    try:
        # Try common date formats
        for fmt in ["%d %B", "%d %b", "%B %d", "%b %d", "%d/%m", "%m/%d"]:
            try:
                # Add current year if not specified
                parsed_date = datetime.strptime(date_text, fmt).replace(year=today.year)
                # If the date is in the past, it might refer to next year
                if parsed_date < today and (today - parsed_date).days > 7:
                    parsed_date = parsed_date.replace(year=today.year + 1)
                return parsed_date.strftime("%Y%m%d")
            except ValueError:
                continue
        
        # Try formats with year
        for fmt in ["%d %B %Y", "%B %d %Y", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d"]:
            try:
                parsed_date = datetime.strptime(date_text, fmt)
                return parsed_date.strftime("%Y%m%d")
            except ValueError:
                continue
                
        # Try to extract with regex
        date_match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)", date_text)
        if date_match:
            day, month = date_match.groups()
            month_names = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
            for i, m in enumerate(month_names):
                if m in month.lower()[:3]:
                    month_num = i + 1
                    parsed_date = datetime(today.year, month_num, int(day))
                    if parsed_date < today:
                        parsed_date = parsed_date.replace(year=today.year + 1)
                    return parsed_date.strftime("%Y%m%d")
    
    except Exception as e:
        print(f"Error parsing date '{date_text}': {str(e)}")
    
    # If all parsing attempts fail, return None
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Check if this is urgent mode or normal mode
            mode = request.form.get('mode', 'normal')
            
            if mode == 'urgent':
                return handle_urgent_mode(request)
            else:
                return handle_normal_mode(request)
                
        except Exception as e:
            print(f"Debug: Route processing error: {str(e)}")
            return render_template('error.html', error=str(e))
    
    return render_template('index.html')

def handle_normal_mode(request):
    """Handle normal mode routing logic"""
    origin = request.form['origin']
    destination = request.form['destination']
    date = request.form['date']
    max_routes = int(request.form['max_routes'])
    min_connection_time = int(request.form['connection_time'])
    
    date = date.replace('-', '')
    
    routes = find_routes(
        origin=origin,
        destination=destination,
        date=date,
        scrape_availability=scrape_train_data,
        scrape_routes=scrape_train_routes,
        max_routes=max_routes
    )
    
    filtered_routes = []
    for route in routes:
        valid_route = True
        if len(route['segments']) > 1:
            for i in range(len(route['segments']) - 1):
                current_segment = route['segments'][i]
                next_segment = route['segments'][i + 1]
                time_diff = (next_segment['departure_time'] - current_segment['arrival_time']).total_seconds() / 60
                if time_diff < min_connection_time:
                    valid_route = False
                    break
        if valid_route:
            filtered_routes.append(route)
    
    print(f"Debug: Using credentials from: {CREDENTIALS_PATH}")
    print(f"Debug: Credentials file exists: {os.path.exists(CREDENTIALS_PATH)}")
    
    try:
        predictor = TrainDelayPredictor(
            project_id="16925727262",
            endpoint_id="1776921841160421376",
            location="us-central1"
        )
        filtered_routes = enhance_routes_with_predictions(filtered_routes, predictor)
        print("Debug: Successfully enhanced routes with predictions")
    except Exception as e:
        print(f"Debug: Error in prediction: {str(e)}")
        # Continue without predictions if there's an error
        return render_template('results.html', 
                            routes=filtered_routes, 
                            connection_time=min_connection_time,
                            error=str(e))

    return render_template('results.html', 
                        routes=filtered_routes, 
                        connection_time=min_connection_time)

def handle_urgent_mode(request):
    """Handle urgent mode using orchestrator"""
    try:
        # Extract form data
        origin = request.form['origin']
        destination = request.form['destination']
        date = request.form['date']
        max_standing_time_minutes = int(request.form['max_standing_time'])
        min_valid_routes = int(request.form['max_routes'])  # This is actually min_valid_routes based on your form
        
        # Convert date format from YYYY-MM-DD to YYYYMMDD
        date = date.replace('-', '')
        
        # Convert standing time from minutes to hours for orchestrator
        max_standing_time_hours = max_standing_time_minutes / 60.0
        
        # Default values as discussed
        max_iterations = 5
        max_candidates_per_iteration = 5
        
        print(f"Debug: Urgent mode parameters:")
        print(f"  Origin: {origin}")
        print(f"  Destination: {destination}")
        print(f"  Date: {date}")
        print(f"  Max Standing Time: {max_standing_time_minutes} minutes ({max_standing_time_hours} hours)")
        print(f"  Min Valid Routes: {min_valid_routes}")
        print(f"  Max Iterations: {max_iterations}")
        print(f"  Max Candidates Per Iteration: {max_candidates_per_iteration}")
        
        # Initialize orchestrator
        driver = TrainAnalysisDriver()
        
        # Run analysis
        result = driver.run_analysis(
            origin=origin,
            destination=destination,
            journey_date=date,
            min_valid_routes=min_valid_routes,
            max_standing_time_hours=max_standing_time_hours,
            max_iterations=max_iterations,
            max_candidates_per_iteration=max_candidates_per_iteration
        )
        
        print(f"Debug: Orchestrator result success: {result.get('success', False)}")
        print(f"Debug: Valid results count: {len(result.get('valid_results', []))}")
        
        # For now, return a simple confirmation as requested
        if result.get('success', False):
            return jsonify({
                'status': 'success',
                'message': f"Urgent mode analysis completed successfully! Found {len(result.get('valid_results', []))} valid train options.",
                'details': {
                    'total_iterations': result.get('total_iterations', 0),
                    'candidates_processed': result.get('candidates_found', 0),
                    'valid_trains_found': len(result.get('valid_results', []))
                }
            })
        else:
            return jsonify({
                'status': 'failed',
                'message': f"Urgent mode analysis failed: {result.get('message', 'Unknown error')}",
                'details': {
                    'total_iterations': result.get('total_iterations', 0),
                    'candidates_processed': result.get('candidates_found', 0),
                    'failed_trains_count': len(result.get('all_failed_trains', []))
                }
            })
            
    except Exception as e:
        print(f"Debug: Urgent mode error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error in urgent mode processing: {str(e)}"
        }), 500

# New endpoint to get Azure Speech token
@app.route('/api/get-speech-token', methods=['GET', 'OPTIONS'])
def get_speech_token():
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
        return response

    try:
        headers = {
            'Ocp-Apim-Subscription-Key': AZURE_SPEECH_KEY,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            f'https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken',
            headers=headers
        )
        
        if response.status_code == 200:
            resp = jsonify({
                'token': response.text,
                'region': AZURE_SPEECH_REGION
            })
            resp.headers.add('Access-Control-Allow-Origin', '*')
            resp.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            return resp
        else:
            return jsonify({
                'error': f'Error from Azure: {response.status_code}',
                'message': response.text
            }), 500
            
    except Exception as e:
        print(f"Error getting speech token: {str(e)}")
        return jsonify({
            'error': 'Could not retrieve token',
            'message': str(e)
        }), 500

# Add this route to proxy the Speech SDK script
@app.route('/speech-sdk-proxy', methods=['GET'])
def speech_sdk_proxy():
    try:
        response = requests.get('https://aka.ms/csspeech/jsbrowserpackageraw')
        if response.status_code == 200:
            proxy_response = app.response_class(
                response=response.content,
                status=200,
                mimetype='application/javascript'
            )
            proxy_response.headers.add('Access-Control-Allow-Origin', '*')
            return proxy_response
        else:
            return jsonify({
                'error': f'Error fetching Speech SDK: {response.status_code}'
            }), response.status_code
    except Exception as e:
        return jsonify({
            'error': f'Error proxying Speech SDK: {str(e)}'
        }), 500

# New endpoint for processing natural language queries
@app.route('/api/process-query', methods=['POST', 'OPTIONS'])
def process_query():
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response
        
    try:
        data = request.json
        query = data.get('query')
        
        if not query:
            return jsonify({"error": "No query provided"}), 400
        
        # Extract booking details using NER
        booking_details = extract_booking_details(query)
        
        return jsonify(booking_details)
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        return jsonify({"error": str(e)}), 500

def run_app():
    """Function to run the Flask app with proper cleanup"""
    # Register cleanup functions
    atexit.register(cleanup_ngrok)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize ngrok
    if init_ngrok():
        # Run the Flask app with reloader disabled
        app.run(debug=True, use_reloader=False)
    else:
        print("Failed to initialize ngrok. Exiting...")
        sys.exit(1)

if __name__ == '__main__':
    run_app()
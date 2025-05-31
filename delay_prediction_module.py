import os
import logging
from google.cloud import aiplatform

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configuration constants
PROJECT_ID = "16925727262"
ENDPOINT_ID = "1776921841160421376"
LOCATION = "us-central1"
ENDPOINT_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/endpoints/{ENDPOINT_ID}"

class TrainDelayPredictor:
    def __init__(self, project_id=PROJECT_ID, endpoint_id=ENDPOINT_ID, location=LOCATION):
        logger.debug("Initializing TrainDelayPredictor...")
        logger.debug(f"Project ID: {project_id}")
        logger.debug(f"Endpoint ID: {endpoint_id}")
        logger.debug(f"Location: {location}")
        
        # Set credentials path
        self.creds_path = self.set_credentials()
        
        try:
            # Initialize the AI Platform client
            aiplatform.init(project=project_id, location=location)
            
            # Get the endpoint
            self.endpoint = aiplatform.Endpoint(endpoint_name=ENDPOINT_NAME)
            self.is_available = True
            logger.debug("Successfully connected to ML endpoint")
        except Exception as e:
            logger.error(f"Failed to initialize ML endpoint: {str(e)}")
            print("Running in fallback mode with mock predictions")
            self.is_available = False
    
    def set_credentials(self):
        """Set up credentials for Google Cloud"""
        try:
            creds_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "keys",
                "fast-tensor-455801-h0-7c50fd901145.json"
            )
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
            logger.debug(f"Set credentials path to: {creds_path}")
            return creds_path
        except Exception as e:
            logger.error(f"Failed to set credentials: {str(e)}")
            return None
    
    def predict_delay(self, train_number: str, source_station: str, destination_station: str) -> dict:
        """
        Predict delay for a train segment
        Args:
            train_number: Train number
            source_station: Source station code (e.g., 'NDLS')
            destination_station: Destination station code (e.g., 'CPR')
        Returns:
            Dictionary with prediction results or fallback prediction if ML endpoint is unavailable
        """
        if not self.is_available:
            logger.warning("Using fallback prediction as ML endpoint is unavailable")
            return self._get_fallback_prediction()
            
        try:
            # Extract station codes if full station names are provided
            source_code = source_station.split('_')[0] if '_' in source_station else source_station
            dest_code = destination_station.split('_')[0] if '_' in destination_station else destination_station
            
            # Prepare the prediction instance with the correct field names
            instance = {
                'train_number': str(train_number),
                'origin_station': source_code,
                'destination_station': dest_code
            }
            
            logger.debug(f"Making prediction request with instance: {instance}")
            response = self.endpoint.predict(instances=[instance])
            prediction = response.predictions[0]
            
            logger.debug(f"Received prediction: {prediction}")
            
            # Process the prediction based on structure
            if isinstance(prediction, dict) and 'value' in prediction:
                return {
                    'predicted_delay': prediction['value'],
                    'min_delay': prediction.get('lower_bound', prediction['value'] - 10),
                    'max_delay': prediction.get('upper_bound', prediction['value'] + 10),
                    'confidence_level': self._calculate_confidence_level(prediction['value'])
                }
            else:
                # Handle case where prediction is directly the value
                predicted_delay = float(prediction) if not isinstance(prediction, dict) else float(prediction.get('predicted_delay', 15))
                return {
                    'predicted_delay': predicted_delay,
                    'min_delay': predicted_delay - 10,
                    'max_delay': predicted_delay + 10,
                    'confidence_level': self._calculate_confidence_level(predicted_delay)
                }
                
        except Exception as e:
            logger.error(f"Prediction error for train {train_number}: {str(e)}")
            return self._get_fallback_prediction()
    
    def _calculate_confidence_level(self, predicted_delay: float) -> str:
        """Calculate confidence level based on predicted delay"""
        if predicted_delay <= 15:
            return "HIGH"
        elif predicted_delay <= 30:
            return "MEDIUM"
        else:
            return "LOW"

    def _get_fallback_prediction(self) -> dict:
        """Provide a fallback prediction when ML endpoint is unavailable"""
        return {
            'predicted_delay': 15,
            'min_delay': 5,
            'max_delay': 25,
            'confidence_level': 'MEDIUM'
        }

def predict_train_delay(train_number, source_station, destination_station):
    """
    Function to predict train delay and print input/output
    """
    # Print input parameters
    print(f"Input parameters:")
    print(f"  Train Number: {train_number}")
    print(f"  Source Station: {source_station}")
    print(f"  Destination Station: {destination_station}")
    
    # Initialize predictor
    predictor = TrainDelayPredictor()
    
    # Get prediction
    prediction = predictor.predict_delay(train_number, source_station, destination_station)
    
    # Print prediction results
    print("\nPrediction results:")
    for key, value in prediction.items():
        print(f"  {key}: {value}")
    
    return prediction

def enhance_routes_with_predictions(routes: list, predictor: TrainDelayPredictor = None) -> list:
    """
    Add delay predictions to each route segment
    """
    if predictor is None:
        predictor = TrainDelayPredictor()
        
    for route in routes:
        for segment in route['segments']:
            # Only predict for first train in each segment
            if segment == route['segments'][0]:
                prediction = predictor.predict_delay(
                    segment['train_number'],
                    segment['from_station'],
                    segment['to_station']
                )
                
                if prediction:
                    segment['delay_prediction'] = prediction
    
    return routes

# Example usage
if __name__ == "__main__":
    try:
        # Call the function with the specified parameters
        result = predict_train_delay('20506', 'NDLS', 'CPR')
        print("\nReturned result:", result)
    except Exception as e:
        print(f"Error during prediction: {str(e)}")
import os
import logging
# from google.cloud import aiplatform  # COMMENTED OUT - Using local ML predictor instead

# Import the local ML predictor
try:
    from delayML import TrainDelayPredictor as LocalMLPredictor
    LOCAL_ML_AVAILABLE = True
    print("✅ Successfully imported local ML predictor from delayML.py")
except ImportError as e:
    LOCAL_ML_AVAILABLE = False
    print(f"❌ Failed to import delayML.py: {e}")
    print("Make sure delayML.py is in the same directory as this file")

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configuration constants (COMMENTED OUT - No longer needed)
# PROJECT_ID = "16925727262"
# ENDPOINT_ID = "1776921841160421376"
# LOCATION = "us-central1"
# ENDPOINT_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/endpoints/{ENDPOINT_ID}"

class TrainDelayPredictor:
    def __init__(self, project_id=None, endpoint_id=None, location=None):
        logger.debug("Initializing TrainDelayPredictor...")
        logger.debug("Using local ML predictor instead of Google Cloud")
        
        # Check if local ML predictor is available
        if not LOCAL_ML_AVAILABLE:
            logger.error("Local ML predictor not available - delayML.py not found")
            print("❌ delayML.py not found. Running in fallback mode with mock predictions")
            self.is_available = False
            return
        
        try:
            # Initialize the local ML predictor instead of Google Cloud
            self.local_predictor = LocalMLPredictor()
            self.is_available = True
            logger.debug("✅ Successfully initialized local ML predictor")
            print("✅ Local ML predictor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize local ML predictor: {str(e)}")
            print(f"❌ Failed to initialize local ML predictor: {e}")
            print("Running in fallback mode with mock predictions")
            self.is_available = False
        
        # COMMENTED OUT - Google Cloud initialization
        # try:
        #     # Initialize the AI Platform client
        #     aiplatform.init(project=project_id, location=location)
        #     
        #     # Get the endpoint
        #     self.endpoint = aiplatform.Endpoint(endpoint_name=ENDPOINT_NAME)
        #     self.is_available = True
        #     logger.debug("Successfully connected to ML endpoint")
        # except Exception as e:
        #     logger.error(f"Failed to initialize ML endpoint: {str(e)}")
        #     print("Running in fallback mode with mock predictions")
        #     self.is_available = False
    
    # COMMENTED OUT - Google Cloud credentials method
    # def set_credentials(self):
    #     """Set up credentials for Google Cloud"""
    #     try:
    #         creds_path = os.path.join(
    #             os.path.dirname(os.path.abspath(__file__)),
    #             "keys",
    #             "fast-tensor-455801-h0-7c50fd901145.json"
    #         )
    #         os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    #         logger.debug(f"Set credentials path to: {creds_path}")
    #         return creds_path
    #     except Exception as e:
    #         logger.error(f"Failed to set credentials: {str(e)}")
    #         return None
    
    def predict_delay(self, train_number: str, source_station: str, destination_station: str) -> dict:
        """
        Predict delay for a train segment using local ML predictor
        Args:
            train_number: Train number
            source_station: Source station code (e.g., 'NDLS')
            destination_station: Destination station code (e.g., 'CPR')
        Returns:
            Dictionary with prediction results or fallback prediction if ML predictor is unavailable
        """
        print(f"\n🔍 Making prediction for Train {train_number}: {source_station} → {destination_station}")
        
        if not self.is_available:
            logger.warning("Using fallback prediction as local ML predictor is unavailable")
            print("⚠️ Using fallback prediction - local ML predictor unavailable")
            return self._get_fallback_prediction()
            
        try:
            # Extract station codes if full station names are provided
            source_code = source_station.split('_')[0] if '_' in source_station else source_station
            dest_code = destination_station.split('_')[0] if '_' in destination_station else destination_station
            
            logger.debug(f"Making prediction request for train {train_number}: {source_code} -> {dest_code}")
            print(f"📊 Using local ML predictor for analysis...")
            
            # Use local ML predictor - ONE LINE CALL (FAST VERSION)
            predicted_delay, min_delay, max_delay, method = self.local_predictor.predict_delay(train_number, source_code, dest_code, verbose=False)
            
            logger.debug(f"Received prediction: {predicted_delay}, range: {min_delay}-{max_delay}, method: {method}")
            print(f"✅ Prediction completed using method: {method}")
            
            # Return in the same format as before
            return {
                'predicted_delay': float(predicted_delay),
                'min_delay': float(min_delay),
                'max_delay': float(max_delay),
                'confidence_level': self._calculate_confidence_level(float(predicted_delay))
            }
                
        except Exception as e:
            logger.error(f"Prediction error for train {train_number}: {str(e)}")
            print(f"❌ Prediction error: {e}")
            print("⚠️ Falling back to mock prediction")
            return self._get_fallback_prediction()
        
        # COMMENTED OUT - Original Google Cloud prediction code
        # try:
        #     # Extract station codes if full station names are provided
        #     source_code = source_station.split('_')[0] if '_' in source_station else source_station
        #     dest_code = destination_station.split('_')[0] if '_' in destination_station else destination_station
        #     
        #     # Prepare the prediction instance with the correct field names
        #     instance = {
        #         'train_number': str(train_number),
        #         'origin_station': source_code,
        #         'destination_station': dest_code
        #     }
        #     
        #     logger.debug(f"Making prediction request with instance: {instance}")
        #     response = self.endpoint.predict(instances=[instance])
        #     prediction = response.predictions[0]
        #     
        #     logger.debug(f"Received prediction: {prediction}")
        #     
        #     # Process the prediction based on structure
        #     if isinstance(prediction, dict) and 'value' in prediction:
        #         return {
        #             'predicted_delay': prediction['value'],
        #             'min_delay': prediction.get('lower_bound', prediction['value'] - 10),
        #             'max_delay': prediction.get('upper_bound', prediction['value'] + 10),
        #             'confidence_level': self._calculate_confidence_level(prediction['value'])
        #         }
        #     else:
        #         # Handle case where prediction is directly the value
        #         predicted_delay = float(prediction) if not isinstance(prediction, dict) else float(prediction.get('predicted_delay', 15))
        #         return {
        #             'predicted_delay': predicted_delay,
        #             'min_delay': predicted_delay - 10,
        #             'max_delay': predicted_delay + 10,
        #             'confidence_level': self._calculate_confidence_level(predicted_delay)
        #         }
        #         
        # except Exception as e:
        #     logger.error(f"Prediction error for train {train_number}: {str(e)}")
        #     return self._get_fallback_prediction()
    
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
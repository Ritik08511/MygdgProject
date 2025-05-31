import pandas as pd
import numpy as np
import pickle
import os
from typing import Tuple, Dict, Optional
import warnings
warnings.filterwarnings('ignore')

class TrainDelayPredictor:
    def __init__(self, csv_file: str = 'train_delays.csv', cache_file: str = 'train_delay_cache.pkl'):
        """
        Initialize the predictor with train delay data
        Uses caching to speed up initialization
        """
        self.cache_file = cache_file
        self.csv_file = csv_file
        self.data = None
        self.train_stats = {}
        self.station_pairs = {}
        
        # Try to load from cache first for instant loading
        if self.load_from_cache():
            print(f"⚡ INSTANT LOAD: Loaded cached data ({len(self.train_stats)} trains, {len(self.station_pairs)} routes)")
        else:
            print("🔄 First-time setup: Processing data and creating cache...")
            self.load_data(csv_file)
            self.build_lookups()
            self.save_to_cache()
            print(f"✅ Cache created! Next load will be instant.")
    
    def load_from_cache(self) -> bool:
        """Load preprocessed data from cache file"""
        try:
            if os.path.exists(self.cache_file):
                # Check if cache is newer than CSV file
                cache_time = os.path.getmtime(self.cache_file)
                if os.path.exists(self.csv_file):
                    csv_time = os.path.getmtime(self.csv_file)
                    if cache_time < csv_time:
                        print("🔄 CSV file is newer than cache, rebuilding...")
                        return False
                
                with open(self.cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    self.train_stats = cache_data['train_stats']
                    self.station_pairs = cache_data['station_pairs']
                    self.data = cache_data.get('data')  # Optional, for compatibility
                return True
        except Exception as e:
            print(f"⚠️ Cache load failed: {e}")
        return False
    
    def save_to_cache(self):
        """Save preprocessed data to cache file"""
        try:
            cache_data = {
                'train_stats': self.train_stats,
                'station_pairs': self.station_pairs,
                'data': self.data  # Save minimal data needed
            }
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
        except Exception as e:
            print(f"⚠️ Cache save failed: {e}")
    
    def load_data(self, csv_file: str):
        """Load CSV data or create sample data if file not found"""
        try:
            print(f"📊 Loading {csv_file}...")
            self.data = pd.read_csv(csv_file)
            print(f"✅ Loaded {len(self.data)} records from {csv_file}")
        except FileNotFoundError:
            print(f"❌ File {csv_file} not found. Creating sample data...")
            # Sample data as per your format
            sample_data = {
                'Train_Number': ['2133', '2133', '2133', '2133', '2133', '12951', '12951', '12952', '22691', '22692'],
                'Source_Station': ['BDTS', 'BDTS', 'BDTS', 'BDTS', 'BDTS', 'NZM', 'NZM', 'MMCT', 'NZM', 'MMCT'],
                'Destination_Station': ['BVI', 'VAPI', 'ST', 'BRC', 'RTM', 'MMCT', 'BRC', 'NZM', 'MMCT', 'NZM'],
                'Avg_Delay': [15, 13, 19, 30, 22, 5, 25, 8, 10, 12]
            }
            self.data = pd.DataFrame(sample_data)
            print("📝 Using sample data")
        
        # Clean and standardize data
        print("🔧 Processing data...")
        self.data['Train_Number'] = self.data['Train_Number'].astype(str).str.strip()
        self.data['Source_Station'] = self.data['Source_Station'].astype(str).str.strip().str.upper()
        self.data['Destination_Station'] = self.data['Destination_Station'].astype(str).str.strip().str.upper()
        self.data['Avg_Delay'] = pd.to_numeric(self.data['Avg_Delay'], errors='coerce')
        self.data = self.data.dropna()
    
    def build_lookups(self):
        """Build lookup dictionaries for fast predictions"""
        print("🏗️ Building lookup tables...")
        
        # Build train statistics (min/max delay for each train across all routes)
        for train_num in self.data['Train_Number'].unique():
            train_data = self.data[self.data['Train_Number'] == train_num]
            self.train_stats[train_num] = {
                'min_delay': train_data['Avg_Delay'].min(),
                'max_delay': train_data['Avg_Delay'].max(),
                'avg_delay': train_data['Avg_Delay'].mean(),
                'routes': {}
            }
            
            # Store each route's delay for this train
            for _, row in train_data.iterrows():
                route_key = f"{row['Source_Station']}_{row['Destination_Station']}"
                self.train_stats[train_num]['routes'][route_key] = row['Avg_Delay']
        
        # Build station pair statistics (for when train number doesn't match)
        for _, row in self.data.iterrows():
            route_key = f"{row['Source_Station']}_{row['Destination_Station']}"
            
            if route_key not in self.station_pairs:
                self.station_pairs[route_key] = []
            
            self.station_pairs[route_key].append(row['Avg_Delay'])
        
        # Calculate statistics for each station pair
        for route_key in self.station_pairs:
            delays = self.station_pairs[route_key]
            self.station_pairs[route_key] = {
                'delays': delays,
                'min_delay': min(delays),
                'max_delay': max(delays),
                'avg_delay': np.mean(delays),
                'count': len(delays)
            }
        
        print(f"✅ Built lookups for {len(self.train_stats)} trains and {len(self.station_pairs)} routes")
    
    def predict_delay(self, train_number: str, source_station: str, destination_station: str, verbose: bool = False) -> Tuple[float, float, float, str]:
        """
        Predict delay for given train and route (FAST VERSION)
        
        Args:
            train_number: Train number
            source_station: Source station code
            destination_station: Destination station code
            verbose: Whether to print detailed output (default: False for speed)
        
        Returns:
            (predicted_delay, min_delay, max_delay, prediction_method)
        """
        train_number = str(train_number).strip()
        source_station = str(source_station).strip().upper()
        destination_station = str(destination_station).strip().upper()
        route_key = f"{source_station}_{destination_station}"
        
        if verbose:
            print(f"\n🔍 Predicting for: Train {train_number}, {source_station} → {destination_station}")
        
        # METHOD 1: Exact match (train + route combination)
        if train_number in self.train_stats:
            train_data = self.train_stats[train_number]
            
            if route_key in train_data['routes']:
                # Found exact match!
                exact_delay = train_data['routes'][route_key]
                train_min = train_data['min_delay']
                train_max = train_data['max_delay']
                
                if verbose:
                    print(f"✅ EXACT MATCH FOUND!")
                    print(f"   🎯 Predicted Delay: {exact_delay} minutes")
                    print(f"   📊 Train {train_number} min-max range: {train_min}-{train_max} minutes")
                
                return exact_delay, train_min, train_max, "Exact Match"
        
        # METHOD 2: Route exists but different train
        if route_key in self.station_pairs:
            route_data = self.station_pairs[route_key]
            predicted_delay = route_data['avg_delay']
            min_delay = route_data['min_delay']
            max_delay = route_data['max_delay']
            
            if verbose:
                print(f"⭐ ROUTE MATCH FOUND!")
                print(f"   🛤️ Route {source_station} → {destination_station} found in database")
                print(f"   📊 Based on {route_data['count']} observations")
                print(f"   🎯 Predicted Delay: {predicted_delay:.1f} minutes")
                print(f"   📈 Route min-max range: {min_delay}-{max_delay} minutes")
            
            return predicted_delay, min_delay, max_delay, f"Similar Route ({route_data['count']} trains)"
        
        # METHOD 3: Find similar routes (same source or destination) - OPTIMIZED
        similar_delays = []
        
        # Look for routes with same source or destination station (faster lookup)
        for route in self.station_pairs:
            source_match = route.startswith(f"{source_station}_")
            dest_match = route.endswith(f"_{destination_station}")
            
            if source_match or dest_match:
                similar_delays.extend(self.station_pairs[route]['delays'])
        
        if similar_delays:
            predicted_delay = np.mean(similar_delays)
            min_delay = min(similar_delays)
            max_delay = max(similar_delays)
            
            if verbose:
                print(f"🔍 SIMILAR STATIONS FOUND!")
                print(f"   📊 Based on {len(similar_delays)} observations")
                print(f"   🎯 Predicted Delay: {predicted_delay:.1f} minutes")
                print(f"   📈 Range: {min_delay}-{max_delay} minutes")
            
            return predicted_delay, min_delay, max_delay, f"Similar Stations ({len(similar_delays)} observations)"
        
        # METHOD 4: Overall dataset average (fallback) - CACHED
        if not hasattr(self, '_overall_stats'):
            if self.data is not None:
                self._overall_stats = {
                    'avg': self.data['Avg_Delay'].mean(),
                    'min': self.data['Avg_Delay'].min(),
                    'max': self.data['Avg_Delay'].max()
                }
            else:
                # Use reasonable defaults if no data
                self._overall_stats = {'avg': 15.0, 'min': 5.0, 'max': 60.0}
        
        overall_avg = self._overall_stats['avg']
        overall_min = self._overall_stats['min']
        overall_max = self._overall_stats['max']
        
        if verbose:
            print(f"❓ NO SIMILAR DATA FOUND")
            print(f"   🌐 Using overall dataset statistics")
            print(f"   🎯 Predicted Delay: {overall_avg:.1f} minutes")
            print(f"   📈 Dataset range: {overall_min}-{overall_max} minutes")
        
        return overall_avg, overall_min, overall_max, "Dataset Average"
    
    def get_train_info(self, train_number: str) -> Optional[Dict]:
        """Get information about a specific train"""
        train_number = str(train_number).strip()
        if train_number in self.train_stats:
            return self.train_stats[train_number]
        return None
    
    def get_route_info(self, source_station: str, destination_station: str) -> Optional[Dict]:
        """Get information about a specific route"""
        route_key = f"{source_station.upper().strip()}_{destination_station.upper().strip()}"
        if route_key in self.station_pairs:
            return self.station_pairs[route_key]
        return None
    
    def clear_cache(self):
        """Clear the cache file (useful for testing or data updates)"""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                print(f"🗑️ Cache file {self.cache_file} deleted")
        except Exception as e:
            print(f"⚠️ Failed to delete cache: {e}")


def main():
    """Demo function"""
    print("🚂 TRAIN DELAY PREDICTOR (OPTIMIZED)")
    print("=" * 50)
    
    # Initialize predictor
    predictor = TrainDelayPredictor()
    
    # Test a few quick predictions
    test_cases = [
        ('20506', 'NDLS', 'CPR'),
        ('2133', 'BDTS', 'BVI'),
        ('12345', 'DEL', 'BOM')  # Non-existent case
    ]
    
    print("\n🧪 SPEED TEST:")
    import time
    
    for train, src, dst in test_cases:
        start_time = time.time()
        result = predictor.predict_delay(train, src, dst, verbose=False)
        end_time = time.time()
        
        print(f"⚡ Train {train} ({src}→{dst}): {result[0]:.1f}min | Method: {result[3]} | Time: {(end_time-start_time)*1000:.1f}ms")
    
    print("\n💡 Enter: <train_number> <source_station> <destination_station>")
    print("   Example: 2133 BDTS BVI")
    print("   Type 'quit' to exit, 'clear' to clear cache\n")
    
    while True:
        try:
            user_input = input("Enter prediction query: ").strip()
            
            if user_input.lower() == 'quit':
                break
            elif user_input.lower() == 'clear':
                predictor.clear_cache()
                continue
            
            parts = user_input.split()
            if len(parts) >= 3:
                train_number = parts[0]
                source_station = parts[1]
                destination_station = parts[2]
                
                # Get prediction with timing
                start_time = time.time()
                predicted_delay, min_delay, max_delay, method = predictor.predict_delay(
                    train_number, source_station, destination_station, verbose=True
                )
                end_time = time.time()
                
                # Display results
                print(f"\n🎯 PREDICTION SUMMARY:")
                print(f"   🚂 Train: {train_number}")
                print(f"   🛤️ Route: {source_station.upper()} → {destination_station.upper()}")
                print(f"   ⏰ Predicted Delay: {predicted_delay:.1f} minutes")
                print(f"   📊 Range: {min_delay:.1f} - {max_delay:.1f} minutes")
                print(f"   🔍 Method: {method}")
                print(f"   ⚡ Response Time: {(end_time-start_time)*1000:.1f}ms")
                print(f"   {'='*50}")
                
            else:
                print("❌ Please provide: <train_number> <source_station> <destination_station>")
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n👋 Thank you for using Train Delay Predictor!")


if __name__ == "__main__":
    main()
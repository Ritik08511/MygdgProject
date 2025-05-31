import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz
from main_scraper import scrape_complete_train_data
from mind import TrainSeatOptimizer

class Stage2Processor:
    def __init__(self, cache_file_path: str = "train_stops.json", station_groups_path: str = "station_groups.json"):
        self.cache_file_path = cache_file_path
        self.station_groups_path = station_groups_path
        self.ist_timezone = pytz.timezone('Asia/Kolkata')
        self._load_train_stops_data()
        self._load_station_groups()
        
    def _load_train_stops_data(self):
        """Load the train stops JSON data"""
        try:
            with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                self.train_stops_data = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load train stops data from {self.cache_file_path}: {e}")
            self.train_stops_data = {}
    
    def _load_station_groups(self):
        """Load the station groups mapping"""
        try:
            with open(self.station_groups_path, 'r', encoding='utf-8') as f:
                self.station_groups = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load station groups from {self.station_groups_path}: {e}")
            self.station_groups = []
    
    def get_station_group_codes(self, station_code: str) -> List[str]:
        """Get all possible station codes for a given station"""
        # Extract the actual station code from formats like "NDLS_New Delhi" or "NZM_Hazrat Nizamuddin"
        if '_' in station_code:
            station_code = station_code.split('_')[0]
        
        station_code_upper = station_code.upper()
        
        # Check if this station is part of any group
        for group in self.station_groups:
            if station_code_upper in [code.upper() for code in group]:
                return group
        
        # If not found in groups, return the original code
        return [station_code]
    
    def extract_station_code(self, station_full: str) -> str:
        """Legacy method - kept for backward compatibility"""
        if '_' in station_full:
            return station_full.split('_')[0]
        return station_full
    
    def find_actual_station_codes(self, train_number: str, user_origin: str, user_destination: str, 
                                 departure_time_from_user_origin: str) -> Tuple[Optional[str], List[str]]:
        """
        Find the actual station codes for origin and destination based on timing match.
        
        Args:
            train_number: Train number (e.g., "12286")
            user_origin: User provided origin code (e.g., "NDLS")
            user_destination: User provided destination code (e.g., "PNBE")
            departure_time_from_user_origin: Departure time from user's boarding station
            
        Returns:
            Tuple of (actual_origin_code, list_of_possible_destination_codes)
        """
        # Try different variations of train number as key
        possible_keys = [
            train_number,
            f" ({train_number}",
            f"({train_number}",
            f"{train_number})",
            f"({train_number})",
            f'"{train_number}"',
            f'" ({train_number}'
        ]
        
        train_stops = None
        for key in possible_keys:
            if key in self.train_stops_data:
                train_stops = self.train_stops_data[key]
                break
        
        if not train_stops:
            print(f"Warning: No route data found for train {train_number}")
            # Return basic codes with station group expansion for destination
            origin_fallback = self.extract_station_code(user_origin)
            destination_possibilities = self.get_station_group_codes(self.extract_station_code(user_destination))
            return origin_fallback, destination_possibilities
        
        # Find origin station by matching departure time
        actual_origin_code = None
        origin_station_index = None
        
        for i, station in enumerate(train_stops):
            station_departure = station.get('departure_time', '').strip()
            # Parse time to compare (handle formats like "15:55")
            if self._normalize_time(station_departure) == self._normalize_time(departure_time_from_user_origin):
                actual_origin_code = station.get('station_code')
                origin_station_index = i
                print(f"Matched origin: {user_origin} -> {actual_origin_code} (departure: {departure_time_from_user_origin})")
                break
        
        if not actual_origin_code:
            print(f"Warning: Could not find matching departure time {departure_time_from_user_origin} for train {train_number}")
            # Fallback to basic extraction
            actual_origin_code = self.extract_station_code(user_origin)
            origin_station_index = 0
        
        # Find destination station possibilities - look for stations after the origin
        destination_possibilities = []
        user_destination_group = self.get_station_group_codes(user_destination)
        
        print(f"Looking for destination codes: {user_destination_group} after station index {origin_station_index}")
        
        # Look for destination stations after the origin station
        for i in range(origin_station_index + 1 if origin_station_index is not None else 0, len(train_stops)):
            station = train_stops[i]
            station_code = station.get('station_code', '')
            station_name = station.get('station_name', '')
            
            # Check if this station matches any of the user's destination possibilities
            for possible_dest in user_destination_group:
                if station_code.upper() == possible_dest.upper():
                    if station_code not in destination_possibilities:
                        destination_possibilities.append(station_code)
                        print(f"Found exact match for destination: {possible_dest} -> {station_code} at {station_name}")
        
        # If no exact matches found in the route, fall back to the user input group
        if not destination_possibilities:
            print(f"Warning: No destination matches found in train route for {user_destination_group}")
            print("Available stations in route after origin:")
            for i in range(origin_station_index + 1 if origin_station_index is not None else 0, min(len(train_stops), origin_station_index + 10 if origin_station_index is not None else 10)):
                station = train_stops[i]
                print(f"  - {station.get('station_code', '')} ({station.get('station_name', '')})")
            
            destination_possibilities = user_destination_group
        
        return actual_origin_code, destination_possibilities
    
    def _normalize_time(self, time_str: str) -> str:
        """Normalize time string for comparison (e.g., '15:5' -> '15:05')"""
        if not time_str or ':' not in time_str:
            return time_str
        
        try:
            # Extract just the time part if there are additional characters
            time_part = time_str.split(',')[0].strip() if ',' in time_str else time_str.strip()
            
            if ':' in time_part:
                hour, minute = time_part.split(':')[:2]  # Take only first 2 parts
                return f"{hour.zfill(2)}:{minute.zfill(2)}"
        except Exception:
            pass
        
        return time_str
    
    def convert_date_to_day_option(self, journey_date: str) -> str:
        try:
            current_ist = datetime.now(self.ist_timezone)
            today = current_ist.date()
            tomorrow = today + timedelta(days=1)
            
            journey_date_obj = datetime.strptime(journey_date, "%Y%m%d").date()
            
            if journey_date_obj == today:
                return "today"
            elif journey_date_obj == tomorrow:
                return "tomorrow"
            else:
                return "today"
        except ValueError:
            return "today"
    
    def parse_time_duration(self, time_str: str) -> float:
        """Parse time duration string to hours (e.g., '2h 30m' -> 2.5)"""
        try:
            hours = 0
            minutes = 0
            
            time_str = time_str.strip().lower()
            
            if 'h' in time_str:
                hours_part = time_str.split('h')[0].strip()
                if hours_part.isdigit():
                    hours = int(hours_part)
            
            if 'm' in time_str:
                if 'h' in time_str:
                    minutes_part = time_str.split('h')[1].strip()
                else:
                    minutes_part = time_str
                
                minutes_part = minutes_part.replace('m', '').strip()
                if minutes_part.isdigit():
                    minutes = int(minutes_part)
            
            return hours + (minutes / 60.0)
        except Exception:
            return 0.0
    
    def minutes_to_hours_float(self, minutes: int) -> float:
        """Convert minutes to hours as float"""
        return minutes / 60.0
    
    def try_destination_analysis(self, train_number: str, actual_origin_code: str, 
                               destination_possibilities: List[str], csv_file_path: str) -> Optional[Dict]:
        """
        Try analyzing with different destination codes until one works
        """
        optimizer = TrainSeatOptimizer(csv_file_path, self.cache_file_path)
        
        for dest_code in destination_possibilities:
            try:
                print(f"   🎯 Trying destination: {dest_code}")
                
                analysis_result = optimizer.optimize_journey(
                    train_number=train_number,
                    origin=actual_origin_code,
                    destination=dest_code
                )
                
                if analysis_result and (analysis_result.get('seated_segments') or analysis_result.get('seatless_segments')):
                    print(f"   ✅ Success with destination: {dest_code}")
                    # Add the successful destination code to the result
                    analysis_result['successful_destination_code'] = dest_code
                    return analysis_result
                else:
                    print(f"   ❌ No results with destination: {dest_code}")
                    
            except Exception as e:
                print(f"   ❌ Error with destination {dest_code}: {str(e)}")
                continue
        
        print(f"   ❌ No valid destination found from possibilities: {destination_possibilities}")
        return None
    
    def analyze_candidates(self, candidates: List[Dict], origin_full: str, destination_full: str, 
                          journey_date: str, min_valid_routes: int = 1, 
                          max_standing_time_hours: float = 2.0) -> Dict:
        
        day_option = self.convert_date_to_day_option(journey_date)
        
        valid_results = []
        failed_trains = []
        
        print(f"\n🔍 Stage2: Analyzing {len(candidates)} candidates with max standing time: {max_standing_time_hours} hours")
        
        for i, candidate in enumerate(candidates):
            train_number = candidate['number']
            departure_time = candidate['departure_time_from_user_origin']
            
            print(f"\n🚂 Processing Train {train_number} ({i+1}/{len(candidates)})")
            
            try:
                # Find actual station codes based on timing match
                actual_origin_code, destination_possibilities = self.find_actual_station_codes(
                    train_number, origin_full, destination_full, departure_time
                )
                
                print(f"   Using origin: {actual_origin_code}")
                print(f"   Destination possibilities: {destination_possibilities}")
                
                scraped_data = scrape_complete_train_data(
                    train_number=train_number,
                    date_option=day_option,
                    keep_browser_open=False
                )
                
                if not scraped_data:
                    print(f"   ❌ Scraping failed")
                    failed_trains.append({
                        'train_number': train_number,
                        'departure_time': departure_time,
                        'error': 'scraping_failed'
                    })
                    continue
                
                csv_file_path = f"scraped_data/{train_number}.csv"
                
                if not os.path.exists(csv_file_path):
                    print(f"   ❌ CSV file not found: {csv_file_path}")
                    failed_trains.append({
                        'train_number': train_number,
                        'departure_time': departure_time,
                        'error': 'csv_file_not_found'
                    })
                    continue
                
                # Try different destination codes until one works
                analysis_result = self.try_destination_analysis(
                    train_number, actual_origin_code, destination_possibilities, csv_file_path
                )
                
                if not analysis_result:
                    print(f"   ❌ No seat combinations found with any destination code")
                    failed_trains.append({
                        'train_number': train_number,
                        'departure_time': departure_time,
                        'error': 'no_seat_combinations_all_destinations',
                        'tried_destinations': destination_possibilities,
                        'origin_used': actual_origin_code
                    })
                    continue
                
                successful_dest_code = analysis_result.get('successful_destination_code')
                print(f"🔍 DEBUG: analysis_result keys: {list(analysis_result.keys())}")
                print(f"🔍 DEBUG: Successful destination code: {successful_dest_code}")
                
                # FIXED: Use correct keys from mind.py TrainSeatOptimizer result
                total_standing_time_minutes = analysis_result.get('total_standing_time', 0)
                standing_percentage = analysis_result.get('standing_percentage', 0.0)
                seated_segments = analysis_result.get('seated_segments', [])
                
                # Convert minutes to hours for comparison
                standing_hours = self.minutes_to_hours_float(total_standing_time_minutes)
                num_seated_segments = len(seated_segments)
                
                print(f"   📊 Standing time: {total_standing_time_minutes} minutes ({standing_hours:.2f} hours)")
                print(f"   📊 Standing percentage: {standing_percentage:.1f}%")
                print(f"   📊 Max allowed: {max_standing_time_hours} hours")
                
                meets_standing_criteria = standing_hours <= max_standing_time_hours
                print(f"   📊 Meets criteria: {meets_standing_criteria}")
                
                if meets_standing_criteria:
                    print(f"   ✅ Train {train_number} ACCEPTED")
                    result = {
                        'train_number': train_number,
                        'departure_time': departure_time,
                        'analysis_result': analysis_result,
                        'standing_time_hours': standing_hours,
                        'standing_time_minutes': total_standing_time_minutes,
                        'standing_percentage': standing_percentage,
                        'seated_segments_count': num_seated_segments,
                        'meets_criteria': True,
                        'criteria_details': {
                            'max_standing_time_hours': max_standing_time_hours,
                            'meets_standing_criteria': meets_standing_criteria
                        },
                        'csv_file_path': csv_file_path,
                        'station_codes_used': {
                            'origin': actual_origin_code,
                            'destination': successful_dest_code,
                            'user_input_origin': origin_full,
                            'user_input_destination': destination_full,
                            'destination_possibilities_tried': destination_possibilities
                        }
                    }
                    
                    valid_results.append(result)
                    
                    # Check if we have enough valid routes
                    if len(valid_results) >= min_valid_routes:
                        print(f"\n✅ Found {len(valid_results)} valid routes (required: {min_valid_routes})")
                        return {
                            'success': True,
                            'total_candidates_processed': i + 1,
                            'total_candidates': len(candidates),
                            'valid_trains_found': len(valid_results),
                            'min_valid_routes_required': min_valid_routes,
                            'criteria_met': True,
                            'valid_results': valid_results,
                            'failed_trains': failed_trains,
                            'processing_complete': True
                        }
                else:
                    print(f"   ❌ Train {train_number} REJECTED - exceeds standing time limit")
                    failed_trains.append({
                        'train_number': train_number,
                        'departure_time': departure_time,
                        'error': 'exceeds_standing_time_limit',
                        'standing_time_hours': standing_hours,
                        'standing_time_minutes': total_standing_time_minutes,
                        'standing_time_limit': max_standing_time_hours,
                        'station_codes_used': f"{actual_origin_code} -> {successful_dest_code}",
                        'destination_possibilities_tried': destination_possibilities
                    })
                    
            except Exception as e:
                print(f"   ❌ Processing exception: {str(e)}")
                failed_trains.append({
                    'train_number': train_number,
                    'departure_time': departure_time,
                    'error': 'processing_exception',
                    'exception_details': str(e)
                })
                continue
        
        # After processing all candidates
        criteria_met = len(valid_results) >= min_valid_routes
        
        print(f"\n📊 Final Results:")
        print(f"   Valid trains found: {len(valid_results)}")
        print(f"   Min required: {min_valid_routes}")
        print(f"   Criteria met: {criteria_met}")
        
        if criteria_met:
            return {
                'success': True,
                'total_candidates_processed': len(candidates),
                'total_candidates': len(candidates),
                'valid_trains_found': len(valid_results),
                'min_valid_routes_required': min_valid_routes,
                'criteria_met': True,
                'valid_results': valid_results,
                'failed_trains': failed_trains,
                'processing_complete': True,
                'message': f"Found {len(valid_results)} valid routes out of {min_valid_routes} required"
            }
        else:
            return {
                'success': False,
                'total_candidates_processed': len(candidates),
                'total_candidates': len(candidates),
                'valid_trains_found': len(valid_results),
                'min_valid_routes_required': min_valid_routes,
                'criteria_met': False,
                'valid_results': valid_results,
                'failed_trains': failed_trains,
                'processing_complete': True,
                'message': f"Found only {len(valid_results)} valid routes, need {min_valid_routes}. All trains exceed standing time limit of {max_standing_time_hours} hours."
            }
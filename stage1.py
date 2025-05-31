import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import pytz
from train_availability_scraper import scrape_train_data
from train_route_scraper import scrape_train_routes
from train_stops_store import TrainStopsStore

class Stage1Processor:
    def __init__(self, cache_file_path: str = "train_stops.json"):
        self.cache_file_path = cache_file_path
        self.ist_timezone = pytz.timezone('Asia/Kolkata')
        self.train_stops_store = TrainStopsStore(cache_file_path)
        # Add cache for all available trains to avoid re-scraping
        self._all_trains_cache = {}
        
    def normalize_train_number(self, train_input: str) -> str:
        if not train_input:
            return ""
        match = re.search(r'\d{4,5}', str(train_input).strip())
        if match:
            return match.group()
        return str(train_input).strip()
    
    def validate_journey_date(self, date_str: str) -> bool:
        try:
            current_ist = datetime.now(self.ist_timezone)
            today = current_ist.date()
            tomorrow = today + timedelta(days=1)
            journey_date = datetime.strptime(date_str, "%Y%m%d").date()
            return journey_date in [today, tomorrow]
        except ValueError:
            return False
    
    def parse_departure_time(self, time_str: str) -> Optional[str]:
        try:
            if ',' in time_str:
                time_part = time_str.split(',')[0].strip()
            else:
                time_part = time_str.strip()
            
            if ':' in time_part and len(time_part.split(':')) == 2:
                hour, minute = time_part.split(':')
                if hour.isdigit() and minute.isdigit():
                    return f"{hour.zfill(2)}:{minute.zfill(2)}"
            return None
        except Exception:
            return None
    
    def create_datetime_from_time(self, time_str: str, base_date: datetime.date, 
                                 reference_datetime: Optional[datetime] = None) -> Optional[datetime]:
        """
        Create datetime object handling cross-day scenarios.
        If reference_datetime is provided, handles cases where the time might be next day.
        """
        try:
            hour, minute = map(int, time_str.split(':'))
            
            # Create datetime for the given date
            target_datetime = datetime.combine(
                base_date, 
                datetime.min.time().replace(hour=hour, minute=minute)
            )
            target_datetime = self.ist_timezone.localize(target_datetime)
            
            # If we have a reference datetime (like train origin departure),
            # and our target time is earlier in the day, it might be next day
            if reference_datetime and target_datetime < reference_datetime:
                # Check if adding a day makes more sense
                next_day_datetime = target_datetime + timedelta(days=1)
                
                # If the time difference suggests it's the next day (e.g., 23:00 -> 04:00)
                time_diff = (target_datetime - reference_datetime).total_seconds() / 3600
                if time_diff < -12:  # More than 12 hours earlier suggests next day
                    target_datetime = next_day_datetime
            
            return target_datetime
        except Exception:
            return None
    
    def is_train_departure_within_6hour_window(self, true_origin_departure_time: str, 
                                              journey_date: str) -> bool:
        """
        Check if train's departure from TRUE ORIGIN is within next 6 hours.
        This is the correct logic - we should check origin departure, not boarding station departure.
        """
        try:
            current_ist = datetime.now(self.ist_timezone)
            journey_date_obj = datetime.strptime(journey_date, "%Y%m%d").date()
            
            # Create departure datetime for true origin
            departure_datetime = self.create_datetime_from_time(
                true_origin_departure_time, 
                journey_date_obj
            )
            
            if not departure_datetime:
                return False
            
            # Handle cross-day scenario: if departure is "earlier" than current time
            # but it's actually tomorrow's departure
            if departure_datetime < current_ist and journey_date_obj > current_ist.date():
                departure_datetime += timedelta(days=1)
            
            six_hours_later = current_ist + timedelta(hours=6)
            
            # Train should depart between now and 6 hours from now
            return current_ist <= departure_datetime <= six_hours_later
            
        except Exception:
            return False
    
    def has_train_already_departed_from_origin(self, true_origin_departure_time: str, 
                                              journey_date: str) -> bool:
        """
        Check if train has already departed from its true origin station.
        """
        try:
            current_ist = datetime.now(self.ist_timezone)
            journey_date_obj = datetime.strptime(journey_date, "%Y%m%d").date()
            
            # Create departure datetime for true origin
            departure_datetime = self.create_datetime_from_time(
                true_origin_departure_time, 
                journey_date_obj
            )
            
            if not departure_datetime:
                return False  # If we can't parse, assume not departed
            
            # Handle cross-day scenario
            if departure_datetime < current_ist and journey_date_obj > current_ist.date():
                departure_datetime += timedelta(days=1)
            
            return current_ist > departure_datetime
            
        except Exception:
            return False
    
    def get_train_route_from_cache_or_scrape(self, train_number: str, origin: str, destination: str, date: str) -> Optional[List[Dict]]:
        normalized_train_number = self.normalize_train_number(train_number)
        
        cache_key_variations = [
            normalized_train_number,
            train_number,
            f" ({normalized_train_number}",
            f"({normalized_train_number}",
            f"{normalized_train_number})",
            f"({normalized_train_number})",
        ]
        
        for cache_key in cache_key_variations:
            cached_route = self.train_stops_store.get_stops(cache_key)
            if cached_route:
                return cached_route
        
        try:
            route_data = scrape_train_routes(origin, destination, date, target_train_number=normalized_train_number)
            
            if route_data and len(route_data) > 0 and 'stops' in route_data[0]:
                route_stops = route_data[0]['stops']
                cache_key_for_storage = f" ({normalized_train_number}"
                self.train_stops_store.add_stops(cache_key_for_storage, route_stops)
                return route_stops
                
        except Exception:
            pass
        
        alternative_approaches = [
            {"origin": origin, "destination": destination, "target_train": normalized_train_number},
            {"origin": origin, "destination": destination, "target_train": train_number},
            {"origin": origin, "destination": destination, "target_train": None}
        ]
        
        for approach in alternative_approaches:
            try:
                if approach['target_train']:
                    route_data = scrape_train_routes(
                        approach['origin'], 
                        approach['destination'], 
                        date, 
                        target_train_number=approach['target_train']
                    )
                else:
                    route_data = scrape_train_routes(approach['origin'], approach['destination'], date)
                    if route_data:
                        route_data = [train for train in route_data 
                                    if self.normalize_train_number(train.get('number', '')) == normalized_train_number]
                
                if route_data and len(route_data) > 0 and 'stops' in route_data[0]:
                    route_stops = route_data[0]['stops']
                    cache_key_for_storage = f" ({normalized_train_number}"
                    self.train_stops_store.add_stops(cache_key_for_storage, route_stops)
                    return route_stops
                    
            except Exception:
                continue
        
        return None
    
    def get_true_origin_info(self, route_stops: List[Dict]) -> Optional[Dict]:
        if not route_stops:
            return None
        return route_stops[0]
    
    def create_fallback_candidate(self, train_data: Dict, normalized_number: str) -> Dict:
        departure_time = self.parse_departure_time(train_data.get('departure_time', ''))
        
        return {
            'number': normalized_number,
            'original_number': train_data.get('number', normalized_number),
            'departure_time_from_user_origin': departure_time,
            'raw_train_data': train_data,
            'is_fallback': True,
            'fallback_reason': 'route_scraping_failed',
            'warning': f'Could not verify train {normalized_number} route - treating as valid candidate'
        }
    
    def get_all_available_trains(self, origin: str, destination: str, journey_date: str) -> List[Dict]:
        """
        Get ALL available trains and cache them to avoid re-scraping.
        This method processes all trains once and caches the result.
        """
        cache_key = f"{origin}_{destination}_{journey_date}"
        
        # Return cached result if available
        if cache_key in self._all_trains_cache:
            return self._all_trains_cache[cache_key]
        
        if not self.validate_journey_date(journey_date):
            self._all_trains_cache[cache_key] = []
            return []
        
        try:
            all_trains = scrape_train_data(origin, destination, journey_date)
            if not all_trains:
                self._all_trains_cache[cache_key] = []
                return []
        except Exception:
            self._all_trains_cache[cache_key] = []
            return []
        
        processed_trains = []
        
        for train in all_trains:
            train_number = train.get('number')
            departure_time_raw = train.get('departure_time')
            
            if not train_number or not departure_time_raw:
                continue
            
            normalized_train_number = self.normalize_train_number(train_number)
            departure_time_from_boarding = self.parse_departure_time(departure_time_raw)
            
            if not departure_time_from_boarding:
                continue
            
            # Get the complete route to find true origin
            route_stops = self.get_train_route_from_cache_or_scrape(
                train_number, origin, destination, journey_date
            )
            
            if not route_stops:
                # Fallback: if we can't get route, use boarding station departure time
                # but only if it's within 6 hours (old logic as fallback)
                if self.is_within_6hour_window_old_logic(departure_time_from_boarding, journey_date):
                    fallback_candidate = self.create_fallback_candidate(train, normalized_train_number)
                    processed_trains.append(fallback_candidate)
                continue
            
            true_origin_info = self.get_true_origin_info(route_stops)
            if not true_origin_info:
                # Same fallback as above
                if self.is_within_6hour_window_old_logic(departure_time_from_boarding, journey_date):
                    fallback_candidate = self.create_fallback_candidate(train, normalized_train_number)
                    fallback_candidate['fallback_reason'] = 'no_origin_info'
                    processed_trains.append(fallback_candidate)
                continue
            
            # Get true origin departure time
            true_origin_departure_raw = true_origin_info.get('departure_time')
            if not true_origin_departure_raw:
                continue
                
            true_origin_departure_time = self.parse_departure_time(true_origin_departure_raw)
            if not true_origin_departure_time:
                continue
            
            # Check if train has already departed from TRUE ORIGIN
            if self.has_train_already_departed_from_origin(true_origin_departure_time, journey_date):
                continue  # Skip trains that have already started their journey
            
            # Check if train will depart from TRUE ORIGIN within next 6 hours
            if self.is_train_departure_within_6hour_window(true_origin_departure_time, journey_date):
                processed_trains.append({
                    'number': normalized_train_number,
                    'original_number': train_number,
                    'departure_time_from_user_origin': departure_time_from_boarding,
                    'departure_time_from_true_origin': true_origin_departure_time,
                    'true_origin_station': true_origin_info.get('station_name', ''),
                    'raw_train_data': train
                })
        
        # Cache the result
        self._all_trains_cache[cache_key] = processed_trains
        
        # Show summary of all trains found and their departure times
        if processed_trains:
            print(f"\n🚂 FOUND {len(processed_trains)} TRAINS DEPARTING IN NEXT 6 HOURS:")
            print("=" * 55)
            for i, train in enumerate(processed_trains[:15]):  # Show first 15
                train_num = train.get('number', 'Unknown')
                true_origin_time = train.get('departure_time_from_true_origin', 'N/A')
                origin_station = train.get('true_origin_station', 'Unknown')
                boarding_time = train.get('departure_time_from_user_origin', 'N/A')
                
                print(f"{i+1:2d}. Train {train_num}")
                if true_origin_time != 'N/A':
                    print(f"    Actual Origin: {origin_station} at {true_origin_time}")
                    print(f"    Your Boarding: {boarding_time}")
                else:
                    print(f"    Departure: {boarding_time} (fallback)")
            
            if len(processed_trains) > 15:
                print(f"    ... and {len(processed_trains) - 15} more trains")
        
        return processed_trains
    
    def get_candidates(self, origin: str, destination: str, journey_date: str, 
                      exclude_train_numbers: Optional[Set[str]] = None,
                      max_candidates: int = 5) -> List[Dict]:
        """
        Get train candidates, excluding already processed trains.
        Returns trains sorted by departure time from actual origin station (earliest first).
        
        Args:
            origin: Origin station
            destination: Destination station  
            journey_date: Journey date in YYYYMMDD format
            exclude_train_numbers: Set of train numbers to exclude
            max_candidates: Maximum number of candidates to return
        
        Returns:
            List of candidate trains (up to max_candidates), sorted by departure time
        """
        if exclude_train_numbers is None:
            exclude_train_numbers = set()
        
        # Get all available trains (cached)
        all_trains = self.get_all_available_trains(origin, destination, journey_date)
        
        if not all_trains:
            return []
        
        # Filter out excluded trains
        available_trains = []
        for train in all_trains:
            train_number = train.get('number', '')
            if train_number not in exclude_train_numbers:
                available_trains.append(train)
        
        # Sort trains by departure time from actual origin station (earliest first)
        available_trains = self.sort_trains_by_departure_time(available_trains, journey_date)
        
        # Return up to max_candidates trains
        return available_trains[:max_candidates]
    
    def sort_trains_by_departure_time(self, trains: List[Dict], journey_date: str) -> List[Dict]:
        """
        Sort trains by their departure time from actual origin station (earliest first).
        
        Args:
            trains: List of train dictionaries
            journey_date: Journey date in YYYYMMDD format
            
        Returns:
            Sorted list of trains (earliest departure first)
        """
        def get_departure_datetime(train_dict: Dict) -> datetime:
            """
            Get departure datetime for sorting.
            Uses true origin departure time, falls back to boarding station time.
            """
            try:
                journey_date_obj = datetime.strptime(journey_date, "%Y%m%d").date()
                
                # Try to use true origin departure time (most accurate)
                true_origin_departure = train_dict.get('departure_time_from_true_origin')
                if true_origin_departure:
                    departure_dt = self.create_datetime_from_time(true_origin_departure, journey_date_obj)
                    if departure_dt:
                        return departure_dt
                
                # Fallback to boarding station departure time
                boarding_departure = train_dict.get('departure_time_from_user_origin')
                if boarding_departure:
                    departure_dt = self.create_datetime_from_time(boarding_departure, journey_date_obj)
                    if departure_dt:
                        return departure_dt
                
                # Last resort - use current time (will be sorted last)
                return datetime.now(self.ist_timezone)
                
            except Exception:
                # If parsing fails, use current time (will be sorted last)
                return datetime.now(self.ist_timezone)
        
        # Sort trains by departure time (earliest first)
        sorted_trains = sorted(trains, key=get_departure_datetime)
        
        # Debug logging to show the sort order
        print(f"\n🕐 TRAINS SORTED BY DEPARTURE TIME:")
        print("-" * 45)
        for i, train in enumerate(sorted_trains[:10]):  # Show first 10
            train_num = train.get('number', 'Unknown')
            true_origin_time = train.get('departure_time_from_true_origin', 'N/A')
            boarding_time = train.get('departure_time_from_user_origin', 'N/A')
            origin_station = train.get('true_origin_station', 'Unknown')
            
            departure_dt = get_departure_datetime(train)
            departure_display = departure_dt.strftime("%H:%M") if departure_dt else "N/A"
            
            print(f"{i+1:2d}. Train {train_num}: {departure_display}")
            print(f"    Origin: {origin_station} at {true_origin_time}")
            print(f"    Boarding: {boarding_time}")
        
        if len(sorted_trains) > 10:
            print(f"    ... and {len(sorted_trains) - 10} more trains")
        
        return sorted_trains
    
    def is_within_6hour_window_old_logic(self, departure_time: str, journey_date: str) -> bool:
        """Keep old logic as fallback when route scraping fails"""
        try:
            current_ist = datetime.now(self.ist_timezone)
            journey_date_obj = datetime.strptime(journey_date, "%Y%m%d").date()
            departure_hour, departure_minute = map(int, departure_time.split(':'))
            
            departure_datetime = datetime.combine(
                journey_date_obj, 
                datetime.min.time().replace(hour=departure_hour, minute=departure_minute)
            )
            departure_datetime = self.ist_timezone.localize(departure_datetime)
            six_hours_later = current_ist + timedelta(hours=6)
            
            return current_ist <= departure_datetime <= six_hours_later
        except Exception:
            return False
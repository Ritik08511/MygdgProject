import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import re

class TrainSeatOptimizer:
    def __init__(self, csv_file_path: str, json_file_path: str):
        """
        Initialize the optimizer with CSV seat data and JSON station data
        """
        self.csv_file_path = csv_file_path
        self.json_file_path = json_file_path
        self.seat_data = None
        self.station_data = None
        
        # Class preference order for upgrades (lower number = higher preference)
        self.class_preference = {
            'SLEEPER': 1,
            'THIRD AC (3E)': 2,  # AC 3E M1 M2
            'THIRD AC (3A)': 3,  # AC 3 B1 B2
            'SECOND AC (2A)': 4, # AC2
            'FIRST AC (1A)': 5   # AC1
        }
        
    def load_data(self):
        """Load CSV and JSON data"""
        # Load CSV data
        self.seat_data = pd.read_csv(self.csv_file_path)
        # Remove filter_list rows
        self.seat_data = self.seat_data[self.seat_data['from_station'] != 'filter_list']
        
        # Load JSON data
        with open(self.json_file_path, 'r') as f:
            content = f.read()
            # Parse JSON with train numbers that might have quotes and parentheses
            self.station_data = json.loads(content)
    
    def get_train_stations(self, train_number: str) -> List[Dict]:
        """Get station data for a specific train number"""
        # Handle train number formats like "15013" or " (15013"
        for key in self.station_data.keys():
            if train_number in key:
                print(f"DEBUG: Found train data with key: '{key}'")
                return self.station_data[key]
        
        print(f"DEBUG: Train {train_number} not found. Available keys: {list(self.station_data.keys())}")
        return []
    
    def get_station_sequence(self, train_number: str, origin: str, destination: str) -> List[Dict]:
        """Get ordered station sequence between origin and destination"""
        stations = self.get_train_stations(train_number)
        
        origin_idx = None
        dest_idx = None
        
        for i, station in enumerate(stations):
            if station['station_code'] == origin:
                origin_idx = i
            if station['station_code'] == destination:
                dest_idx = i
                
        if origin_idx is None or dest_idx is None:
            raise ValueError(f"Origin {origin} or destination {destination} not found in train route")
            
        if origin_idx >= dest_idx:
            raise ValueError("Origin must come before destination in train route")
            
        return stations[origin_idx:dest_idx + 1]
    
    def calculate_journey_duration(self, from_station: str, to_station: str, station_sequence: List[Dict]) -> Dict:
        """Calculate journey duration between two stations"""
        from_time = None
        to_time = None
        
        for station in station_sequence:
            if station['station_code'] == from_station:
                from_time = station['departure_time'] if station['departure_time'] != 'Start' else station['arrival_time']
            if station['station_code'] == to_station:
                to_time = station['arrival_time'] if station['arrival_time'] != 'Finish' else station['departure_time']
                
        if from_time and to_time and from_time != 'Start' and to_time != 'Finish':
            # Simple time difference calculation (assuming same day for simplicity)
            try:
                from_hr, from_min = map(int, from_time.split(':'))
                to_hr, to_min = map(int, to_time.split(':'))
                
                from_minutes = from_hr * 60 + from_min
                to_minutes = to_hr * 60 + to_min
                
                # Handle next day scenario
                if to_minutes < from_minutes:
                    to_minutes += 24 * 60
                    
                duration_minutes = to_minutes - from_minutes
                hours = duration_minutes // 60
                minutes = duration_minutes % 60
                
                return {
                    'from_time': from_time,
                    'to_time': to_time,
                    'duration_hours': hours,
                    'duration_minutes': minutes,
                    'total_minutes': duration_minutes
                }
            except:
                pass
                
        return {
            'from_time': from_time or 'Unknown',
            'to_time': to_time or 'Unknown',
            'duration_hours': 0,
            'duration_minutes': 0,
            'total_minutes': 0
        }
    
    def extract_station_code(self, station_string: str) -> str:
        """Extract station code from strings like 'JAISALMER (JSM)' or 'JSM'"""
        if '(' in station_string and ')' in station_string:
            # Extract code between parentheses
            match = re.search(r'\(([^)]+)\)', station_string)
            if match:
                return match.group(1)
        return station_string.strip()
    
    def get_seat_coverage(self, seat_row: pd.Series, origin: str, destination: str, station_sequence: List[Dict]) -> Tuple[List[str], int]:
        """Determine which stations a seat covers and calculate coverage distance"""
        from_station_raw = seat_row['from_station']
        to_station_raw = seat_row['to_station']
        
        # Extract station codes
        from_station = self.extract_station_code(from_station_raw)
        to_station = self.extract_station_code(to_station_raw)
        
        # Get station codes in sequence
        station_codes = [s['station_code'] for s in station_sequence]
        
        # Find indices
        try:
            origin_idx = station_codes.index(origin)
            dest_idx = station_codes.index(destination)
            from_idx = station_codes.index(from_station)
            to_idx = station_codes.index(to_station)
        except ValueError:
            return [], 0
            
        # Calculate effective coverage within our journey
        effective_from = max(origin_idx, from_idx)
        effective_to = min(dest_idx, to_idx)
        
        if effective_from >= effective_to:
            return [], 0
            
        covered_stations = station_codes[effective_from:effective_to + 1]
        coverage_distance = effective_to - effective_from
        
        return covered_stations, coverage_distance
    
    def calculate_seat_preference_score(self, seat_row: pd.Series, reference_seat: Optional[pd.Series] = None) -> float:
        """Calculate preference score for seat selection tie-breaking with enhanced logic"""
        score = 0.0
        
        if reference_seat is not None:
            # 1. Same coach preference (highest priority)
            if seat_row['coach'] == reference_seat['coach']:
                score += 10000  # Very high score for same coach
                
                # 2. Nearby seat number preference within same coach
                try:
                    seat_diff = abs(int(seat_row['berth_no']) - int(reference_seat['berth_no']))
                    score += max(0, 1000 - seat_diff * 10)  # Closer seats get higher score
                except:
                    pass
            else:
                # 3. Same class, nearby coach preference
                if seat_row['category'] == reference_seat['category']:
                    try:
                        # Extract coach numbers/letters for comparison
                        ref_coach = reference_seat['coach']
                        curr_coach = seat_row['coach']
                        
                        # Handle different coach naming patterns
                        if ref_coach[-1:].isalpha() and curr_coach[-1:].isalpha():
                            coach_diff = abs(ord(curr_coach[-1]) - ord(ref_coach[-1]))
                            score += max(0, 500 - coach_diff * 50)  # Nearby coaches get higher score
                        elif ref_coach[-1:].isdigit() and curr_coach[-1:].isdigit():
                            coach_diff = abs(int(curr_coach[-1]) - int(ref_coach[-1]))
                            score += max(0, 500 - coach_diff * 50)
                    except:
                        pass
                else:
                    # 4. Different class - prefer upgrade in price order
                    ref_class_pref = self.class_preference.get(reference_seat['category'], 999)
                    curr_class_pref = self.class_preference.get(seat_row['category'], 999)
                    
                    # Prefer higher class (lower preference number)
                    if curr_class_pref < ref_class_pref:
                        score += (ref_class_pref - curr_class_pref) * 100  # Upgrade bonus
                    else:
                        score += max(0, 50 - (curr_class_pref - ref_class_pref) * 10)  # Penalty for downgrade
        
        # 5. Base class preference (independent scoring)
        if seat_row['category'] in self.class_preference:
            score += (6 - self.class_preference[seat_row['category']]) * 10
        
        # 6. Berth type preference (Lower berth generally preferred)
        berth_type = str(seat_row['berth_type']).lower()
        if 'lower' in berth_type:
            score += 20
        elif 'middle' in berth_type:
            score += 10
        elif 'upper' in berth_type:
            score += 5
        elif 'side lower' in berth_type:
            score += 15
        elif 'side upper' in berth_type:
            score += 8
            
        return score
    
    def create_seat_id(self, seat_row: pd.Series) -> str:
        """Create unique identifier for a seat"""
        return f"{seat_row['category']}_{seat_row['coach']}_{seat_row['berth_no']}"
    
    def find_optimal_seat_combination(self, train_number: str, origin: str, destination: str) -> Dict:
        """Find the optimal combination of seats for the journey"""
        # Get station sequence
        station_sequence = self.get_station_sequence(train_number, origin, destination)
        
        print(f"DEBUG: Journey stations: {[s['station_code'] for s in station_sequence]}")
        
        # Filter seats for this journey and create seat info with unique IDs
        journey_seats = []
        for idx, seat in self.seat_data.iterrows():
            covered_stations, coverage_distance = self.get_seat_coverage(seat, origin, destination, station_sequence)
            if coverage_distance > 0:
                seat_info = {
                    'seat_id': self.create_seat_id(seat),  # Unique identifier
                    'seat_data': seat,
                    'covered_stations': covered_stations,
                    'coverage_distance': coverage_distance,
                    'from_station': covered_stations[0] if covered_stations else '',
                    'to_station': covered_stations[-1] if covered_stations else ''
                }
                journey_seats.append(seat_info)
        
        print(f"DEBUG: Found {len(journey_seats)} available seats for journey")
        for seat in journey_seats[:5]:  # Show first 5 seats
            print(f"  Seat: {seat['seat_data']['category']} {seat['seat_data']['coach']}-{seat['seat_data']['berth_no']}")
            print(f"    From: {seat['seat_data']['from_station']} To: {seat['seat_data']['to_station']}")
            print(f"    Coverage: {seat['coverage_distance']} stations: {seat['covered_stations']}")
        
        if not journey_seats:
            return self.create_no_seat_result(train_number, origin, destination, station_sequence)
        
        # Initialize result structure
        result = {
            'train_number': train_number,
            'origin': origin,
            'destination': destination,
            'seated_segments': [],
            'seatless_segments': [],
            'total_journey_time': 0,
            'total_seated_time': 0,
            'total_standing_time': 0,
            'standing_percentage': 0
        }
        
        current_station = origin
        station_codes = [s['station_code'] for s in station_sequence]
        current_idx = station_codes.index(origin)
        dest_idx = station_codes.index(destination)
        last_assigned_seat = None
        used_seat_ids = set()  # Track used seats by ID
        
        while current_idx < dest_idx:
            current_station_code = station_codes[current_idx]
            
            # Find best seat that covers current station
            best_seat = None
            best_coverage = 0
            best_score = -1
            
            for seat_info in journey_seats:
                # Skip if seat already used
                if seat_info['seat_id'] in used_seat_ids:
                    continue
                    
                # Check if this seat covers the current station
                try:
                    seat_from_idx = station_codes.index(self.extract_station_code(seat_info['seat_data']['from_station']))
                    seat_to_idx = station_codes.index(self.extract_station_code(seat_info['seat_data']['to_station']))
                except ValueError:
                    continue
                
                if seat_from_idx <= current_idx < seat_to_idx:
                    # This seat covers our current position
                    # Calculate how much of remaining journey it covers
                    remaining_coverage = min(seat_to_idx, dest_idx) - current_idx
                    
                    # Calculate preference score
                    pref_score = self.calculate_seat_preference_score(
                        seat_info['seat_data'], 
                        last_assigned_seat['seat_data'] if last_assigned_seat else None
                    )
                    
                    # Select best seat based on coverage first, then preference score
                    if (remaining_coverage > best_coverage or 
                        (remaining_coverage == best_coverage and pref_score > best_score)):
                        best_seat = seat_info
                        best_coverage = remaining_coverage
                        best_score = pref_score
            
            if best_seat:
                # Calculate actual segment for this seat
                seat_from_station = self.extract_station_code(best_seat['seat_data']['from_station'])
                seat_to_station = self.extract_station_code(best_seat['seat_data']['to_station'])
                
                # Effective segment is from current station to seat's end (or journey end)
                effective_from = current_station_code
                effective_to_idx = min(station_codes.index(seat_to_station), dest_idx)
                effective_to = station_codes[effective_to_idx]
                
                journey_time = self.calculate_journey_duration(
                    effective_from, 
                    effective_to, 
                    station_sequence
                )
                
                result['seated_segments'].append({
                    'from_station': effective_from,
                    'to_station': effective_to,
                    'seat_details': {
                        'category': best_seat['seat_data']['category'],
                        'coach': best_seat['seat_data']['coach'],
                        'berth_no': best_seat['seat_data']['berth_no'],
                        'berth_type': best_seat['seat_data']['berth_type'],
                        'cabin': best_seat['seat_data']['cabin'],
                        'cabin_no': best_seat['seat_data']['cabin_no']
                    },
                    'journey_time': journey_time
                })
                
                result['total_seated_time'] += journey_time['total_minutes']
                
                # Update current position
                current_idx = effective_to_idx
                last_assigned_seat = best_seat
                
                # Mark seat as used
                used_seat_ids.add(best_seat['seat_id'])
            else:
                # No seat available - standing segment
                if current_idx + 1 <= dest_idx:
                    if current_idx + 1 == len(station_codes):
                        break
                    next_station = station_codes[current_idx + 1]
                    journey_time = self.calculate_journey_duration(
                        current_station_code, 
                        next_station, 
                        station_sequence
                    )
                    
                    result['seatless_segments'].append({
                        'from_station': current_station_code,
                        'to_station': next_station,
                        'journey_time': journey_time,
                        'status': 'Standing'
                    })
                    
                    result['total_standing_time'] += journey_time['total_minutes']
                
                current_idx += 1
        
        # Calculate total journey time and percentages
        total_journey = self.calculate_journey_duration(origin, destination, station_sequence)
        result['total_journey_time'] = total_journey['total_minutes']
        
        if result['total_journey_time'] > 0:
            result['standing_percentage'] = round(
                (result['total_standing_time'] / result['total_journey_time']) * 100, 2
            )
        
        return result
    
    def create_no_seat_result(self, train_number: str, origin: str, destination: str, station_sequence: List[Dict]) -> Dict:
        """Create result when no seats are available"""
        total_journey = self.calculate_journey_duration(origin, destination, station_sequence)
        
        return {
            'train_number': train_number,
            'origin': origin,
            'destination': destination,
            'seated_segments': [],
            'seatless_segments': [{
                'from_station': origin,
                'to_station': destination,
                'journey_time': total_journey,
                'status': 'Standing - No seats available'
            }],
            'total_journey_time': total_journey['total_minutes'],
            'total_seated_time': 0,
            'total_standing_time': total_journey['total_minutes'],
            'standing_percentage': 100.0
        }
    
    def format_time_duration(self, minutes: int) -> str:
        """Format duration in minutes to human readable format"""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
    
    def print_results(self, result: Dict):
        """Print formatted results"""
        print(f"\n{'='*60}")
        print(f"TRAIN SEAT ALLOCATION ANALYSIS")
        print(f"{'='*60}")
        print(f"Train Number: {result['train_number']}")
        print(f"Journey: {result['origin']} → {result['destination']}")
        print(f"Total Journey Time: {self.format_time_duration(result['total_journey_time'])}")
        print(f"Total Seated Time: {self.format_time_duration(result['total_seated_time'])}")
        print(f"Total Standing Time: {self.format_time_duration(result['total_standing_time'])}")
        print(f"Standing Percentage: {result['standing_percentage']}%")
        
        if result['seated_segments']:
            print(f"\n{'SEATED SEGMENTS':=^60}")
            for i, segment in enumerate(result['seated_segments'], 1):
                print(f"\nSegment {i}:")
                print(f"  Route: {segment['from_station']} → {segment['to_station']}")
                print(f"  Duration: {self.format_time_duration(segment['journey_time']['total_minutes'])}")
                print(f"  Time: {segment['journey_time']['from_time']} - {segment['journey_time']['to_time']}")
                print(f"  Seat Details:")
                seat = segment['seat_details']
                print(f"    Class: {seat['category']}")
                print(f"    Coach: {seat['coach']}")
                print(f"    Berth: {seat['berth_no']} ({seat['berth_type']})")
                if seat['cabin'] != 'filter_list' and str(seat['cabin']).upper() != 'NAN':
                    print(f"    Cabin: {seat['cabin']} {seat['cabin_no']}")
        
        if result['seatless_segments']:
            print(f"\n{'SEATLESS SEGMENTS (STANDING)':=^60}")
            for i, segment in enumerate(result['seatless_segments'], 1):
                print(f"\nStanding Segment {i}:")
                print(f"  Route: {segment['from_station']} → {segment['to_station']}")
                print(f"  Duration: {self.format_time_duration(segment['journey_time']['total_minutes'])}")
                print(f"  Time: {segment['journey_time']['from_time']} - {segment['journey_time']['to_time']}")
                print(f"  Status: {segment['status']}")
    
    def optimize_journey(self, train_number: str, origin: str, destination: str) -> Dict:
        """Main method to optimize seat allocation for a journey"""
        self.load_data()
        result = self.find_optimal_seat_combination(train_number, origin, destination)
        self.print_results(result)
        return result

# Example usage
def main():
    # Initialize optimizer
    optimizer = TrainSeatOptimizer('scraped_data/12424.csv', 'train_stops.json')
    
    # Example: Find optimal seats for journey
    train_number = "12424"  # Example train number
    origin = "NDLS"  # JAISALMER
    destination = "PPTA"  # DELHI
    
    result = optimizer.optimize_journey(train_number, origin, destination)
    
    return result

if __name__ == "__main__":
    main()
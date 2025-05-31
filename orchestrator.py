import json
from datetime import datetime
from typing import Dict, Set
from stage1 import Stage1Processor
from stage2 import Stage2Processor

class TrainAnalysisDriver:
    def __init__(self, cache_file_path: str = "train_stops.json"):
        self.stage1 = Stage1Processor(cache_file_path)
        self.stage2 = Stage2Processor(cache_file_path)
    
    def run_analysis(self, origin: str, destination: str, journey_date: str, 
                    min_valid_routes: int = 1, max_standing_time_hours: float = 2.0,
                    max_iterations: int = 5, max_candidates_per_iteration: int = 5) -> Dict:
        
        all_failed_trains = []
        all_candidates_processed = 0
        iteration = 0
        processed_train_numbers: Set[str] = set()  # Track processed trains
        
        try:
            while iteration < max_iterations:
                iteration += 1
                print(f"\n🔄 ITERATION {iteration}/{max_iterations}")
                print("=" * 50)
                
                # Get candidates from Stage1, excluding already processed trains
                candidates = self.stage1.get_candidates(
                    origin, destination, journey_date, 
                    exclude_train_numbers=processed_train_numbers,
                    max_candidates=max_candidates_per_iteration
                )
                
                if not candidates:
                    print(f"❌ No more candidate trains found in iteration {iteration}")
                    print(f"   Already processed trains: {sorted(processed_train_numbers)}")
                    break
                
                print(f"📋 Found {len(candidates)} NEW candidates in iteration {iteration}")
                
                # Show which trains we're about to process WITH THEIR DEPARTURE TIMES
                print(f"   🕐 Trains ordered by departure time (earliest first):")
                for i, candidate in enumerate(candidates):
                    train_num = candidate.get('number', 'Unknown')
                    true_origin_time = candidate.get('departure_time_from_true_origin', 'N/A')
                    origin_station = candidate.get('true_origin_station', 'Unknown')
                    boarding_time = candidate.get('departure_time_from_user_origin', 'N/A')
                    
                    print(f"     {i+1}. Train {train_num}")
                    if true_origin_time != 'N/A':
                        print(f"        Origin: {origin_station} at {true_origin_time}")
                        print(f"        Your boarding: {boarding_time}")
                    else:
                        print(f"        Departure: {boarding_time} (fallback mode)")
                
                print(f"   Previously processed: {sorted(processed_train_numbers)}")
                
                # Add these candidates to processed set BEFORE analysis
                # This prevents them from being returned in future iterations
                for candidate in candidates:
                    train_number = candidate.get('number', '')
                    if train_number:
                        processed_train_numbers.add(train_number)
                
                # Analyze candidates with Stage2
                analysis_result = self.stage2.analyze_candidates(
                    candidates, origin, destination, journey_date, 
                    min_valid_routes, max_standing_time_hours
                )
                
                all_candidates_processed += analysis_result.get('total_candidates_processed', 0)
                all_failed_trains.extend(analysis_result.get('failed_trains', []))
                
                # If Stage2 succeeded (found enough valid trains), return success
                if analysis_result.get('success', False) and analysis_result.get('criteria_met', False):
                    print(f"\n✅ SUCCESS: Found valid trains in iteration {iteration}")
                    analysis_result['stage_completed'] = 2
                    analysis_result['candidates_found'] = all_candidates_processed
                    analysis_result['total_iterations'] = iteration
                    analysis_result['all_failed_trains'] = all_failed_trains
                    analysis_result['processed_train_numbers'] = list(processed_train_numbers)
                    return analysis_result
                
                # If Stage2 failed, continue to next iteration
                print(f"\n⚠️ Iteration {iteration} failed: {analysis_result.get('message', 'Unknown reason')}")
                print(f"   Failed trains in this iteration: {len(analysis_result.get('failed_trains', []))}")
                
                # Show details of failed trains
                failed_in_iteration = analysis_result.get('failed_trains', [])
                for failed in failed_in_iteration:
                    train_num = failed.get('train_number', 'Unknown')
                    error = failed.get('error', 'Unknown error')
                    if 'standing_time_hours' in failed:
                        standing_hours = failed['standing_time_hours']
                        limit = failed.get('standing_time_limit', 0)
                        print(f"     • Train {train_num}: {standing_hours:.2f}h > {limit}h limit")
                    else:
                        print(f"     • Train {train_num}: {error}")
                
                # Continue to next iteration with remaining trains
                print(f"   Total trains processed so far: {len(processed_train_numbers)}")
                print(f"   Continuing to next iteration...")
            
            # All iterations exhausted without success
            return {
                'success': False,
                'stage_completed': 2,
                'message': f'No trains found meeting criteria after {iteration} iterations. All trains exceed standing time limit of {max_standing_time_hours} hours.',
                'candidates_found': all_candidates_processed,
                'total_iterations': iteration,
                'valid_results': [],
                'all_failed_trains': all_failed_trains,
                'failed_trains': all_failed_trains,  # For backward compatibility
                'processed_train_numbers': list(processed_train_numbers)
            }
            
        except Exception as e:
            return {
                'success': False,
                'stage_completed': 0,
                'message': f'Analysis failed with error: {str(e)}',
                'error_details': str(e),
                'candidates_found': all_candidates_processed,
                'total_iterations': iteration,
                'valid_results': [],
                'all_failed_trains': all_failed_trains,
                'processed_train_numbers': list(processed_train_numbers)
            }
    
def format_time_from_minutes(total_minutes: int) -> str:
    """Convert total minutes to readable format like '2h 30m'"""
    if total_minutes == 0:
        return "0h 0m"
    
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    if hours > 0 and minutes > 0:
        return f"{hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h 0m"
    else:
        return f"0h {minutes}m"

def display_results(result: Dict):
    print("\n" + "="*60)
    print("📊 ANALYSIS RESULTS")
    print("="*60)
    
    if not result['success']:
        print(f"❌ ANALYSIS FAILED")
        print(f"Stage completed: {result.get('stage_completed', 0)}/2")
        print(f"Message: {result.get('message', 'Unknown error')}")
        print(f"Total iterations: {result.get('total_iterations', 0)}")
        print(f"Total candidates processed: {result.get('candidates_found', 0)}")
        
        # Show processed trains
        processed_trains = result.get('processed_train_numbers', [])
        if processed_trains:
            print(f"Trains analyzed: {sorted(processed_trains)}")
        
        # Show failed trains summary
        all_failed_trains = result.get('all_failed_trains', [])
        if all_failed_trains:
            print(f"\n❌ FAILED TRAINS SUMMARY ({len(all_failed_trains)}):")
            print("-" * 40)
            for failed in all_failed_trains:
                train_num = failed.get('train_number', 'Unknown')
                error = failed.get('error', 'Unknown error')
                if 'standing_time_hours' in failed:
                    standing_hours = failed['standing_time_hours']
                    limit = failed.get('standing_time_limit', 0)
                    print(f"   Train {train_num}: Standing time {standing_hours:.2f}h > {limit}h limit")
                else:
                    print(f"   Train {train_num}: {error}")
        return
    
    print(f"✅ ANALYSIS COMPLETED")
    print(f"Candidates processed: {result.get('total_candidates_processed', 0)}/{result.get('total_candidates', 0)}")
    print(f"Valid trains found: {result.get('valid_trains_found', 0)}")
    print(f"Criteria met: {'YES' if result.get('criteria_met', False) else 'NO'}")
    
    # Show processed trains
    processed_trains = result.get('processed_train_numbers', [])
    if processed_trains:
        print(f"Trains analyzed: {sorted(processed_trains)}")
    
    valid_results = result.get('valid_results', [])
    
    if valid_results:
        print(f"\n🎯 VALID TRAIN OPTIONS ({len(valid_results)}):")
        print("=" * 40)
        
        for i, train_result in enumerate(valid_results, 1):
            print(f"\n🚂 OPTION {i}: Train {train_result['train_number']}")
            print(f"   Departure: {train_result['departure_time']}")
            
            # Get standing time from the correct location
            standing_time_hours = train_result.get('standing_time_hours', 0)
            standing_percentage = train_result.get('standing_percentage', 0)
            
            # Convert hours back to readable format
            hours = int(standing_time_hours)
            minutes = int((standing_time_hours - hours) * 60)
            standing_time_display = f"{hours}h {minutes}m"
            
            print(f"   Standing time: {standing_time_display} ({standing_time_hours:.2f} hours)")
            print(f"   Standing %: {standing_percentage:.1f}%")
            print(f"   Seated segments: {train_result['seated_segments_count']}")
            
            # Show criteria check
            criteria = train_result.get('criteria_details', {})
            max_allowed = criteria.get('max_standing_time_hours', 'N/A')
            print(f"   Max allowed standing: {max_allowed} hours")
            print(f"   Meets criteria: {train_result.get('meets_criteria', False)}")
            
            # Show detailed seat analysis
            analysis = train_result.get('analysis_result', {})
            
            # SEATED SEGMENTS with full details
            seated_segments = analysis.get('seated_segments', [])
            if seated_segments:
                print(f"\n   ======================SEATED SEGMENTS=======================")
                for j, segment in enumerate(seated_segments, 1):
                    print(f"   Segment {j}:")
                    print(f"     Route: {segment.get('from_station', 'N/A')} → {segment.get('to_station', 'N/A')}")
                    
                    # Extract journey time details
                    journey_time = segment.get('journey_time', {})
                    if journey_time:
                        total_minutes = journey_time.get('total_minutes', 0) 
                        duration_str = format_time_from_minutes(total_minutes)
                        print(f"     Duration: {duration_str}")
                        
                        # Show departure and arrival times if available
                        departure_time = journey_time.get('departure_time', 'N/A')
                        arrival_time = journey_time.get('arrival_time', 'N/A')
                        if departure_time != 'N/A' and arrival_time != 'N/A':
                            print(f"     Time: {departure_time} - {arrival_time}")
                    
                    # Extract seat details
                    seat_details = segment.get('seat_details', {})
                    if seat_details:
                        print(f"     Seat Details:")
                        category = seat_details.get('category', 'N/A')
                        coach = seat_details.get('coach', 'N/A')
                        berth_no = seat_details.get('berth_no', 'N/A')
                        berth_type = seat_details.get('berth_type', 'N/A')
                        cabin = seat_details.get('cabin', 'N/A')
                        cabin_no = seat_details.get('cabin_no', 'N/A')
                        
                        print(f"       Class: {category}")
                        print(f"       Coach: {coach}")
                        if berth_no != 'N/A':
                            print(f"       Berth: {berth_no} ({berth_type})")
                        if cabin != 'N/A' and cabin_no != 'N/A':
                            print(f"       Cabin: {cabin} {cabin_no}")
            
            # SEATLESS SEGMENTS (Standing) with full details  
            seatless_segments = analysis.get('seatless_segments', [])
            if seatless_segments:
                print(f"\n   ================SEATLESS SEGMENTS (STANDING)================")
                for j, segment in enumerate(seatless_segments, 1):
                    print(f"   Standing Segment {j}:")
                    print(f"     Route: {segment.get('from_station', 'N/A')} → {segment.get('to_station', 'N/A')}")
                    
                    # Extract journey time details for standing segments
                    journey_time = segment.get('journey_time', {})
                    if journey_time:
                        total_minutes = journey_time.get('total_minutes', 0)
                        duration_str = format_time_from_minutes(total_minutes)
                        print(f"     Duration: {duration_str}")
                        
                        # Show departure and arrival times if available
                        departure_time = journey_time.get('departure_time', 'N/A')
                        arrival_time = journey_time.get('arrival_time', 'N/A')
                        if departure_time != 'N/A' and arrival_time != 'N/A':
                            print(f"     Time: {departure_time} - {arrival_time}")
                    
                    status = segment.get('status', 'Standing')
                    print(f"     Status: {status}")
            
            # Show total journey summary
            total_journey_time = analysis.get('total_journey_time', 0)
            total_seated_time = analysis.get('total_seated_time', 0)  
            total_standing_time = analysis.get('total_standing_time', 0)
            
            if total_journey_time > 0:
                print(f"\n   📊 JOURNEY SUMMARY:")
                print(f"     Total Journey: {format_time_from_minutes(total_journey_time)}")
                print(f"     Total Seated: {format_time_from_minutes(total_seated_time)}")
                print(f"     Total Standing: {format_time_from_minutes(total_standing_time)}")
                print(f"     Standing %: {analysis.get('standing_percentage', 0):.1f}%")
    
    # Show failed trains if any
    failed_trains = result.get('all_failed_trains', result.get('failed_trains', []))
    if failed_trains:
        print(f"\n❌ FAILED TRAINS ({len(failed_trains)}):")
        print("-" * 30)
        for failed in failed_trains:
            train_num = failed.get('train_number', 'Unknown')
            error = failed.get('error', 'Unknown error')
            if 'standing_time_hours' in failed:
                standing_hours = failed['standing_time_hours']
                limit = failed.get('standing_time_limit', 0)
                print(f"   Train {train_num}: Standing time {standing_hours:.2f}h exceeds {limit}h limit")
            else:
                print(f"   Train {train_num}: {error}")

if __name__ == "__main__":
    origin = "DLI_Delhi"
    destination = "PNBE_Patna"
    journey_date = "20250530"
    max_standing_time_hours = 3  # This should reject trains with ANY standing time
    min_valid_routes = 2
    max_iterations = 5  # Try up to 5 batches of trains
    max_candidates_per_iteration = 3  # Process 3 trains at a time
    
    print(f"🚂 Starting train analysis...")
    print(f"Journey: {origin} → {destination}")
    print(f"Date: {journey_date}")
    print(f"Max standing time: {max_standing_time_hours} hours")
    print(f"Min valid routes needed: {min_valid_routes}")
    print(f"Max iterations: {max_iterations}")
    print(f"Candidates per iteration: {max_candidates_per_iteration}")
    print("=" * 50)
    
    driver = TrainAnalysisDriver()
    
    result = driver.run_analysis(
        origin=origin,
        destination=destination,
        journey_date=journey_date,
        min_valid_routes=min_valid_routes,
        max_standing_time_hours=max_standing_time_hours,
        max_iterations=max_iterations,
        max_candidates_per_iteration=max_candidates_per_iteration
    )
    
    display_results(result)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"analysis_result_{timestamp}.json"
    
    with open(result_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {result_file}")
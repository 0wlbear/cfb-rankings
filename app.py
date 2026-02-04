# Standard library imports
import json
import math
import os
import time
import hashlib
import signal
import sys
from datetime import date, datetime, timedelta
from collections import defaultdict
from functools import wraps

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, session, render_template_string
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Local imports - Database models
from models import (
    db, 
    Game, 
    TeamStats, 
    ScheduledGame, 
    ArchivedSeason, 
    WeeklySnapshot, 
    CFBPredictionLog,
    ExternalPoll
)

# Bowl Pick'em Blueprint
from blueprints.bowl_pickem import bp as bowl_pickem_bp

# Local imports - CFB ML tracking (with error handling)
CFB_ML_ENABLED = False
try:
    import cfb_ml_tracking
    from cfb_ml_tracking import (
        track_prediction,
        log_actual_result, 
        get_ml_dashboard_data,
        export_prediction_data
    )
    CFB_ML_ENABLED = True
    print("✅ CFB ML tracking module loaded")
except ImportError as e:
    print(f"⚠️ CFB ML tracking not available: {e}")
    # Create dummy functions to prevent errors
    def track_prediction(prediction_type):
        def decorator(func):
            return func
        return decorator
    
    def log_actual_result(*args, **kwargs):
        return 0
    
    def get_ml_dashboard_data():
        return None
    
    def export_prediction_data():
        return None

# # Local imports - CFB Gen AI (with error handling)
# CFB_GEN_AI_ENABLED = False
# try:
#     import cfb_gen_ai
#     from cfb_gen_ai import (
#         explain_game_impact,
#         get_gen_ai_status,
#         explain_team_ranking,
#         generate_weekly_preview,
#         process_natural_language_query,
#         generate_weekly_report
#     )
#     CFB_GEN_AI_ENABLED = True
#     print("✅ CFB Gen AI module loaded")
# except ImportError as e:
#     print(f"⚠️ CFB Gen AI not available: {e}")
#     # Create dummy functions to prevent errors
#     def explain_game_impact(*args, **kwargs):
#         return "AI analysis temporarily unavailable"
    
#     def get_gen_ai_status():
#         return {'available': False}
    
#     def test_gen_ai_connection():
#         return {'status': 'unavailable', 'error': 'Module not loaded'}

#     def generate_weekly_preview(*args, **kwargs):
#         return "Weekly preview temporarily unavailable"
    
#     def explain_team_ranking(*args, **kwargs):
#         return "Ranking explanation temporarily unavailable"
    
#     def enhance_matchup_prediction(*args, **kwargs):
#         return "Prediction analysis temporarily unavailable"


# Simple in-memory cache (for production, use Redis)
performance_cache = {}
CACHE_TIMEOUT = 300  # 5 minutes

def cache_result(timeout=CACHE_TIMEOUT):
    """Decorator to cache expensive function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}_{hashlib.md5(str(args).encode()).hexdigest()}"
            
            # Check if result is in cache and not expired
            if cache_key in performance_cache:
                cached_result, timestamp = performance_cache[cache_key]
                if time.time() - timestamp < timeout:
                    return cached_result
            
            # Not in cache or expired - calculate result
            result = func(*args, **kwargs)
            
            # Store in cache
            performance_cache[cache_key] = (result, time.time())
            
            return result
        return wrapper
    return decorator

# Cache management functions
def clear_cache():
    """Clear all cached results"""
    global performance_cache
    performance_cache.clear()

def get_cache_stats():
    """Get cache statistics"""
    total_entries = len(performance_cache)
    total_size = sum(len(str(v)) for v in performance_cache.values())
    
    return {
        'total_entries': total_entries,
        'total_size_bytes': total_size,
        'entries': list(performance_cache.keys())
    }

# Apply caching to your expensive functions
@cache_result(timeout=300)  # Cache for 5 minutes
def calculate_comprehensive_stats_cached(team_name):
    """Cached version of calculate_comprehensive_stats"""
    return calculate_comprehensive_stats(team_name)

@cache_result(timeout=300)  # Cache for 5 minutes  
def calculate_enhanced_scientific_ranking_cached(team_name):
    """Cached version of calculate_enhanced_scientific_ranking"""
    return calculate_enhanced_scientific_ranking(team_name)

@cache_result(timeout=180)  # Cache for 3 minutes
def get_current_opponent_quality_cached(opponent_name):
    """Cached version of get_current_opponent_quality"""
    return get_current_opponent_quality(opponent_name)

def time_route(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        end_time = time.time()
        print(f"⏱️ Route {f.__name__} took {end_time - start_time:.2f} seconds")
        return result
    return decorated_function

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.permanent_session_lifetime = 86400  # Session lasts 24 hours

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://cfb_admin:CFBRankings2025!@cfb-rankings-db.c0x628i8m5pg.us-east-1.rds.amazonaws.com:5432/cfb_rankings')

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

db.init_app(app)

# Register Bowl Pick'em Blueprint
app.register_blueprint(bowl_pickem_bp)

# Conference Teams
ACC_TEAMS = [
    'Boston College', 'California', 'Clemson', 'Duke', 'Florida State',
    'Georgia Tech', 'Louisville', 'Miami', 'NC State', 'North Carolina',
    'Pittsburgh', 'SMU', 'Stanford', 'Syracuse', 'Virginia', 'Virginia Tech',
    'Wake Forest'
]

BIG_TEN_TEAMS = [
    'Illinois', 'Indiana', 'Iowa', 'Maryland', 'Michigan', 'Michigan State',
    'Minnesota', 'Nebraska', 'Northwestern', 'Ohio State', 'Oregon',
    'Penn State', 'Purdue', 'Rutgers', 'UCLA', 'USC', 'Washington', 'Wisconsin'
]

BIG_XII_TEAMS = [
    'Arizona', 'Arizona State', 'Baylor', 'BYU', 'Cincinnati', 'Colorado',
    'Houston', 'Iowa State', 'Kansas', 'Kansas State', 'Oklahoma State',
    'TCU', 'Texas Tech', 'UCF', 'Utah', 'West Virginia'
]

PAC_12_TEAMS = [
    'Oregon State', 'Washington State'
]

SEC_TEAMS = [
    'Alabama', 'Arkansas', 'Auburn', 'Florida', 'Georgia', 'Kentucky',
    'LSU', 'Mississippi State', 'Missouri', 'Oklahoma', 'Ole Miss',
    'South Carolina', 'Tennessee', 'Texas', 'Texas A&M', 'Vanderbilt'
]

INDEPENDENT_TEAMS = [
    'Connecticut', 'Notre Dame', 'FCS'
]

AMERICAN_TEAMS = [
    'Army', 'Charlotte', 'East Carolina', 'Florida Atlantic', 'Memphis',
    'Navy', 'North Texas', 'Rice', 'South Florida', 'Temple',
    'Tulane', 'Tulsa', 'UAB', 'UTSA'
]

CONFERENCE_USA_TEAMS = [
    'Delaware', 'Florida Intl', 'Jacksonville State', 'Kennesaw State',
    'LA Tech', 'Liberty', 'Middle Tennessee', 'Missouri State',
    'New Mexico St', 'Sam Houston', 'UTEP', 'Western Kentucky'
]

MAC_TEAMS = [
    'Akron', 'Ball State', 'Bowling Green', 'Buffalo', 'Central Michigan',
    'Eastern Michigan', 'Kent State', 'UMass', 'Miami (OH)',
    'Northern Illinois', 'Ohio', 'Toledo', 'Western Michigan'
]

MOUNTAIN_WEST_TEAMS = [
    'Air Force', 'Boise State', 'Colorado State', 'Fresno State',
    'Hawaii', 'Nevada', 'New Mexico', 'San Diego State',
    'San Jose State', 'UNLV', 'Utah State', 'Wyoming'
]

SUN_BELT_TEAMS = [
    'Appalachian St', 'Arkansas State', 'Coastal Carolina', 'Georgia Southern',
    'Georgia State', 'James Madison', 'UL Monroe', 'Louisiana',
    'Marshall', 'Old Dominion', 'South Alabama', 'Southern Miss',
    'Texas State', 'Troy'
]

# ESPN Team ID mapping for logos
TEAM_LOGOS = {
   # ACC
    'Boston College': '103',
    'California': '25', 
    'Clemson': '228',
    'Duke': '150',
    'Florida State': '52',
    'Georgia Tech': '59',
    'Louisville': '97',
    'Miami': '2390',
    'NC State': '152',
    'North Carolina': '153',
    'Pittsburgh': '221',
    'SMU': '2567',
    'Stanford': '24',
    'Syracuse': '183',
    'Virginia': '258',
    'Virginia Tech': '259',
    'Wake Forest': '154',
    
    # Big Ten
    'Illinois': '356',
    'Indiana': '84',
    'Iowa': '2294',
    'Maryland': '120',
    'Michigan': '130',
    'Michigan State': '127',
    'Minnesota': '135',
    'Nebraska': '158',
    'Northwestern': '77',
    'Ohio State': '194',
    'Oregon': '2483',
    'Penn State': '213',
    'Purdue': '2509',
    'Rutgers': '164',
    'UCLA': '26',
    'USC': '30',
    'Washington': '264',
    'Wisconsin': '275',
    
    # Big XII
    'Arizona': '12',
    'Arizona State': '9',
    'Baylor': '239',
    'BYU': '252',
    'Cincinnati': '2132',
    'Colorado': '38',
    'Houston': '248',
    'Iowa State': '66',
    'Kansas': '2305',
    'Kansas State': '2306',
    'Oklahoma State': '197',
    'TCU': '2628',
    'Texas Tech': '2641',
    'UCF': '2116',
    'Utah': '254',
    'West Virginia': '277',
    
    # SEC
    'Alabama': '333',
    'Arkansas': '8',
    'Auburn': '2',
    'Florida': '57',
    'Georgia': '61',
    'Kentucky': '96',
    'LSU': '99',
    'Mississippi State': '344',
    'Missouri': '142',
    'Oklahoma': '201',
    'Ole Miss': '145',
    'South Carolina': '2579',
    'Tennessee': '2633',
    'Texas': '251',
    'Texas A&M': '245',
    'Vanderbilt': '238',
    
    # Pac 12
    'Oregon State': '204',
    'Washington State': '265',
    
    # American
    'Army': '349',
    'Charlotte': '2429',
    'East Carolina': '151',
    'Florida Atlantic': '2226',
    'Memphis': '235',
    'Navy': '2426',
    'North Texas': '249',
    'Rice': '242',
    'South Florida': '58',
    'Temple': '218',
    'Tulane': '2655',
    'Tulsa': '202',
    'UAB': '5',
    'UTSA': '2636',
    
    # Conference USA
    'Delaware': '48',
    'Florida Intl': '2229',
    'Jacksonville State': '55',
    'Kennesaw State': '338',
    'LA Tech': '2348',
    'Liberty': '2335',
    'Middle Tennessee': '2393',
    'Missouri State': '2623',
    'New Mexico St': '166',
    'Sam Houston': '2534',
    'UTEP': '2638',
    'Western Kentucky': '98',
    
    # MAC
    'Akron': '2006',
    'Ball State': '2050',
    'Bowling Green': '189',
    'Buffalo': '2084',
    'Central Michigan': '2117',
    'Eastern Michigan': '2199',
    'Kent State': '2309',
    'UMass': '113',
    'Miami (OH)': '193',
    'Northern Illinois': '2459',
    'Ohio': '195',
    'Toledo': '2649',
    'Western Michigan': '2711',
    
    # Mountain West
    'Air Force': '2005',
    'Boise State': '68',
    'Colorado State': '36',
    'Fresno State': '278',
    'Hawaii': '62',
    'Nevada': '2440',
    'New Mexico': '167',
    'San Diego State': '21',
    'San Jose State': '23',
    'UNLV': '2439',
    'Utah State': '328',
    'Wyoming': '2751',
    
    # Sun Belt
    'Appalachian St': '2026',
    'Arkansas State': '2032',
    'Coastal Carolina': '324',
    'Georgia Southern': '290',
    'Georgia State': '2247',
    'James Madison': '256',
    'UL Monroe': '2433',
    'Louisiana': '309',
    'Marshall': '276',
    'Old Dominion': '295',
    'South Alabama': '6',
    'Southern Miss': '2572',
    'Texas State': '326',
    'Troy': '2653',
    
    # Independent
    'Connecticut': '41',
    'Notre Dame': '87',

}

# Comprehensive team variations - GLOBAL
TEAM_VARIATIONS = {
    # SEC
            'Alabama': ['Alabama', 'Bama', 'Crimson Tide'],
            'Arkansas': ['Arkansas', 'Ark', 'Razorbacks'],
            'Auburn': ['Auburn', 'Tigers'],
            'Florida': ['Florida', 'UF', 'Gators'],
            'Georgia': ['Georgia', 'UGA', 'Bulldogs'],
            'Kentucky': ['Kentucky', 'UK', 'Wildcats'],
            'LSU': ['LSU', 'Louisiana State', 'Tigers'],
            'Mississippi State': ['Mississippi State', 'MSU', 'Miss State', 'Bulldogs'],
            'Missouri': ['Missouri', 'Mizzou', 'Tigers'],
            'Oklahoma': ['Oklahoma', 'OU', 'Sooners'],
            'Ole Miss': ['Ole Miss', 'Mississippi', 'Rebels'],
            'South Carolina': ['South Carolina', 'Gamecocks'],
            'Tennessee': ['Tennessee', 'Tenn', 'UT', 'Volunteers', 'Vols'],
            'Texas': ['Texas', 'UT', 'Longhorns'],
            'Texas A&M': ['Texas A&M', 'TAMU', 'A&M', 'Aggies', 'Texas AM'],
            'Vanderbilt': ['Vanderbilt', 'Vandy', 'Commodores'],

            # Big Ten
            'Illinois': ['Illinois', 'Illini', 'Fighting Illini'],
            'Indiana': ['Indiana', 'IU', 'Hoosiers'],
            'Iowa': ['Iowa', 'Hawkeyes'],
            'Maryland': ['Maryland', 'UMD', 'Terrapins', 'Terps'],
            'Michigan': ['Michigan', 'UM', 'Wolverines'],
            'Michigan State': ['Michigan State', 'MSU', 'Mich State', 'Spartans'],
            'Minnesota': ['Minnesota', 'Gophers', 'Golden Gophers'],
            'Nebraska': ['Nebraska', 'Huskers', 'Cornhuskers'],
            'Northwestern': ['Northwestern', 'NU', 'Wildcats'],
            'Ohio State': ['Ohio State', 'OSU', 'tOSU', 'Buckeyes'],
            'Oregon': ['Oregon', 'Ducks'],
            'Penn State': ['Penn State', 'PSU', 'Nittany Lions'],
            'Purdue': ['Purdue', 'Boilermakers'],
            'Rutgers': ['Rutgers', 'RU', 'Scarlet Knights'],
            'UCLA': ['UCLA', 'Bruins'],
            'USC': ['USC', 'Southern Cal', 'Southern California', 'Trojans'],
            'Washington': ['Washington', 'UW', 'Huskies'],
            'Wisconsin': ['Wisconsin', 'Badgers'],

            # ACC
            'Boston College': ['Boston College', 'BC', 'Eagles'],
            'California': ['California', 'Cal', 'Berkeley', 'Golden Bears'],
            'Clemson': ['Clemson', 'Tigers'],
            'Duke': ['Duke', 'Blue Devils'],
            'Florida State': ['Florida State', 'FSU', 'Seminoles'],
            'Georgia Tech': ['Georgia Tech', 'GT', 'Yellow Jackets'],
            'Louisville': ['Louisville', 'Cards', 'Cardinals'],
            'Miami': ['Miami', 'UM', 'Miami (FL)', 'Miami Florida', 'Miami FL', 'Hurricanes', 'The U'],
            'NC State': ['NC State', 'North Carolina State', 'NCSU', 'Wolfpack'],
            'North Carolina': ['North Carolina', 'UNC', 'Tar Heels', 'Carolina'],
            'Pittsburgh': ['Pittsburgh', 'Pitt', 'Panthers'],
            'SMU': ['SMU', 'Southern Methodist', 'Mustangs'],
            'Stanford': ['Stanford', 'Cardinal'],
            'Syracuse': ['Syracuse', 'Cuse', 'Orange'],
            'Virginia': ['Virginia', 'UVA', 'Cavaliers'],
            'Virginia Tech': ['Virginia Tech', 'VT', 'Hokies'],
            'Wake Forest': ['Wake Forest', 'Wake', 'Demon Deacons'],

            # Big 12
            'Arizona': ['Arizona', 'Wildcats'],
            'Arizona State': ['Arizona State', 'ASU', 'Sun Devils'],
            'Baylor': ['Baylor', 'Bears'],
            'BYU': ['BYU', 'Brigham Young', 'Cougars'],
            'Cincinnati': ['Cincinnati', 'UC', 'Bearcats'],
            'Colorado': ['Colorado', 'CU', 'Buffaloes', 'Buffs'],
            'Houston': ['Houston', 'UH', 'Cougars'],
            'Iowa State': ['Iowa State', 'ISU', 'Cyclones'],
            'Kansas': ['Kansas', 'KU', 'Jayhawks'],
            'Kansas State': ['Kansas State', 'KSU', 'K-State', 'Wildcats'],
            'Oklahoma State': ['Oklahoma State', 'OSU', 'Cowboys'],
            'TCU': ['TCU', 'Texas Christian', 'Horned Frogs'],
            'Texas Tech': ['Texas Tech', 'TTU', 'Red Raiders'],
            'UCF': ['UCF', 'Central Florida', 'Knights'],
            'Utah': ['Utah', 'Utes'],
            'West Virginia': ['West Virginia', 'WVU', 'Mountaineers'],

            # Pac-12 (remaining)
            'Oregon State': ['Oregon State', 'OSU', 'Beavers'],
            'Washington State': ['Washington State', 'WSU', 'Cougars'],

            # American Athletic Conference
            'Army': ['Army', 'Black Knights'],
            'Charlotte': ['Charlotte', '49ers'],
            'East Carolina': ['East Carolina', 'ECU', 'Pirates'],
            'Florida Atlantic': ['Florida Atlantic', 'FAU', 'Owls'],
            'Memphis': ['Memphis', 'Tigers'],
            'Navy': ['Navy', 'Midshipmen'],
            'North Texas': ['North Texas', 'UNT', 'Mean Green'],
            'Rice': ['Rice', 'Owls'],
            'South Florida': ['South Florida', 'USF', 'Bulls'],
            'Temple': ['Temple', 'Owls'],
            'Tulane': ['Tulane', 'Green Wave'],
            'Tulsa': ['Tulsa', 'Golden Hurricane'],
            'UAB': ['UAB', 'Alabama Birmingham', 'Blazers'],
            'UTSA': ['UTSA', 'Texas San Antonio', 'Roadrunners'],

            # Conference USA
            'Delaware': ['Delaware', 'Blue Hens'],
            'Florida Intl': ['Florida Intl', 'FIU', 'Florida International', 'Panthers'],
            'Jacksonville State': ['Jacksonville State', 'JSU', 'Gamecocks'],
            'Kennesaw State': ['Kennesaw State', 'Owls'],
            'LA Tech': ['LA Tech', 'Louisiana Tech', 'Bulldogs'],
            'Liberty': ['Liberty', 'Flames'],
            'Middle Tennessee': ['Middle Tennessee', 'MTSU', 'Blue Raiders'],
            'Missouri State': ['Missouri State', 'Bears'],
            'New Mexico St': ['New Mexico St', 'New Mexico State', 'NMSU', 'Aggies'],
            'Sam Houston': ['Sam Houston', 'Sam Houston State', 'SHSU', 'Bearkats'],
            'UTEP': ['UTEP', 'Texas El Paso', 'Miners'],
            'Western Kentucky': ['Western Kentucky', 'WKU', 'Hilltoppers'],

            # MAC
            'Akron': ['Akron', 'Zips'],
            'Ball State': ['Ball State', 'Cardinals'],
            'Bowling Green': ['Bowling Green', 'BGSU', 'Falcons'],
            'Buffalo': ['Buffalo', 'Bulls'],
            'Central Michigan': ['Central Michigan', 'CMU', 'Chippewas'],
            'Eastern Michigan': ['Eastern Michigan', 'EMU', 'Eagles'],
            'Kent State': ['Kent State', 'Golden Flashes'],
            'UMass': ['UMass', 'Massachusetts', 'Minutemen'],
            'Miami (OH)': ['Miami (OH)', 'Miami Ohio', 'Miami "Ohio"', 'Miami (Ohio)', 'RedHawks'],
            'Northern Illinois': ['Northern Illinois', 'NIU', 'Huskies'],
            'Ohio': ['Ohio', 'Bobcats'],
            'Toledo': ['Toledo', 'Rockets'],
            'Western Michigan': ['Western Michigan', 'WMU', 'Broncos'],

            # Mountain West
            'Air Force': ['Air Force', 'Falcons'],
            'Boise State': ['Boise State', 'Broncos'],
            'Colorado State': ['Colorado State', 'CSU', 'Rams'],
            'Fresno State': ['Fresno State', 'Bulldogs'],
            'Hawaii': ['Hawaii', 'Rainbow Warriors'],
            'Nevada': ['Nevada', 'Wolf Pack'],
            'New Mexico': ['New Mexico', 'UNM', 'Lobos'],
            'San Diego State': ['San Diego State', 'SDSU', 'Aztecs'],
            'San Jose State': ['San Jose State', 'SJSU', 'Spartans'],
            'UNLV': ['UNLV', 'Rebels'],
            'Utah State': ['Utah State', 'USU', 'Aggies'],
            'Wyoming': ['Wyoming', 'Cowboys'],

            # Sun Belt
            'Appalachian St': ['Appalachian St', 'Appalachian State', 'App State', 'Mountaineers'],
            'Arkansas State': ['Arkansas State', 'A-State', 'Red Wolves'],
            'Coastal Carolina': ['Coastal Carolina', 'Chanticleers'],
            'Georgia Southern': ['Georgia Southern', 'Eagles'],
            'Georgia State': ['Georgia State', 'Panthers'],
            'James Madison': ['James Madison', 'JMU', 'Dukes'],
            'UL Monroe': ['UL Monroe', 'ULM', 'Louisiana Monroe', 'Warhawks'],
            'Louisiana': ['Louisiana', 'UL', 'Ragin Cajuns', 'Louisiana Lafayette'],
            'Marshall': ['Marshall', 'Thundering Herd'],
            'Old Dominion': ['Old Dominion', 'ODU', 'Monarchs'],
            'South Alabama': ['South Alabama', 'USA', 'Jaguars'],
            'Southern Miss': ['Southern Miss', 'Southern Mississippi', 'USM', 'Golden Eagles'],
            'Texas State': ['Texas State', 'Bobcats'],
            'Troy': ['Troy', 'Trojans'],

            # Independents
            'Connecticut': ['Connecticut', 'UConn', 'Huskies'],
            'Notre Dame': ['Notre Dame', 'ND', 'Fighting Irish'],
}



# Bowl game definitions with tie-ins and selection order
BOWL_GAMES = {
    # College Football Playoff (handled separately)
    'cfp_national_championship': {
        'name': 'CFP National Championship',
        'tier': 'CFP',
        'location': 'TBD',
        'teams': 2,
        'selection': 'CFP #1 vs CFP #2',
        'payout': '$20M'
    },
    
    # New Year's Six Bowls
    'rose_bowl': {
        'name': 'Rose Bowl',
        'tier': 'NY6',
        'location': 'Pasadena, CA',
        'teams': 2,
        'primary_tie_ins': ['Big Ten', 'Pac 12'],
        'selection_order': 1,
        'payout': '$4M'
    },
    'sugar_bowl': {
        'name': 'Sugar Bowl',
        'tier': 'NY6', 
        'location': 'New Orleans, LA',
        'teams': 2,
        'primary_tie_ins': ['SEC', 'Big XII'],
        'selection_order': 2,
        'payout': '$4M'
    },
    'orange_bowl': {
        'name': 'Orange Bowl',
        'tier': 'NY6',
        'location': 'Miami Gardens, FL',
        'teams': 2,
        'primary_tie_ins': ['ACC', 'SEC/Big Ten/Notre Dame'],
        'selection_order': 3,
        'payout': '$4M'
    },
    'cotton_bowl': {
        'name': 'Cotton Bowl',
        'tier': 'NY6',
        'location': 'Arlington, TX',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'SEC/Big Ten'],
        'selection_order': 4,
        'payout': '$4M'
    },
    'fiesta_bowl': {
        'name': 'Fiesta Bowl',
        'tier': 'NY6',
        'location': 'Glendale, AZ',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'At-Large'],
        'selection_order': 5,
        'payout': '$4M'
    },
    'peach_bowl': {
        'name': 'Peach Bowl',
        'tier': 'NY6',
        'location': 'Atlanta, GA',
        'teams': 2,
        'primary_tie_ins': ['ACC', 'At-Large'],
        'selection_order': 6,
        'payout': '$4M'
    },
    
    # Major Conference Bowls
    'citrus_bowl': {
        'name': 'Citrus Bowl',
        'tier': 'Major',
        'location': 'Orlando, FL',
        'teams': 2,
        'primary_tie_ins': ['SEC', 'Big Ten'],
        'selection_order': 7,
        'payout': '$2.75M'
    },
    'outback_bowl': {
        'name': 'Outback Bowl',
        'tier': 'Major',
        'location': 'Tampa, FL',
        'teams': 2,
        'primary_tie_ins': ['SEC', 'Big Ten'],
        'selection_order': 8,
        'payout': '$2.5M'
    },
    'alamo_bowl': {
        'name': 'Alamo Bowl',
        'tier': 'Major',
        'location': 'San Antonio, TX',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'Pac 12'],
        'selection_order': 9,
        'payout': '$2.4M'
    },
    'holiday_bowl': {
        'name': 'Holiday Bowl',
        'tier': 'Major',
        'location': 'San Diego, CA',
        'teams': 2,
        'primary_tie_ins': ['Pac 12', 'ACC'],
        'selection_order': 10,
        'payout': '$2.2M'
    },
    'gator_bowl': {
        'name': 'Gator Bowl',
        'tier': 'Major',
        'location': 'Jacksonville, FL',
        'teams': 2,
        'primary_tie_ins': ['ACC', 'SEC'],
        'selection_order': 11,
        'payout': '$2.1M'
    },
    'sun_bowl': {
        'name': 'Sun Bowl',
        'tier': 'Major',
        'location': 'El Paso, TX',
        'teams': 2,
        'primary_tie_ins': ['Pac 12', 'ACC'],
        'selection_order': 12,
        'payout': '$2M'
    },
    
    # Conference Tie-In Bowls
    'music_city_bowl': {
        'name': 'Music City Bowl',
        'tier': 'Conference',
        'location': 'Nashville, TN',
        'teams': 2,
        'primary_tie_ins': ['SEC', 'Big Ten'],
        'selection_order': 13,
        'payout': '$1.8M'
    },
    'las_vegas_bowl': {
        'name': 'Las Vegas Bowl',
        'tier': 'Conference',
        'location': 'Las Vegas, NV',
        'teams': 2,
        'primary_tie_ins': ['Pac 12', 'SEC'],
        'selection_order': 14,
        'payout': '$1.7M'
    },
    'texas_bowl': {
        'name': 'Texas Bowl',
        'tier': 'Conference',
        'location': 'Houston, TX',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'SEC'],
        'selection_order': 15,
        'payout': '$1.6M'
    },
    'duke_mayo_bowl': {
        'name': "Duke's Mayo Bowl",
        'tier': 'Conference',
        'location': 'Charlotte, NC',
        'teams': 2,
        'primary_tie_ins': ['ACC', 'Big Ten'],
        'selection_order': 16,
        'payout': '$1.5M'
    },
    'liberty_bowl': {
        'name': 'Liberty Bowl',
        'tier': 'Conference',
        'location': 'Memphis, TN',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'SEC'],
        'selection_order': 17,
        'payout': '$1.4M'
    },
    'armed_forces_bowl': {
        'name': 'Armed Forces Bowl',
        'tier': 'Conference',
        'location': 'Fort Worth, TX',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'American'],
        'selection_order': 18,
        'payout': '$1.3M'
    },
    
    # G5 and Lower Tier Bowls
    'new_mexico_bowl': {
        'name': 'New Mexico Bowl',
        'tier': 'G5',
        'location': 'Albuquerque, NM',
        'teams': 2,
        'primary_tie_ins': ['Mountain West', 'Conference USA'],
        'selection_order': 25,
        'payout': '$1M'
    },
    'boca_raton_bowl': {
        'name': 'Boca Raton Bowl',
        'tier': 'G5',
        'location': 'Boca Raton, FL',
        'teams': 2,
        'primary_tie_ins': ['American', 'MAC'],
        'selection_order': 26,
        'payout': '$1M'
    },
    'frisco_bowl': {
        'name': 'Frisco Bowl',
        'tier': 'G5',
        'location': 'Frisco, TX',
        'teams': 2,
        'primary_tie_ins': ['American', 'Mountain West'],
        'selection_order': 27,
        'payout': '$1M'
    },
    'cure_bowl': {
        'name': 'Cure Bowl',
        'tier': 'G5',
        'location': 'Orlando, FL',
        'teams': 2,
        'primary_tie_ins': ['American', 'Sun Belt'],
        'selection_order': 28,
        'payout': '$1M'
    },
    'gasparilla_bowl': {
        'name': 'Gasparilla Bowl',
        'tier': 'G5',
        'location': 'St. Petersburg, FL',
        'teams': 2,
        'primary_tie_ins': ['American', 'ACC'],
        'selection_order': 29,
        'payout': '$1M'
    },
    'camellia_bowl': {
        'name': 'Camellia Bowl',
        'tier': 'G5',
        'location': 'Montgomery, AL',
        'teams': 2,
        'primary_tie_ins': ['MAC', 'Sun Belt'],
        'selection_order': 30,
        'payout': '$1M'
    }
}

# Define major college football rivalries
RIVALRIES = {
    # SEC Rivalries
    'Alabama': ['Auburn', 'Tennessee', 'LSU'],
    'Auburn': ['Alabama', 'Georgia'],
    'Georgia': ['Auburn', 'Florida', 'Georgia Tech'],
    'Florida': ['Georgia', 'Florida State', 'Miami'],
    'LSU': ['Alabama', 'Arkansas', 'Ole Miss'],
    'Arkansas': ['LSU', 'Texas', 'Missouri'],
    'Tennessee': ['Alabama', 'Kentucky', 'Vanderbilt'],
    'Kentucky': ['Tennessee', 'Louisville'],
    'Vanderbilt': ['Tennessee'],
    'Mississippi State': ['Ole Miss'],
    'Ole Miss': ['Mississippi State', 'LSU'],
    'Missouri': ['Arkansas', 'Kansas'],
    'South Carolina': ['Clemson', 'North Carolina'],
    'Texas': ['Arkansas', 'Texas A&M', 'Oklahoma'],
    'Texas A&M': ['Texas', 'LSU'],
    
    # Big Ten Rivalries
    'Ohio State': ['Michigan', 'Penn State'],
    'Michigan': ['Ohio State', 'Michigan State'],
    'Michigan State': ['Michigan', 'Penn State'],
    'Penn State': ['Ohio State', 'Michigan State'],
    'Wisconsin': ['Minnesota', 'Iowa'],
    'Minnesota': ['Wisconsin', 'Iowa'],
    'Iowa': ['Wisconsin', 'Minnesota', 'Iowa State'],
    'Illinois': ['Northwestern', 'Indiana'],
    'Northwestern': ['Illinois'],
    'Indiana': ['Illinois', 'Purdue'],
    'Purdue': ['Indiana'],
    'Nebraska': ['Iowa', 'Wisconsin'],
    'Maryland': ['Virginia', 'Penn State'],
    'Rutgers': ['Penn State'],
    
    # Big XII Rivalries
    'Oklahoma': ['Texas', 'Oklahoma State'],
    'Oklahoma State': ['Oklahoma'],
    'Texas Tech': ['Texas', 'Baylor'],
    'Baylor': ['Texas Tech', 'TCU'],
    'TCU': ['Baylor', 'SMU'],
    'West Virginia': ['Virginia Tech', 'Pittsburgh'],
    'Kansas': ['Kansas State', 'Missouri'],
    'Kansas State': ['Kansas'],
    'Iowa State': ['Iowa'],
    'Cincinnati': ['Louisville'],
    'Houston': ['Rice'],
    'UCF': ['South Florida'],
    
    # ACC Rivalries
    'Clemson': ['South Carolina', 'Georgia Tech'],
    'Florida State': ['Florida', 'Miami'],
    'Miami': ['Florida State', 'Florida'],
    'North Carolina': ['NC State', 'Duke', 'South Carolina'],
    'NC State': ['North Carolina', 'Wake Forest'],
    'Duke': ['North Carolina', 'Wake Forest'],
    'Wake Forest': ['NC State', 'Duke'],
    'Virginia': ['Virginia Tech', 'Maryland'],
    'Virginia Tech': ['Virginia', 'West Virginia'],
    'Pittsburgh': ['West Virginia', 'Penn State'],
    'Georgia Tech': ['Georgia', 'Clemson'],
    'Louisville': ['Kentucky', 'Cincinnati'],
    'Boston College': ['Syracuse'],
    'Syracuse': ['Boston College'],
    
    # Pac 12 / West Coast
    'Stanford': ['California'],
    'California': ['Stanford'],
    'Oregon': ['Oregon State', 'Washington'],
    'Oregon State': ['Oregon'],
    'Washington': ['Oregon', 'Washington State'],
    'Washington State': ['Washington'],
    'UCLA': ['USC'],
    'USC': ['UCLA'],
    
    # Independent
    'Notre Dame': ['USC', 'Michigan', 'Navy', 'Stanford'],
    'Navy': ['Notre Dame', 'Army'],
    'Army': ['Navy'],
    
    # G5 Major Rivalries
    'SMU': ['TCU', 'Rice', 'Houston'],
    'Rice': ['SMU', 'Houston'],
    'Memphis': ['UAB', 'Tulane'],
    'UAB': ['Memphis'],
    'Tulane': ['Memphis', 'Louisiana'],
    'Louisiana': ['Tulane'],
    'Boise State': ['Fresno State'],
    'Fresno State': ['Boise State'],
    'Air Force': ['Army', 'Navy'],
    'Colorado State': ['Colorado'],
    'Wyoming': ['Colorado State'],
    'Marshall': ['West Virginia'],
    'Troy': ['South Alabama'],
    'South Alabama': ['Troy'],
    'App State': ['Georgia Southern'],
    'Georgia Southern': ['App State'],
    'Miami (OH)': ['Cincinnati', 'Ohio'],
    'Ohio': ['Miami (OH)'],
    'Toledo': ['Bowling Green'],
    'Bowling Green': ['Toledo'],
    'Northern Illinois': ['Western Michigan'],
    'Western Michigan': ['Northern Illinois'],
}

BOWL_GAMES_DETECTION = {
    # New Year's Six
    'Rose Bowl': ['rose bowl', 'rose bowl game', 'granddaddy'],
    'Sugar Bowl': ['sugar bowl', 'sugar bowl game'],
    'Orange Bowl': ['orange bowl', 'orange bowl game'],
    'Cotton Bowl': ['cotton bowl', 'cotton bowl classic'],
    'Fiesta Bowl': ['fiesta bowl', 'fiesta bowl game'],
    'Peach Bowl': ['peach bowl', 'chick-fil-a peach bowl', 'cfp peach bowl'],
    
    # Major Bowls
    'Citrus Bowl': ['citrus bowl', 'capital one citrus bowl'],
    'Outback Bowl': ['outback bowl', 'outback steakhouse bowl'],
    'Alamo Bowl': ['alamo bowl', 'valero alamo bowl'],
    'Holiday Bowl': ['holiday bowl', 'san diego county credit union holiday bowl'],
    'Gator Bowl': ['gator bowl', 'taxslayer gator bowl'],
    'Sun Bowl': ['sun bowl', 'tony the tiger sun bowl'],
    
    # Conference Championship Bowls
    'Music City Bowl': ['music city bowl', 'transperfect music city bowl'],
    'Las Vegas Bowl': ['las vegas bowl', 'srs distribution las vegas bowl'],
    'Texas Bowl': ['texas bowl', 'texas bowl game'],
    'Duke\'s Mayo Bowl': ['duke mayo bowl', 'dukes mayo bowl', 'mayo bowl'],
    'Liberty Bowl': ['liberty bowl', 'autozone liberty bowl'],
    'Armed Forces Bowl': ['armed forces bowl', 'lockheed martin armed forces bowl'],
    
    # Additional Bowls
    'ReliaQuest Bowl': ['reliaquset bowl', 'outback bowl', 'tampa bowl'],
    'Gasparilla Bowl': ['gasparilla bowl', 'bad boy mowers gasparilla bowl'],
    'Cure Bowl': ['cure bowl', 'cricket celebration bowl'],
    'New Mexico Bowl': ['new mexico bowl', 'dreamstyle stadium new mexico bowl'],
    'Frisco Bowl': ['frisco bowl', 'frisco football classic'],
    'Boca Raton Bowl': ['boca raton bowl', 'cheribundi boca raton bowl'],
    'Camellia Bowl': ['camellia bowl', 'raycom media camellia bowl'],
    'New Orleans Bowl': ['new orleans bowl', 'r+l carriers new orleans bowl'],
    'Cure Bowl': ['cure bowl', 'makers wanted bahamas bowl'],
    'Fenway Bowl': ['fenway bowl', 'wasabi fenway bowl'],
    'Pinstripe Bowl': ['pinstripe bowl', 'new era pinstripe bowl'],
    'Quick Lane Bowl': ['quick lane bowl', 'ford motor company quick lane bowl'],
    'Military Bowl': ['military bowl', 'peraton military bowl'],
    'First Responder Bowl': ['first responder bowl', 'servpro first responder bowl'],
    'Birmingham Bowl': ['birmingham bowl', 'ticketsmarter birmingham bowl'],
    'Independence Bowl': ['independence bowl', 'radiance technologies independence bowl'],
    'Rate Bowl': ['guaranteed rate bowl', 'rate bowl'],
    'Hawaii Bowl': ['hawaii bowl', 'eia hawaii bowl'],
    'Bahamas Bowl': ['bahamas bowl', 'makers wanted bahamas bowl'],
    'Famous Toastery Bowl': ['famous toastery bowl', 'toastery bowl'],
    'Myrtle Beach Bowl': ['myrtle beach bowl', 'championship myrtle beach bowl'],
    'Potato Bowl': ['potato bowl', 'famous idaho potato bowl'],
    'Sports Bowl': ['potato bowl', 'famous idaho potato bowl'],
    'Pop-Tarts Bowl': ['pop-tarts bowl', 'pop tarts bowl'],
    'Arizona Bowl': ['arizona bowl', 'snoop dogg arizona bowl'],
    'Ventures Bowl': ['ventures bowl', 'venture bowl'],
    'LA Bowl': ['la bowl', 'los angeles bowl'],
    'Xbox Bowl': ['xbox bowl', 'x-box bowl'],

    
    # CFP Related
    'CFP National Championship': ['cfp national championship', 'national championship', 'championship game'],
    'CFP Semifinal': ['cfp semifinal', 'playoff semifinal', 'college football playoff semifinal'],
    'CFP Quarterfinal': ['cfp quaterfinal', 'playoff quarterfinal', 'college football playoff quarterfinal'],
    'CFP First Round': ['cfp first round', 'playoff first round', 'cfp first-round'],
    
    # Generic Detection
    'Bowl Game': ['bowl', 'bowl game'],  # Fallback for any unspecified bowl
}

SCHEDULE_MANIPULATION_PENALTIES = {
    "Multiple weak opponents late in season": 1.5,
    "Multiple FCS opponents scheduled": 1.0,
    "Excessive home game scheduling": 0.8
}


def detect_bowl_game(line_text):
    """Detect bowl game name from a line of text"""
    line_lower = line_text.lower().strip()

    # ADD THIS ONE LINE:
    print(f"  DEBUG: Testing '{line}' -> 'at' found: {'at' in line_lower}")
    
    # Check for specific bowl games first (most specific to least specific)
    for bowl_name, variations in BOWL_GAMES_DETECTION.items():
        if bowl_name == 'Bowl Game':  # Skip the generic fallback for now
            continue
            
        for variation in variations:
            if variation in line_lower:
                return bowl_name
    
    # Generic bowl detection as fallback
    if 'bowl' in line_lower and ('vs' in line_lower or 'at' in line_lower or '@' in line_lower):
        # Try to extract a more specific name
        words = line_lower.split()
        bowl_index = -1
        for i, word in enumerate(words):
            if 'bowl' in word:
                bowl_index = i
                break
        
        if bowl_index > 0:
            # Try to get the word before "bowl"
            potential_name = words[bowl_index - 1].title() + ' Bowl'
            return potential_name
        else:
            return 'Bowl Game'
    
    return None

# Add this date formatting filter
@app.template_filter('format_date')
def format_date(date_string):
    """Format date string for display"""
    if not date_string:
        return ""
    
    try:
        # Parse the date string (YYYY-MM-DD format)
        date_obj = datetime.strptime(date_string, '%Y-%m-%d')
        
        # Format as "Sat, Aug 23"
        return date_obj.strftime('%a, %b %d')
    except:
        return date_string  # Return original if parsing fails

@app.template_filter('format_date_header')
def format_date_header(date_string):
    """Format date string for section headers"""
    if not date_string or date_string == 'No Date':
        return "Date TBD"
    
    try:
        # Parse the date string (YYYY-MM-DD format)
        date_obj = datetime.strptime(date_string, '%Y-%m-%d')
        
        # Format as "Saturday, August 23"
        return date_obj.strftime('%A, %B %d')
    except:
        return date_string  # Return original if parsing fails


def get_bowl_eligible_teams():
    """Get all teams with 6+ wins (bowl eligible) - FCS wins don't count"""
    bowl_eligible = []
    
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            
            # Calculate REAL wins (excluding FCS)
            real_wins = 0
            for game in team_stats[team]['games']:
                if game['result'] == 'W' and not is_fcs_opponent(game['opponent']):
                    real_wins += 1
            
            # Bowl eligible = 6+ real wins (not counting FCS)
            if real_wins >= 6:
                team_data = {
                    'team': team,
                    'conference': conf_name,
                    'wins': real_wins,  # Real wins only
                    'total_wins': stats['total_wins'],  # Total wins including FCS
                    'losses': stats['total_losses'],
                    'adjusted_total': stats['adjusted_total']
                }
                bowl_eligible.append(team_data)
    
    # Sort by adjusted total (best teams first)
    bowl_eligible.sort(key=lambda x: x['adjusted_total'], reverse=True)
    return bowl_eligible

def get_conference_bowl_teams():
    """Get available teams by conference for bowl selection"""
    bowl_teams_by_conf = {}
    
    # Get conference champions and bowl eligible teams
    champions = get_conference_champions()
    bowl_eligible = get_bowl_eligible_teams()
    
    # Organize teams by conference (excluding CFP teams)
    cfp_bracket = generate_cfp_bracket()
    cfp_team_names = {team['team'] for team in cfp_bracket['all_teams']}
    
    for conf_name in CONFERENCES.keys():
        conf_teams = [team for team in bowl_eligible 
                     if team['conference'] == conf_name and team['team'] not in cfp_team_names]
        bowl_teams_by_conf[conf_name] = conf_teams[:8]  # Max 8 bowl teams per conference
    
    return bowl_teams_by_conf, champions

def generate_bowl_projections():
    """Generate complete bowl projections"""
    # Get CFP bracket (already have this)
    cfp_bracket = generate_cfp_bracket()
    
    # Get available teams for bowls
    bowl_teams_by_conf, champions = get_conference_bowl_teams()
    
    # Get all bowl eligible teams not in CFP
    cfp_team_names = {team['team'] for team in cfp_bracket['all_teams']}
    at_large_pool = [team for team in get_bowl_eligible_teams() 
                     if team['team'] not in cfp_team_names]
    
    bowl_projections = []
    used_teams = set()
    
    # Process bowls in selection order
    sorted_bowls = sorted(BOWL_GAMES.items(), key=lambda x: x[1].get('selection_order', 99))
    
    for bowl_id, bowl_info in sorted_bowls:
        if bowl_info['tier'] == 'CFP':
            continue  # Skip CFP, handled separately
            
        projection = {
            'id': bowl_id,
            'name': bowl_info['name'],
            'tier': bowl_info['tier'],
            'location': bowl_info['location'],
            'payout': bowl_info['payout'],
            'teams': [],
            'tie_ins': bowl_info.get('primary_tie_ins', [])
        }
        
        # Try to fill based on tie-ins
        teams_needed = bowl_info['teams']
        for tie_in in bowl_info.get('primary_tie_ins', []):
            if teams_needed <= 0:
                break
                
            if tie_in in bowl_teams_by_conf:
                available_teams = [t for t in bowl_teams_by_conf[tie_in] if t['team'] not in used_teams]
                if available_teams:
                    selected_team = available_teams[0]
                    projection['teams'].append(selected_team)
                    used_teams.add(selected_team['team'])
                    teams_needed -= 1
        
        # Fill remaining spots with at-large teams
        while teams_needed > 0:
            available_at_large = [t for t in at_large_pool if t['team'] not in used_teams]
            if not available_at_large:
                break
            selected_team = available_at_large[0]
            projection['teams'].append(selected_team)
            used_teams.add(selected_team['team'])
            teams_needed -= 1
        
        # Only add bowl if it has at least one team
        if projection['teams']:
            bowl_projections.append(projection)
    
    # Add conference championships
    conf_championships = []
    for conf_name, champion in champions.items():
        if conf_name not in ['Independent', 'Pac 12']:  # Skip independents and Pac 12
            # Get second place team
            conf_teams = [team for team in get_bowl_eligible_teams() 
                         if team['conference'] == conf_name and team['team'] != champion['team']]
            runner_up = conf_teams[0] if conf_teams else None
            
            conf_championships.append({
                'name': f'{conf_name} Championship',
                'teams': [champion, runner_up] if runner_up else [champion],
                'tier': 'Championship'
            })
    
    return {
        'cfp_bracket': cfp_bracket,
        'bowl_projections': bowl_projections,
        'conference_championships': conf_championships,
        'total_bowl_teams': len(used_teams) + len(cfp_bracket['all_teams'])
    }

def is_rivalry_game(team1, team2):
    """Check if two teams are rivals"""
    return (team2 in RIVALRIES.get(team1, []) or 
            team1 in RIVALRIES.get(team2, []))

def get_rivalry_bonus(team_name, opponent_name):
    """
    Calculate rivalry bonus for beating a rival.
    Returns bonus points to add to victory value.
    """
    if not is_rivalry_game(team_name, opponent_name):
        return 0.0
    
    # Different tiers of rivalry bonuses based on intensity
    major_rivalries = {
        # Tier 1: Historic, intense rivalries (1.0 bonus)
        ('Alabama', 'Auburn'): 1.0,
        ('Ohio State', 'Michigan'): 1.0,
        ('Texas', 'Oklahoma'): 1.0,
        ('Florida', 'Georgia'): 1.0,
        ('USC', 'UCLA'): 1.0,
        ('Army', 'Navy'): 1.0,
        ('Florida State', 'Miami'): 1.0,
        ('Clemson', 'South Carolina'): 1.0,
        ('North Carolina', 'NC State'): 1.0,
        ('Notre Dame', 'USC'): 1.0,
        ('Virginia', 'Virginia Tech'): 1.0,
        ('Stanford', 'California'): 1.0,
        ('Oregon', 'Oregon State'): 1.0,
        ('Washington', 'Washington State'): 1.0,
        
        # Add more Tier 1 rivalries as needed
    }
    
    # Check if this is a Tier 1 rivalry (order doesn't matter)
    rivalry_pair = tuple(sorted([team_name, opponent_name]))
    for (team_a, team_b), bonus in major_rivalries.items():
        if rivalry_pair == tuple(sorted([team_a, team_b])):
            return bonus
    
    # Default rivalry bonus for other rivalries
    return 0.6  # Standard rivalry bonus

def calculate_victory_value_with_rivalry(game, team_name):
    """
    Calculate victory value with special FCS penalty
    """
    if game['result'] != 'W':
        return 0.0
    
    opponent = game['opponent']
    team_score = game['team_score']
    opp_score = game['opp_score']
    margin = team_score - opp_score
    location = game['home_away']
    
    # Check if this is an FCS game for special handling
    is_fcs_game = (opponent == 'FCS' or opponent.upper() == 'FCS')
    
    # 1. Base Opponent Quality (0.5 for FCS, 1-10 for others)
    opponent_quality = get_current_opponent_quality(opponent)
    
    # 2. Location Multiplier (no bonus for FCS games)
    if is_fcs_game:
        location_mult = 1.0  # No location bonus for beating FCS teams
    else:
        location_multipliers = {
            'Home': 1.0,
            'Away': 1.3,    # Road wins worth 30% more
            'Neutral': 1.15  # Neutral site wins worth 15% more
        }
        location_mult = location_multipliers.get(location, 1.0)
    
    # 3. Margin Bonus (severely limited for FCS)
    if is_fcs_game:
        # FCS games get minimal margin bonus regardless of score
        margin_bonus = min(0.2, margin * 0.02)  # Max 0.2 bonus, very small scaling
    else:
        # Normal margin bonus for real opponents
        if margin <= 0:
            margin_bonus = 0
        elif margin <= 7:
            margin_bonus = margin * 0.1  # Linear up to 7 points
        elif margin <= 14:
            margin_bonus = 0.7 + (margin - 7) * 0.08  # Slower growth 7-14
        elif margin <= 21:
            margin_bonus = 1.26 + (margin - 14) * 0.04  # Even slower 14-21
        else:
            margin_bonus = 1.54 + (margin - 21) * 0.02  # Minimal benefit beyond 21
    
    # 4. Conference Context Bonus (none for FCS)
    if is_fcs_game:
        conf_bonus = 0  # No conference bonus for FCS games
    else:
        team_conf = get_team_conference(team_name)
        opp_conf = get_team_conference(opponent)
        
        conf_bonus = 0
        if team_conf in P4_CONFERENCES and opp_conf in P4_CONFERENCES:
            conf_bonus = 0.3  # P4 vs P4 bonus
        elif team_conf in G5_CONFERENCES and opp_conf in P4_CONFERENCES:
            conf_bonus = 0.5  # G5 beating P4 major bonus
    
    # 5. Rivalry Bonus (FCS can't be rivals)
    if is_fcs_game:
        rivalry_bonus = 0  # No rivalry bonus for FCS
    else:
        rivalry_bonus = get_rivalry_bonus(team_name, opponent)
    
    # 6. Calculate Final Victory Value
    base_value = opponent_quality * location_mult
    total_value = base_value + margin_bonus + conf_bonus + rivalry_bonus
    
    # 7. Extra FCS penalty - cap maximum value
    if is_fcs_game:
        total_value = min(total_value, 1.0)  # FCS wins can never be worth more than 1.0 point
    
    return round(total_value, 2)


def get_team_logo_url(team_name, size='60'):
    """
    Get local logo URL for a team with specified size
    
    Args:
        team_name (str): Name of the team
        size (str): Logo size - '20', '60', '120' (default: '60')
    
    Returns:
        str: URL path to logo, or None if team not found
    """
    team_id = TEAM_LOGOS.get(team_name)
    if team_id:
        return f"/static/images/team-logos/{team_id}_{size}.png"
    return None
    
# All conferences organized
CONFERENCES = {
    'ACC': ACC_TEAMS,
    'Big Ten': BIG_TEN_TEAMS,
    'Big XII': BIG_XII_TEAMS,
    'Pac 12': PAC_12_TEAMS,
    'SEC': SEC_TEAMS,
    'Independent': INDEPENDENT_TEAMS,
    'American': AMERICAN_TEAMS,
    'Conference USA': CONFERENCE_USA_TEAMS,
    'MAC': MAC_TEAMS,
    'Mountain West': MOUNTAIN_WEST_TEAMS,
    'Sun Belt': SUN_BELT_TEAMS
}

# Scheduled games storage
scheduled_games = []

# Team name mappings for unknown teams
team_mappings = {}

# All teams combined
TEAMS = (ACC_TEAMS + BIG_TEN_TEAMS + BIG_XII_TEAMS + PAC_12_TEAMS + SEC_TEAMS + 
         INDEPENDENT_TEAMS + AMERICAN_TEAMS + CONFERENCE_USA_TEAMS + MAC_TEAMS + 
         MOUNTAIN_WEST_TEAMS + SUN_BELT_TEAMS)

WEEKS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', 'Bowls', 'CFP']
GAME_TYPES = ['P4', 'G5', 'None']

# P4 and G5 Conference Classifications
P4_CONFERENCES = ['ACC', 'Big Ten', 'Big XII', 'Pac 12', 'SEC']
G5_CONFERENCES = ['American', 'Conference USA', 'MAC', 'Mountain West', 'Sun Belt']
P4_INDEPENDENT_TEAMS = ['Notre Dame']
G5_INDEPENDENT_TEAMS = ['Connecticut']
NONE_INDEPENDENT_TEAMS = ['FCS']

# In-memory storage for games and rankings
games_data = []
team_stats = defaultdict(lambda: {
    'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0,
    'p4_wins': 0, 'p4_losses': 0, 'g5_wins': 0, 'g5_losses': 0,
    'home_wins': 0, 'road_wins': 0, 'margin_of_victory_total': 0,
    'games': []
})

def get_team_conference(team_name):
    """Get the conference for a given team"""
    for conf_name, teams in CONFERENCES.items():
        if team_name in teams:
            return conf_name
    return 'Unknown'

def is_p4_team(team_name):
    """Determine if a team is P4"""
    if team_name in P4_INDEPENDENT_TEAMS:
        return True
    conference = get_team_conference(team_name)
    return conference in P4_CONFERENCES

def is_g5_team(team_name):
    """Determine if a team is G5"""
    if team_name in G5_INDEPENDENT_TEAMS:
        return True
    conference = get_team_conference(team_name)
    return conference in G5_CONFERENCES

def get_auto_game_type(team_name):
    """Get the automatic game type for a team"""
    if is_p4_team(team_name):
        return 'P4'
    elif is_g5_team(team_name):
        return 'G5'
    else:
        return 'None'

# Admin credentials from environment variables
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'testuser')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'testpass')

def is_admin():
    """Check if user is logged in as admin"""
    return session.get('admin_logged_in', False)

@app.context_processor
def inject_user():
    return dict(
        is_admin=session.get('admin_logged_in', False),
        get_team_logo_url=get_team_logo_url,
        get_current_week_info=get_current_week_info,
        CFB_ML_ENABLED=CFB_ML_ENABLED,
        CFB_GEN_AI_ENABLED=CFB_GEN_AI_ENABLED

    )


def login_required(f):
    """Decorator to require admin login for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function        

# Data persistence functions
def save_data():
    """Database auto-saves, so this function now does nothing"""
    pass  # Database automatically saves when we commit transactions


def load_data():
    """Initialize database if needed - replaces JSON loading"""
    try:
        with app.app_context():
            db.create_all()
            print("Database tables initialized")
    except Exception as e:
        print(f"Error initializing database: {e}")

def get_games_data():
    """Get all games from database"""
    games = Game.query.order_by(Game.date_added).all()
    return [game.to_dict() for game in games]

def get_team_stats_dict():
    """Get team stats from database"""
    stats_dict = defaultdict(lambda: {
        'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0,
        'home_wins': 0, 'road_wins': 0, 'margin_of_victory_total': 0,
        'games': []
    })
    
    team_stats_records = TeamStats.query.all()
    for record in team_stats_records:
        stats_dict[record.team_name] = record.to_dict()
    
    return stats_dict




def get_conference_champions():
    """Determine conference champions based on current standings"""
    champions = {}
    
    for conf_name, teams in CONFERENCES.items():
        if conf_name in ['Independent', 'Pac 12']:  # Skip independents and Pac 12
            continue
            
        # Get all teams in conference with their stats
        conf_teams = []
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            conf_teams.append(stats)
        
        # Sort by adjusted total (highest first)
        conf_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        if conf_teams:
            champions[conf_name] = conf_teams[0]
    
    return champions

def generate_cfp_bracket():
    """Generate 12-team CFP bracket based on current rankings - FIXED VERSION"""
    try:
        # Get all teams ranked by adjusted total
        all_teams = []
        for conf_name, teams in CONFERENCES.items():
            for team in teams:
                stats = calculate_comprehensive_stats(team)
                
                # Calculate real wins (excluding FCS) for display
                real_wins = 0
                total_wins = stats['total_wins']
                if team in team_stats:
                    for game in team_stats[team]['games']:
                        if game['result'] == 'W' and not is_fcs_opponent(game['opponent']):
                            real_wins += 1
                else:
                    real_wins = total_wins  # Fallback if no game data
                
                team_data = {
                    'team': team,
                    'conference': conf_name,
                    'total_wins': total_wins,
                    'total_losses': stats['total_losses'],
                    'real_wins': real_wins,
                    'adjusted_total': stats['adjusted_total']
                }
                all_teams.append(team_data)
        
        # Sort by adjusted total (highest first)
        all_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        # Get conference champions (using existing function)
        champions = get_conference_champions()
        
        # Ensure we have at least some teams to work with
        if len(all_teams) < 4:
            # Return minimal bracket if not enough teams
            return {
                'first_round_byes': all_teams[:4] if len(all_teams) >= 4 else all_teams,
                'first_round_games': [],
                'all_teams': all_teams[:12] if len(all_teams) >= 12 else all_teams,
                'automatic_qualifiers': [],
                'at_large_display': [],
                'conference_champions': champions if champions else {}
            }
        
        # Step 1: Get the top 5 ranked conference champions (automatic qualifiers)
        automatic_qualifiers = []
        for team in all_teams:
            if team['conference'] in champions and champions[team['conference']]['team'] == team['team']:
                automatic_qualifiers.append(team)
                if len(automatic_qualifiers) == 5:
                    break
        
        # Step 2: Get the top 12 teams overall
        top_12_teams = all_teams[:12].copy() if len(all_teams) >= 12 else all_teams.copy()
        
        # Step 3: Ensure all auto-qualifiers are in the playoff
        auto_qualifier_names = {team['team'] for team in automatic_qualifiers}
        
        # Find auto-qualifiers not in top 12
        missing_auto_qualifiers = [team for team in automatic_qualifiers if team['team'] not in [t['team'] for t in top_12_teams]]
        
        # Replace lowest-ranked non-auto-qualifiers with missing auto-qualifiers
        for missing_team in missing_auto_qualifiers:
            # Find the lowest-ranked team in top_12 that's not an auto-qualifier
            for i in range(len(top_12_teams) - 1, -1, -1):  # Start from bottom
                if top_12_teams[i]['team'] not in auto_qualifier_names:
                    top_12_teams[i] = missing_team
                    break
        
        # Step 4: Sort the final teams and assign seeds 1-12
        playoff_teams = top_12_teams
        playoff_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        for i, team in enumerate(playoff_teams):
            team['seed'] = i + 1
        
        # Step 5: First Round Byes go to TOP 4 TEAMS (seeds 1-4)
        first_round_byes = playoff_teams[:4]
        
        # At-Large Display: Seeds 5-12
        at_large_display = playoff_teams[4:] if len(playoff_teams) > 4 else []
        
        # Generate first round games if we have enough teams
        first_round_games = []
        if len(playoff_teams) >= 8:
            first_round_games = [
                {'higher_seed': playoff_teams[4], 'lower_seed': playoff_teams[11], 'game_num': 1} if len(playoff_teams) > 11 else None,
                {'higher_seed': playoff_teams[5], 'lower_seed': playoff_teams[10], 'game_num': 2} if len(playoff_teams) > 10 else None,
                {'higher_seed': playoff_teams[6], 'lower_seed': playoff_teams[9], 'game_num': 3} if len(playoff_teams) > 9 else None,
                {'higher_seed': playoff_teams[7], 'lower_seed': playoff_teams[8], 'game_num': 4} if len(playoff_teams) > 8 else None,
            ]
            # Remove None entries
            first_round_games = [game for game in first_round_games if game is not None]
        
        # Generate bracket structure
        bracket = {
            'first_round_byes': first_round_byes,
            'first_round_games': first_round_games,
            'all_teams': playoff_teams,
            'automatic_qualifiers': automatic_qualifiers,
            'at_large_display': at_large_display,
            'conference_champions': champions if champions else {}
        }
        
        return bracket
        
    except Exception as e:
        print(f"Error in generate_cfp_bracket: {e}")
        # Return safe fallback bracket
        return {
            'first_round_byes': [],
            'first_round_games': [],
            'all_teams': [],
            'automatic_qualifiers': [],
            'at_large_display': [],
            'conference_champions': {}
        }


# ===============================================
# MODULE 1: OPPONENT QUALITY ENGINE
# ===============================================

CONFERENCE_STRENGTH_MULTIPLIERS = {
    # P4 Conferences
    'SEC': 1.05,           # Slightly above baseline
    'Big Ten': 1.03,       # Strong top to bottom
    'Big XII': 1.00,       # Baseline P4
    'ACC': 0.98,           # Slightly weaker P4
    'Pac 12': 0.95,        # Weakened by departures
    
    # Strong G5
    'American': 0.85,      # Best G5 conference
    'Mountain West': 0.83, # Competitive G5
    
    # Average G5
    'Sun Belt': 0.82,      # Rising G5 conference
    'MAC': 0.80,           # Traditional G5
    
    # Weaker G5
    'Conference USA': 0.78, # Weakest G5
    
    # Independent
    'Independent': 1.0      # Varies by team (Notre Dame vs UConn)
}

def calculate_all_basic_team_strengths():
    """Pre-calculate basic strength ratings for all teams to avoid recursion"""
    basic_strengths = {}
    
    # Get all teams from database
    all_teams = TeamStats.query.all()
    
    for team_record in all_teams:
        team_name = team_record.team_name
        stats = team_record.to_dict()
        total_games = stats['wins'] + stats['losses']
        
        if total_games == 0:
            basic_strengths[team_name] = 5.0
        else:
            win_pct = stats['wins'] / total_games
            basic_strengths[team_name] = 2.0 + (win_pct * 6.0)  # Scale 2-8 based on win percentage
    
    return basic_strengths

def get_enhanced_opponent_quality(opponent_name):
    """Enhanced opponent quality WITHOUT conference strength multipliers"""
    
    # Handle FCS specially (unchanged)
    if opponent_name == 'FCS' or opponent_name.upper() == 'FCS':
        return 0.5
    
    if opponent_name not in team_stats:
        return 1.5
    
    # Use cached basic strengths to avoid recursion
    basic_strengths_cache = calculate_all_basic_team_strengths()
    base_strength = calculate_team_base_strength(opponent_name, basic_strengths_cache)
    
    # REMOVED: Conference multiplier section
    # No more artificial boosts for conference membership
    
    # Apply recent form bonus (keep this - it's based on actual performance)
    recent_games = team_stats[opponent_name]['games'][-4:]
    if len(recent_games) >= 2:
        recent_wins = sum(1 for g in recent_games if g['result'] == 'W')
        recent_form_bonus = (recent_wins / len(recent_games) - 0.5) * 1.0
        base_strength += recent_form_bonus
    
    return max(1.0, min(10.0, base_strength))

def calculate_team_base_strength(team_name, basic_strengths_cache=None):
    """
    Calculate a team's base strength using pre-computed basic strengths to avoid recursion.
    Returns value between 1-10 (10 = elite, 5 = average, 1 = terrible)
    """
    # If no cache provided, calculate it (fallback for single calls)
    if basic_strengths_cache is None:
        basic_strengths_cache = calculate_all_basic_team_strengths()
    
    team_record = TeamStats.query.filter_by(team_name=team_name).first()
    if not team_record:
        return 5.0
    
    stats = team_record.to_dict()
    total_games = stats['wins'] + stats['losses']
    
    if total_games == 0:
        return 5.0
    
    # Calculate base win percentage component
    win_pct = stats['wins'] / total_games
    base_score = 2.0 + (win_pct * 4.0)  # 2-6 range from win percentage
    
    # Add opponent-adjusted component using pre-computed strengths
    opponent_quality_sum = 0
    game_count = 0
    
    for game in stats['games']:
        opponent = game['opponent']
        if opponent in basic_strengths_cache and opponent != team_name:
            # Use pre-computed strength instead of recursive call
            opp_strength = basic_strengths_cache[opponent]
            
            # Weight by game result and margin (same logic as before)
            if game['result'] == 'W':
                quality_bonus = (opp_strength - 5.0) * 0.3
                margin_factor = min(1.0, abs(game['team_score'] - game['opp_score']) / 14.0)
                opponent_quality_sum += quality_bonus * margin_factor
            else:
                quality_penalty = (5.0 - opp_strength) * 0.4
                margin_factor = min(1.0, abs(game['team_score'] - game['opp_score']) / 21.0)
                opponent_quality_sum -= quality_penalty * margin_factor
            
            game_count += 1
    
    if game_count > 0:
        avg_opponent_adjustment = opponent_quality_sum / game_count
        final_strength = base_score + avg_opponent_adjustment
    else:
        final_strength = base_score
    
     # NEW: Early season subdivision-level adjustments (add this section)
    if total_games <= 3:  # Apply only in early season
        team_conf = get_team_conference(team_name)
        print(f"EARLY SEASON ADJUSTMENT: {team_name} ({team_conf}) - games: {total_games}, final_strength: {final_strength}")
        
        
        if team_conf in P4_CONFERENCES:
            # P4 teams get quality floor - prevent 0-1 P4 teams from rating too low
            final_strength = max(final_strength, 4.0)
        elif team_conf in G5_CONFERENCES:
            # G5 teams get quality ceiling - prevent 1-0 G5 teams from rating too high  
            final_strength = min(final_strength, 6.5)

    return max(1.0, min(10.0, final_strength))

def get_current_opponent_quality(opponent_name):
    """Get current quality rating for an opponent (1-10 scale) with FCS independence"""
    
    # Special handling for FCS - ALWAYS return fixed quality regardless of record
    if opponent_name == 'FCS' or opponent_name.upper() == 'FCS':
        return 0.5  # Fixed quality - never changes regardless of FCS "record"
    
    # Handle other non-FBS opponents
    opponent_record = TeamStats.query.filter_by(team_name=opponent_name).first()  # 
    if not opponent_record:  # 
        return 1.5  # Lower default for unknown opponents
    
    # Use cached basic strengths to avoid recursion
    basic_strengths_cache = calculate_all_basic_team_strengths()
    base_strength = calculate_team_base_strength(opponent_name, basic_strengths_cache)
    
    # Adjust for recent form (last 4 games) - only for real teams
    opponent_stats = opponent_record.to_dict()  # 
    recent_games = opponent_stats['games'][-4:]  # 
    if len(recent_games) >= 2:
        recent_wins = sum(1 for g in recent_games if g['result'] == 'W')
        recent_form_bonus = (recent_wins / len(recent_games) - 0.5) * 1.0
        base_strength += recent_form_bonus
    
    return max(1.0, min(10.0, base_strength))

# ===============================================
# MODULE 2: ENHANCED VICTORY VALUE CALCULATOR  
# ===============================================

# Team-specific home field advantages
STRONG_HOME_FIELD_TEAMS = {
    # Top 5 - Most intimidating venues
    'LSU': 1.30,           # #1 Tiger Stadium
    'Alabama': 1.30,       # #2 Bryant-Denny Stadium  
    'Florida': 1.30,       # #3 Ben Hill Griffin Stadium
    'Penn State': 1.30,    # #4 Beaver Stadium
    'Auburn': 1.30,        # #5 Jordan-Hare Stadium
    
    # Tier 2 - Elite difficulty (6-10)
    'Tennessee': 1.25,     # #6 Neyland Stadium
    'Texas A&M': 1.25,    # #7 Kyle Field
    'Oregon': 1.25,       # #8 Autzen Stadium
    'Florida State': 1.25, # #9 Doak Campbell Stadium
    'Oklahoma State': 1.25, # #10 Boone Pickens Stadium
    
    # Tier 3 - Very tough (11-15)
    'Georgia': 1.20,       # #11 Sanford Stadium
    'Ohio State': 1.20,   # #12 Ohio Stadium
    'Clemson': 1.20,      # #13 Memorial Stadium (Death Valley)
    'Iowa': 1.20,         # #14 Kinnick Stadium
    'Wisconsin': 1.20,    # #15 Camp Randall Stadium
    
    # Tier 4 - Above average (16-20)
    'Oklahoma': 1.15,     # #16 Gaylord Family Memorial
    'Michigan': 1.15,     # #17 Michigan Stadium
    'Washington': 1.15,   # #18 Husky Stadium
    'Virginia Tech': 1.15, # #19 Lane Stadium
    'South Carolina': 1.15, # #20 Williams-Brice Stadium
    
    # Tier 5 - Notable venues (21-25)
    'Texas': 1.12,        # #21 DKR Memorial Stadium
    'Utah': 1.12,         # #22 Rice-Eccles Stadium
    'Nebraska': 1.12,     # #23 Memorial Stadium
    'Arkansas': 1.12,     # #24 Reynolds Razorback Stadium
    'Washington State': 1.12, # #25 Martin Stadium
    
    # Keep Notre Dame for its mystique factor
    'Notre Dame': 1.15,   # Historical significance
}

def calculate_margin_bonus_capped(margin, opponent_quality):
    """Enhanced margin bonus with quality-based caps"""
    if margin <= 0:
        return 0
    
    # Determine margin cap based on opponent quality
    if opponent_quality < 3.0:  # Very weak opponent
        max_margin_counted = 17  # Don't reward excessive blowouts
    elif opponent_quality < 5.0:  # Below average opponent
        max_margin_counted = 24  
    elif opponent_quality < 7.0:  # Average to good opponent
        max_margin_counted = 35
    else:  # Elite opponent
        max_margin_counted = 50  # No cap against top teams
    
    # Apply cap
    effective_margin = min(margin, max_margin_counted)
    
    # Apply existing diminishing returns formula
    if effective_margin <= 7:
        return effective_margin * 0.1
    elif effective_margin <= 14:
        return 0.7 + (effective_margin - 7) * 0.08
    elif effective_margin <= 21:
        return 1.26 + (effective_margin - 14) * 0.04
    else:
        return 1.54 + (effective_margin - 21) * 0.02

def get_enhanced_home_field_multiplier(team_name, location):
    """Enhanced home field advantage with team-specific factors"""
    if location != 'Home':
        return 1.0
    
    # Check if team has enhanced home field advantage
    home_multiplier = STRONG_HOME_FIELD_TEAMS.get(team_name, 1.0)
    return home_multiplier

def calculate_enhanced_victory_value(game, team_name):
    """Enhanced victory value with all new factors"""
    if game['result'] != 'W':
        return 0.0
    
    opponent = game['opponent']
    team_score = game['team_score']
    opp_score = game['opp_score']
    margin = team_score - opp_score
    location = game['home_away']
    week = game.get('week', '1')
    
    # Special FCS handling (existing)
    is_fcs_game = (opponent == 'FCS' or opponent.upper() == 'FCS')
    if is_fcs_game:
        # Existing FCS logic - minimal credit
        opponent_quality = 0.5
        location_mult = 1.0
        margin_bonus = min(0.2, margin * 0.02)
        conf_bonus = 0
        rivalry_bonus = 0
        total_value = min(1.0, opponent_quality + margin_bonus)
        return round(total_value, 2)
    
    # 1. Enhanced Opponent Quality
    opponent_quality = get_enhanced_opponent_quality(opponent)
    
    # 2. Enhanced Location Multiplier
    base_location_mult = {'Home': 1.0, 'Away': 1.3, 'Neutral': 1.15}.get(location, 1.0)
    home_field_mult = get_enhanced_home_field_multiplier(team_name, location)
    location_mult = base_location_mult * home_field_mult
    
    # 3. Enhanced Margin Bonus with Caps
    margin_bonus = calculate_margin_bonus_capped(margin, opponent_quality)
    
    # 4. Game Context Bonus (NEW)
    game_context_bonus = get_game_context_bonus(week, opponent)
    
    # 5. Travel Adjustment (NEW)
    travel_adjustment = calculate_travel_adjustment(team_name, opponent, location)
    
    # 6. Conference Context (existing)
    team_conf = get_team_conference(team_name)
    opp_conf = get_team_conference(opponent)
    conf_bonus = 0
    if team_conf in P4_CONFERENCES and opp_conf in P4_CONFERENCES:
        conf_bonus = 0.3
    elif team_conf in G5_CONFERENCES and opp_conf in P4_CONFERENCES:
        conf_bonus = 0.5
    
    # 7. Rivalry Bonus (existing)
    rivalry_bonus = get_rivalry_bonus(team_name, opponent)
    
    # 8. Temporal Weight (NEW)
    temporal_weight = get_temporal_weight_by_week(week)
    
    # Calculate final value
    base_value = opponent_quality * location_mult
    total_adjustments = (margin_bonus + game_context_bonus + travel_adjustment + 
                        conf_bonus + rivalry_bonus)
    
    final_value = (base_value + total_adjustments) * temporal_weight
    
    return round(final_value, 2)

def calculate_victory_value(game, team_name):
    """
    Calculate the value of a single victory.
    Returns a score typically between 0-15 (excellent wins can exceed 10)
    """
    if game['result'] != 'W':
        return 0.0
    
    opponent = game['opponent']
    team_score = game['team_score']
    opp_score = game['opp_score']
    margin = team_score - opp_score
    location = game['home_away']
    
    # 1. Base Opponent Quality (1-10 scale)
    opponent_quality = get_current_opponent_quality(opponent)
    
    # 2. Location Multiplier
    location_multipliers = {
        'Home': 1.0,
        'Away': 1.3,    # Road wins worth 30% more
        'Neutral': 1.15  # Neutral site wins worth 15% more
    }
    location_mult = location_multipliers.get(location, 1.0)
    
    # 3. Margin Bonus with Diminishing Returns
    # Peak efficiency at 14-point wins, diminishing returns after that
    if margin <= 0:
        margin_bonus = 0
    elif margin <= 7:
        margin_bonus = margin * 0.1  # Linear up to 7 points
    elif margin <= 14:
        margin_bonus = 0.7 + (margin - 7) * 0.08  # Slower growth 7-14
    elif margin <= 21:
        margin_bonus = 1.26 + (margin - 14) * 0.04  # Even slower 14-21
    else:
        margin_bonus = 1.54 + (margin - 21) * 0.02  # Minimal benefit beyond 21
    
    # 4. Conference Context Bonus
    team_conf = get_team_conference(team_name)
    opp_conf = get_team_conference(opponent)
    
    conf_bonus = 0
    if team_conf in P4_CONFERENCES and opp_conf in P4_CONFERENCES:
        conf_bonus = 0.3  # P4 vs P4 bonus
    elif team_conf in G5_CONFERENCES and opp_conf in P4_CONFERENCES:
        conf_bonus = 0.5  # G5 beating P4 major bonus
    
    # 5. Calculate Final Victory Value
    base_value = opponent_quality * location_mult
    total_value = base_value + margin_bonus + conf_bonus
    
    return round(total_value, 2)

# Add helper function to show bowl eligibility status:


def reset_prediction_to_pending(home_team, away_team, week):
    """Reset prediction back to pending when a game is deleted"""
    if not CFB_ML_ENABLED:
        return 0
    
    try:
        # Find all matching predictions for this game (check both orientations for neutral site games)
        predictions = CFBPredictionLog.query.filter(
            CFBPredictionLog.week == str(week),
            CFBPredictionLog.game_completed == True
        ).filter(
            db.or_(
                db.and_(CFBPredictionLog.home_team == home_team, CFBPredictionLog.away_team == away_team),
                db.and_(CFBPredictionLog.home_team == away_team, CFBPredictionLog.away_team == home_team)
            )
        ).all()
        
        predictions_reset = 0
        
        for prediction in predictions:
            # Reset prediction back to pending
            prediction.game_completed = False
            prediction.actual_winner = None
            prediction.actual_margin = None
            prediction.actual_total = None
            prediction.winner_correct = None
            prediction.margin_error = None
            prediction.total_error = None
            prediction.result_date = None
            
            predictions_reset += 1
        
        # Commit all updates
        db.session.commit()
        
        if predictions_reset > 0:
            flash(f'🤖 ML Tracking: Reset {predictions_reset} prediction(s) back to pending', 'info')
        
        return predictions_reset
    
    except Exception as e:
        db.session.rollback()
        print(f"🤖 Error resetting predictions: {e}")
        return 0


def log_game_result_to_ml(home_team, away_team, home_score, away_score, week, is_overtime=False):
    """Enhanced game result logging with over/under tracking"""
    if not CFB_ML_ENABLED:
        return
    
    try:
        # Determine actual winner and margin
        if home_score > away_score:
            actual_winner = home_team
            actual_margin = home_score - away_score
        else:
            actual_winner = away_team
            actual_margin = away_score - home_score
        
        # Calculate actual total
        actual_total = home_score + away_score
        
        # Find all matching predictions for this game
        predictions = CFBPredictionLog.query.filter(
            CFBPredictionLog.home_team == home_team,
            CFBPredictionLog.away_team == away_team,
            CFBPredictionLog.week == str(week),
            CFBPredictionLog.game_completed == False
        ).all()
        
        results_updated = 0
        
        for prediction in predictions:
            # Update actual results
            prediction.actual_winner = actual_winner
            prediction.actual_margin = actual_margin
            prediction.actual_total = actual_total
            prediction.game_completed = True
            prediction.result_date = datetime.utcnow()
            
            # Calculate accuracy metrics
            
            # FIXED: Sports betting spread logic
            predicted_spread = prediction.predicted_margin if prediction.predicted_margin else 0
            actual_margin_for_predicted_winner = actual_margin

            # FIXED: Sports betting spread logic
            if prediction.predicted_winner == actual_winner:
                # Winner predicted correctly, check if they covered the spread
                predicted_spread = prediction.predicted_margin if prediction.predicted_margin else 0
                prediction.winner_correct = (actual_margin >= predicted_spread)
            else:
                # Wrong winner predicted = automatically wrong
                prediction.winner_correct = False
            
            # Margin error
            if prediction.predicted_margin is not None:
                prediction.margin_error = abs(prediction.predicted_margin - actual_margin)
            
            # Total error (over/under)
            if prediction.predicted_total is not None:
                prediction.total_error = abs(prediction.predicted_total - actual_total)
            
            results_updated += 1
        
        # Commit all updates
        db.session.commit()
        
        if results_updated > 0:
            flash(f'🤖 ML Tracking: Updated {results_updated} prediction(s) with actual result', 'info')
        
        return results_updated
    
    except Exception as e:
        db.session.rollback()
        print(f"Enhanced ML tracking error: {e}")
        return 0

def get_team_bowl_status(team_name):
    """Get detailed bowl eligibility status for a team"""
    if team_name not in team_stats:
        return None
    
    stats = team_stats[team_name]
    total_wins = stats['wins']
    total_losses = stats['losses']
    
    # Count real wins (non-FCS)
    real_wins = 0
    fcs_wins = 0
    for game in stats['games']:
        if game['result'] == 'W':
            if is_fcs_opponent(game['opponent']):
                fcs_wins += 1
            else:
                real_wins += 1
    
    bowl_eligible = real_wins >= 6
    
    return {
        'total_wins': total_wins,
        'real_wins': real_wins,
        'fcs_wins': fcs_wins,
        'losses': total_losses,
        'bowl_eligible': bowl_eligible,
        'wins_needed': max(0, 6 - real_wins) if not bowl_eligible else 0
    }

def calculate_total_victory_value(team_name):
    """Sum up all victory values for a team - DATABASE VERSION"""
    # Get team stats from database
    team_stats_record = TeamStats.query.filter_by(team_name=team_name).first()
    
    if not team_stats_record:
        return 0, []
    
    team_stats = team_stats_record.to_dict()
    total_value = 0
    victory_details = []
    
    for game in team_stats['games']:
        if game['result'] == 'W':
            value = calculate_victory_value_with_rivalry(game, team_name)  # Use existing function
            total_value += value
            
            # Check if this was a rivalry win for display
            is_rival = is_rivalry_game(team_name, game['opponent'])
            rivalry_bonus = get_rivalry_bonus(team_name, game['opponent']) if is_rival else 0
            
            victory_details.append({
                'opponent': game['opponent'],
                'value': value,
                'margin': game['team_score'] - game['opp_score'],
                'location': game['home_away'],
                'is_rivalry': is_rival,
                'rivalry_bonus': rivalry_bonus
            })
    
    return total_value, victory_details

# ===============================================
# MODULE 3: ENHANCED LOSS QUALITY ASSESSMENT
# ===============================================

def calculate_enhanced_loss_penalty(game, team_name):
    """Enhanced loss penalty with all new factors"""
    if game['result'] != 'L':
        return 0.0
    
    opponent = game['opponent']
    team_score = game['team_score']
    opp_score = game['opp_score']
    margin = opp_score - team_score
    location = game['home_away']
    is_overtime = game.get('overtime', False)
    week = game.get('week', '1')
    
    # CATASTROPHIC FCS LOSS PENALTY (Adjusted)
    is_fcs_loss = (opponent == 'FCS' or opponent.upper() == 'FCS')
    if is_fcs_loss:
        base_penalty = 8.0  # Reduced from 10.0
        
        # More margin sensitivity
        if margin <= 3:
            margin_penalty = 1.0  # Close loss - still bad but not devastating
        elif margin <= 7:
            margin_penalty = 2.0
        elif margin <= 14:
            margin_penalty = 3.5
        else:
            margin_penalty = 5.0  # Blowout loss to FCS still severe
        
        # Location penalty (same logic)
        home_field_mult = get_enhanced_home_field_multiplier(team_name, location)
        if location == 'Home':
            location_penalty = 2.5 * home_field_mult  # Reduced from 3.0
        elif location == 'Away':
            location_penalty = 1.0  # Reduced from 1.5
        else:
            location_penalty = 1.5  # Reduced from 2.0
        
        overtime_reduction = 1.5 if is_overtime else 0.0  # Increased reduction
        temporal_weight = get_temporal_weight_by_week(week)
        
        total_penalty = (base_penalty + margin_penalty + location_penalty - overtime_reduction) * temporal_weight
        return max(8.0, total_penalty)  # Reduced minimum from 12.0 to 8.0
    
    # REGULAR LOSS PENALTIES (Enhanced)
    base_penalty = 3.0
    
    # Enhanced opponent quality adjustment
    opponent_quality = get_enhanced_opponent_quality(opponent)
    
    if opponent_quality >= 8.0:  # Elite opponent
        quality_adjustment = -2.0
    elif opponent_quality >= 7.0:  # Very good opponent
        quality_adjustment = -1.5
    elif opponent_quality >= 5.5:  # Good opponent
        quality_adjustment = -0.5
    elif opponent_quality >= 4.0:  # Average opponent
        quality_adjustment = 0.5
    elif opponent_quality >= 2.5:  # Bad opponent
        quality_adjustment = 1.5
    else:  # Terrible opponent
        quality_adjustment = 3.0
    
    # Enhanced margin penalty
    if margin <= 3:
        margin_penalty = 0
    elif margin <= 7:
        margin_penalty = 0.5
    elif margin <= 14:
        margin_penalty = 1.2
    elif margin <= 21:
        margin_penalty = 2.5
    elif margin <= 28:
        margin_penalty = 4.0
    else:
        margin_penalty = 5.5  # Massive blowout losses
    
    # Enhanced location adjustment with team-specific factors
    home_field_mult = get_enhanced_home_field_multiplier(team_name, location)
    if location == 'Home':
        location_adj = 1.0 * home_field_mult  # Worse if you have strong home field
    elif location == 'Away':
        location_adj = -0.5
    else:
        location_adj = 0.0
    
    # Travel adjustment
    travel_penalty = calculate_travel_adjustment(team_name, opponent, location, is_loss=True)
    
    # Game context adjustment
    context_penalty = get_game_context_penalty(week, opponent)
    
    # Temporal weighting
    temporal_weight = get_temporal_weight_by_week(week)
    
    # Calculate total
    total_penalty = base_penalty + quality_adjustment + margin_penalty + location_adj + travel_penalty + context_penalty
    
    # Overtime reduction
    if is_overtime:
        total_penalty *= 0.65  # Slightly more reduction for enhanced system
    
    # Apply temporal weight
    final_penalty = total_penalty * temporal_weight
    
    return max(0.5, final_penalty)

def calculate_loss_penalty(game, team_name):
    """
    Calculate penalty for a single loss based on quality and context.
    Returns a penalty value (positive number = bad for ranking)
    """
    if game['result'] != 'L':
        return 0.0
    
    opponent = game['opponent']
    team_score = game['team_score']
    opp_score = game['opp_score']
    margin = opp_score - team_score  # How much they lost by
    location = game['home_away']
    is_overtime = game.get('overtime', False)
    
    # ⚡ NEW: Special catastrophic penalty for FCS losses
    is_fcs_loss = (opponent == 'FCS' or opponent.upper() == 'FCS')
    
    if is_fcs_loss:
        # FCS losses are catastrophic regardless of other factors
        base_penalty = 8.0  # Much higher base penalty
        
        # Margin makes it even worse
        if margin <= 3:
            margin_penalty = 1.0  # Even close FCS losses are bad
        elif margin <= 7:
            margin_penalty = 2.0
        elif margin <= 14:
            margin_penalty = 3.5
        else:
            margin_penalty = 5.0  # Blowout loss to FCS is devastating
        
        # Location makes it worse
        if location == 'Home':
            location_penalty = 2.0  # Losing to FCS at home is inexcusable
        elif location == 'Away':
            location_penalty = 1.0  # Still bad, but slightly less so
        else:
            location_penalty = 1.5  # Neutral site
        
        # Overtime doesn't help much with FCS losses
        overtime_reduction = 0.5 if is_overtime else 0.0
        
        total_penalty = base_penalty + margin_penalty + location_penalty - overtime_reduction
        
        # Minimum penalty for any FCS loss
        return max(9.0, total_penalty)
    
    # EXISTING: Normal loss penalty logic for non-FCS opponents
    # 1. Base Loss Penalty
    base_penalty = 3.0  # Every loss starts with 3-point penalty
    
    # 2. Opponent Quality Adjustment
    opponent_quality = get_current_opponent_quality(opponent)
    
    # Losing to good teams hurts less, losing to bad teams hurts more
    if opponent_quality >= 7.0:  # Top tier opponent
        quality_adjustment = -1.5  # Reduce penalty
    elif opponent_quality >= 5.5:  # Decent opponent  
        quality_adjustment = -0.5  # Slight penalty reduction
    elif opponent_quality >= 4.0:  # Below average opponent
        quality_adjustment = 0.5   # Slight penalty increase
    else:  # Bad opponent
        quality_adjustment = 2.0   # Major penalty increase
    
    # 3. Margin Penalty - Blowout losses hurt more
    if margin <= 3:
        margin_penalty = 0  # Close losses don't add extra penalty
    elif margin <= 7:
        margin_penalty = 0.5
    elif margin <= 14:
        margin_penalty = 1.0
    elif margin <= 21:
        margin_penalty = 2.0
    else:
        margin_penalty = 3.0  # Blowout losses hurt a lot
    
    # 4. Location Adjustment
    location_adjustments = {
        'Home': 0.5,     # Losing at home hurts more
        'Away': -0.3,    # Losing on road hurts less
        'Neutral': 0.0   # Neutral baseline
    }
    location_adj = location_adjustments.get(location, 0.0)
    
    # 5. Calculate Total Penalty
    total_penalty = base_penalty + quality_adjustment + margin_penalty + location_adj
    
    # 6. Overtime Loss Reduction
    if is_overtime:
        total_penalty *= 0.7  # 30% reduction for overtime losses
    
    # Ensure penalty is never negative (losses should always hurt something)
    return max(0.5, total_penalty)

def calculate_total_loss_penalty(team_name):
    """Sum up all loss penalties for a team - DATABASE VERSION"""
    # Get team stats from database
    team_stats_record = TeamStats.query.filter_by(team_name=team_name).first()
    
    if not team_stats_record:
        return 0, []
    
    team_stats = team_stats_record.to_dict()
    total_penalty = 0
    loss_details = []    
    
    for game in team_stats['games']:
        if game['result'] == 'L':
            penalty = calculate_loss_penalty(game, team_name)  # Use existing function
            total_penalty += penalty
            loss_details.append({
                'opponent': game['opponent'],
                'penalty': penalty,
                'margin': game['opp_score'] - game['team_score'],
                'location': game['home_away']
            })
    
    return total_penalty, loss_details

# ===============================================
# MODULE 4: ENHANCED TEMPORAL WEIGHTING ENGINE
# ===============================================

def get_temporal_weight_by_week(week):
    """Weight games by when they occurred in season - early games matter less"""
    week_weights = {
        # Early season - teams still developing
        '1': 0.65,   # Week 1 rust, limited prep time
        '2': 0.75,   # Still finding identity
        '3': 0.8,    # Starting to gel
        '4': 0.85,   # Getting more reliable
        '5': 0.9,    # Mostly developed
        
        # Mid season - full weight
        '6': 0.95,   # Nearly full strength
        '7': 1.0,    # Peak evaluation period
        '8': 1.0,    # Peak evaluation period
        '9': 1.0,    # Peak evaluation period
        '10': 1.0,   # Peak evaluation period
        
        # Late season - heightened importance
        '11': 1.05,  # Conference races heating up
        '12': 1.1,   # Rivalry week, conference titles
        '13': 1.15,  # Conference championships
        
        # Postseason - high stakes
        'Bowls': 1.08,     # Bowl games matter, but not as much as regular season
        'CFP': 1.25,       # Playoff games are crucial
        'Championship': 1.3 # National Championship
    }
    
    return week_weights.get(str(week), 1.0)

def calculate_enhanced_temporal_adjustment(team_name):
    """Enhanced temporal adjustment with early season consideration"""
    team_stats_record = TeamStats.query.filter_by(team_name=team_name).first()
    if not team_stats_record:
        return 0
    
    games = team_stats_record.to_dict()['games']
    if len(games) < 4:
        return 0
    
    # Separate games by period with enhanced weighting
    early_games = []    # First 4 games
    mid_games = []      # Games 5-8
    recent_games = []   # Last 4 games
    
    total_games = len(games)
    
    if total_games <= 8:
        # For teams with fewer games, just compare first half vs second half
        split_point = total_games // 2
        early_games = games[:split_point]
        recent_games = games[split_point:]
    else:
        # For teams with many games, use three periods
        early_games = games[:4]
        if total_games >= 12:
            mid_games = games[4:-4]
            recent_games = games[-4:]
        else:
            recent_games = games[4:]
    
    def calculate_weighted_performance(game_list):
        if not game_list:
            return 0.5, 0
        
        total_weight = 0
        weighted_wins = 0
        total_margin = 0
        
        for game in game_list:
            week = game.get('week', '7')  # Default to mid-season
            weight = get_temporal_weight_by_week(week)
            
            total_weight += weight
            if game['result'] == 'W':
                weighted_wins += weight
            
            margin = game['team_score'] - game['opp_score']
            total_margin += margin * weight
        
        weighted_win_rate = weighted_wins / total_weight if total_weight > 0 else 0
        weighted_avg_margin = total_margin / total_weight if total_weight > 0 else 0
        
        return weighted_win_rate, weighted_avg_margin
    
    # Calculate performance for each period
    early_wr, early_margin = calculate_weighted_performance(early_games)
    recent_wr, recent_margin = calculate_weighted_performance(recent_games)
    
    # If we have mid-season games, factor them in
    if mid_games:
        mid_wr, mid_margin = calculate_weighted_performance(mid_games)
        # Compare recent vs average of early+mid
        baseline_wr = (early_wr + mid_wr) / 2
        baseline_margin = (early_margin + mid_margin) / 2
    else:
        baseline_wr = early_wr
        baseline_margin = early_margin
    
    # Calculate improvement metrics
    win_rate_improvement = recent_wr - baseline_wr
    margin_improvement = (recent_margin - baseline_margin) / 14.0  # Normalize
    
    # Enhanced adjustment calculation
    temporal_adjustment = (win_rate_improvement * 2.5) + margin_improvement
    
    # Bonus for sustained improvement across all three periods
    if mid_games and recent_wr > mid_wr > early_wr:
        temporal_adjustment += 0.5  # Sustained improvement bonus
    
    return max(-3.0, min(3.0, temporal_adjustment))

def calculate_temporal_adjustment(team_name):
    """
    Adjust for recent form vs season-long performance - DATABASE VERSION
    Returns adjustment factor for current strength (-2 to +2 range).
    """
    # Get team stats from database
    team_stats_record = TeamStats.query.filter_by(team_name=team_name).first()
    
    if not team_stats_record:
        return 0
    
    games = team_stats_record.to_dict()['games']
    if len(games) < 4:
        return 0  # Not enough games for temporal analysis
    
    # Split season into early (all but last 4) and recent (last 4)
    early_games = games[:-4] if len(games) > 4 else []
    recent_games = games[-4:]
    
    if not early_games:
        return 0  # All games are "recent"
    
    # Calculate performance metrics for each period
    def calculate_period_performance(game_list):
        if not game_list:
            return 0.5, 0  # Neutral win rate, no margin
        
        wins = sum(1 for g in game_list if g['result'] == 'W')
        win_rate = wins / len(game_list)
        
        total_margin = sum(g['team_score'] - g['opp_score'] for g in game_list)
        avg_margin = total_margin / len(game_list)
        
        return win_rate, avg_margin
    
    early_win_rate, early_margin = calculate_period_performance(early_games)
    recent_win_rate, recent_margin = calculate_period_performance(recent_games)
    
    # Calculate improvement/decline
    win_rate_change = recent_win_rate - early_win_rate
    margin_change = recent_margin - early_margin
    
    # Convert to temporal adjustment (-2 to +2 range)
    adjustment = (win_rate_change * 2.0) + (margin_change / 14.0)
    
    return max(-2.0, min(2.0, adjustment))

# ===============================================
# MODULE 5: CONSISTENCY ANALYZER
# ===============================================

def calculate_consistency_factor(team_name):
    """
    Measure team consistency/reliability - DATABASE VERSION
    Returns adjustment based on performance variance (-0.6 to +0.5 range).
    """
    # Get team stats from database
    team_stats_record = TeamStats.query.filter_by(team_name=team_name).first()
    
    if not team_stats_record:
        return 0
    
    games = team_stats_record.to_dict()['games']
    if len(games) < 4:
        return 0  # Need multiple games for consistency analysis
    
    # Calculate game-by-game performance scores
    performance_scores = []
    for game in games:
        opponent_quality = get_current_opponent_quality(game['opponent'])
        margin = game['team_score'] - game['opp_score']
        
        # Expected margin based on opponent quality (rough approximation)
        expected_margin = (5.0 - opponent_quality) * 2  # Stronger opponents = negative expected margin
        
        # Performance score = how much better/worse than expected
        performance_score = margin - expected_margin
        performance_scores.append(performance_score)
    
    # Calculate variance
    if len(performance_scores) < 2:
        return 0
    
    mean_performance = sum(performance_scores) / len(performance_scores)
    variance = sum((score - mean_performance) ** 2 for score in performance_scores) / len(performance_scores)
    std_dev = math.sqrt(variance)
    
    # Convert to consistency factor
    # Lower variance = more consistent = small bonus
    # Higher variance = less reliable = small penalty
    if std_dev <= 10:
        consistency_bonus = 0.5  # Very consistent
    elif std_dev <= 15:
        consistency_bonus = 0.2  # Somewhat consistent
    elif std_dev <= 20:
        consistency_bonus = 0.0  # Average consistency
    elif std_dev <= 25:
        consistency_bonus = -0.3  # Inconsistent
    else:
        consistency_bonus = -0.6  # Very inconsistent
    
    return consistency_bonus

# ===============================================
# MODULE 6: ENHANCED FINAL RANKING COMPOSER
# ===============================================

def calculate_enhanced_scientific_ranking(team_name):
    """
    Enhanced scientific ranking with all new modules
    """
    team_stats_record = TeamStats.query.filter_by(team_name=team_name).first()
    if not team_stats_record:
        return create_default_ranking_result()
    
    stats = team_stats_record.to_dict()
    total_games = stats['wins'] + stats['losses']
    
    if total_games == 0:
        return create_default_ranking_result()

    # COMPONENT 1: Enhanced Victory Value
    victory_value = 0
    victory_details = []
    for game in stats['games']:
        if game['result'] == 'W':
            value = calculate_enhanced_victory_value(game, team_name)
            victory_value += value
            victory_details.append({
                'opponent': game['opponent'],
                'value': value,
                'week': game.get('week', '1')
            })
    
    # COMPONENT 2: Enhanced Loss Penalties
    loss_penalty = 0
    loss_details = []
    for game in stats['games']:
        if game['result'] == 'L':
            penalty = calculate_enhanced_loss_penalty(game, team_name)
            loss_penalty += penalty
            loss_details.append({
                'opponent': game['opponent'],
                'penalty': penalty,
                'week': game.get('week', '1')
            })
    
    # COMPONENT 3: Enhanced Temporal Adjustment
    temporal_adj = calculate_enhanced_temporal_adjustment(team_name)
    
    # COMPONENT 4: Consistency Factor (existing)
    consistency_factor = calculate_consistency_factor(team_name)
    
    # COMPONENT 5: Schedule Quality Penalty (NEW)
    schedule_penalty = calculate_schedule_quality_penalty(team_name)

    # COMPONENT 5B: Schedule Manipulation Penalties
    manipulation_flags = detect_schedule_manipulation(team_name)
    manipulation_penalty = 0
    for flag in manipulation_flags:
        manipulation_penalty += SCHEDULE_MANIPULATION_PENALTIES.get(flag, 0)
    
    # COMPONENT 6: Games Bonus
    games_bonus = min(2.5, total_games * 0.18)  # Slightly enhanced
    
    # COMPONENT 7: Strength of Schedule Rating (NEW)
    sos_rating = calculate_strength_of_schedule_rating(team_name)
    sos_bonus = (sos_rating - 5.0) * 0.3  # Bonus/penalty for strong/weak schedules
    
    # Conference Multiplier (existing)
    team_conf = get_team_conference(team_name)
    if team_conf in G5_CONFERENCES or team_name in G5_INDEPENDENT_TEAMS:
        conference_multiplier = 0.85
    else:
        conference_multiplier = 1.0
    
    adjusted_victory_value = victory_value * conference_multiplier
    
    # FINAL CALCULATION
    total_score = (
        adjusted_victory_value -    # Core victory value
        loss_penalty -             # Loss penalties
        schedule_penalty -         # Schedule quality penalty
        manipulation_penalty +     # Schedule manipulation penalty
        temporal_adj +             # Recent form
        consistency_factor +       # Reliability
        sos_bonus +               # Strength of schedule
        games_bonus               # Games played bonus
    )
    
    return {
        'total_score': round(total_score, 3),
        'components': {
            'victory_value': round(victory_value, 2),
            'conference_multiplier': conference_multiplier,
            'adjusted_victory_value': round(adjusted_victory_value, 2),
            'loss_penalty': round(loss_penalty, 2),
            'schedule_penalty': round(schedule_penalty, 2),
            'temporal_adjustment': round(temporal_adj, 2),
            'consistency_factor': round(consistency_factor, 2),
            'sos_bonus': round(sos_bonus, 2),
            'games_bonus': round(games_bonus, 2),
            'sos_rating': sos_rating
        },
        'basic_stats': {
            'wins': stats['wins'],
            'losses': stats['losses'],
            'total_games': total_games
        },
        'schedule_analysis': {
            'strength_rating': sos_rating,
            'manipulation_flags': detect_schedule_manipulation(team_name)
        }
    }


def create_default_ranking_result():
    """Create default ranking result for teams with no games"""
    return {
        'total_score': 0.0,
        'components': {
            'victory_value': 0.0,
            'conference_multiplier': 1.0,
            'adjusted_victory_value': 0.0,
            'loss_penalty': 0.0,
            'schedule_penalty': 0.0,
            'temporal_adjustment': 0.0,
            'consistency_factor': 0.0,
            'sos_bonus': 0.0,
            'games_bonus': 0.0,
            'sos_rating': 5.0
        },
        'basic_stats': {
            'wins': 0,
            'losses': 0,
            'total_games': 0
        },
        'schedule_analysis': {
            'strength_rating': 5.0,
            'manipulation_flags': []
        }
    }


# Add these new functions near your other calculation functions
# (around where calculate_comprehensive_stats, calculate_victory_value, etc. are)

def get_all_team_stats_bulk():
    """Load all team stats with PROPER ranking calculations but efficient bulk approach"""
    try:
        start_time = time.time()
        
        # Get all teams with games
        teams_with_games = TeamStats.query.filter(
            (TeamStats.wins + TeamStats.losses) > 0
        ).all()
        
        print(f"⏱️ Database query took {time.time() - start_time:.2f} seconds")
        
        # BULK BUILD: Create team lookup for efficient opponent quality calculations
        cache_start = time.time()
        team_lookup = {}
        
        for team_record in teams_with_games:
            team_data = team_record.to_dict()
            team_lookup[team_record.team_name] = team_data
        
        print(f"⏱️ Team lookup built in {time.time() - cache_start:.2f} seconds")
        
        # Now calculate proper ratings for each team
        loop_start = time.time()
        comprehensive_stats = []
        
        for team_record in teams_with_games:
            team_name = team_record.team_name
            team_data = team_record.to_dict()
            
            # CALCULATE PROPER VICTORY VALUE using bulk data
            total_victory_value = 0
            total_loss_penalty = 0
            
            for game in team_data['games']:
                opponent = game['opponent']
                team_score = game['team_score']
                opp_score = game['opp_score']
                location = game['home_away']
                
                if game['result'] == 'W':
                    # Calculate victory value properly
                    
                    # 1. Opponent Quality (using bulk data instead of expensive query)
                    if opponent == 'FCS':
                        opponent_quality = 0.5
                    elif opponent in team_lookup:
                        opp_data = team_lookup[opponent]
                        opp_games = opp_data['wins'] + opp_data['losses']
                        if opp_games > 0:
                            opp_win_pct = opp_data['wins'] / opp_games
                            opponent_quality = 2.0 + (opp_win_pct * 6.0)  # 2-8 scale

                            # Base quality using subdivision-aware calculation
                            opp_conf = get_team_conference(opponent)
                            if opp_conf in P4_CONFERENCES:
                                opponent_quality = 4.0 + (opp_win_pct * 4.0)  # P4: 4.0-8.0 range
                            elif opp_conf in G5_CONFERENCES:
                                opponent_quality = 2.5 + (opp_win_pct * 4.0)  # G5: 2.5-6.5 range
                            else:
                                opponent_quality = 2.0 + (opp_win_pct * 6.0)  # Default/Other: 2.0-8.0 range

                        else:
                            opponent_quality = 5.0
                    else:
                        opponent_quality = 5.0  # Unknown opponent
                    
                    # 2. Location Multiplier
                    location_mult = {'Home': 1.0, 'Away': 1.3, 'Neutral': 1.15}.get(game['home_away'], 1.0)

                    travel_bonus = calculate_travel_adjustment(team_name, opponent, game['home_away'])
                    
                    # 3. Margin Bonus
                    margin = team_score - opp_score
                    if margin <= 7:
                        margin_bonus = margin * 0.1
                    elif margin <= 14:
                        margin_bonus = 0.7 + (margin - 7) * 0.08
                    elif margin <= 21:
                        margin_bonus = 1.26 + (margin - 14) * 0.04
                    else:
                        margin_bonus = 1.54 + (margin - 21) * 0.02
                    
                    # 4. Calculate victory value
                    victory_value = (opponent_quality * location_mult) + margin_bonus + travel_bonus
                    
                    # 5. FCS cap
                    if opponent == 'FCS':
                        victory_value = min(victory_value, 1.0)
                    
                    total_victory_value += victory_value
                
                elif game['result'] == 'L':
                    # Calculate loss penalty
                    margin = opp_score - team_score
                    
                    if opponent == 'FCS':
                        # Catastrophic FCS loss
                        loss_penalty = 10.0 + (margin * 0.5)
                    else:
                        # Normal loss penalty
                        if opponent in team_lookup:
                            opp_data = team_lookup[opponent]
                            opp_games = opp_data['wins'] + opp_data['losses']
                            if opp_games > 0:
                                opp_win_pct = opp_data['wins'] / opp_games
                                opponent_quality = 2.0 + (opp_win_pct * 6.0)
                            else:
                                opponent_quality = 5.0
                        else:
                            opponent_quality = 5.0
                        
                        # Base loss penalty
                        base_penalty = 3.0
                        
                        # Opponent quality adjustment
                        if opponent_quality >= 7.0:
                            quality_adj = -1.5  # Good opponent
                        elif opponent_quality >= 5.5:
                            quality_adj = -0.5
                        elif opponent_quality >= 4.0:
                            quality_adj = 0.5
                        else:
                            quality_adj = 2.0  # Bad opponent
                        
                        # Margin penalty
                        if margin <= 3:
                            margin_penalty = 0
                        elif margin <= 7:
                            margin_penalty = 0.5
                        elif margin <= 14:
                            margin_penalty = 1.0
                        else:
                            margin_penalty = 2.0
                        
                        loss_penalty = base_penalty + quality_adj + margin_penalty
                    
                    total_loss_penalty += loss_penalty
            
            # CALCULATE STRENGTH OF SCHEDULE using bulk data
            opponent_total_wins = 0
            opponent_total_losses = 0
            opponent_total_games = 0
            
            for game in team_data['games']:
                opponent = game['opponent']
                if opponent in team_lookup and opponent != 'FCS':
                    opp_data = team_lookup[opponent]
                    opponent_total_wins += opp_data['wins']
                    opponent_total_losses += opp_data['losses']
                    opponent_total_games += (opp_data['wins'] + opp_data['losses'])
            
            strength_of_schedule = opponent_total_wins / opponent_total_games if opponent_total_games > 0 else 0.500
            
            # Apply conference multiplier
            team_conf = get_team_conference(team_name)
            if team_conf in ['American', 'Conference USA', 'MAC', 'Mountain West', 'Sun Belt'] or team_name == 'Connecticut':
                conference_multiplier = 0.85
            else:
                conference_multiplier = 1.0
            
            adjusted_victory_value = total_victory_value * conference_multiplier
            
            # Final calculation
            games_bonus = min(2.5, len(team_data['games']) * 0.18)
            adjusted_total = adjusted_victory_value - total_loss_penalty + games_bonus
            
            # Build the stats object
            stats = {
                'team': team_name,
                'conference': get_team_conference(team_name),
                'adjusted_total': round(adjusted_total, 3),
                'total_wins': team_data['wins'],
                'total_losses': team_data['losses'],
                'points_fielded': team_data['points_for'],
                'points_allowed': team_data['points_against'],
                'margin_of_victory': team_data['margin_of_victory_total'],
                'point_differential': team_data['points_for'] - team_data['points_against'],
                'home_wins': team_data['home_wins'],
                'road_wins': team_data['road_wins'],
                'strength_of_schedule': round(strength_of_schedule, 3),  # NOW CALCULATED PROPERLY
                'totals': round(adjusted_total, 3),
                'scientific_breakdown': {'total_score': adjusted_total},
                'opp_w': opponent_total_wins, 
                'opp_l': opponent_total_losses, 
                'opp_wl_differential': opponent_total_wins - opponent_total_losses, 
                'strength_of_record': round(strength_of_schedule * (team_data['wins'] / max(1, team_data['wins'] + team_data['losses'])), 3)
            }
            
            comprehensive_stats.append(stats)
        
        print(f"⏱️ All teams calculations took {time.time() - loop_start:.2f} seconds")
        
        # Sort by ranking
        comprehensive_stats.sort(key=lambda x: x['adjusted_total'], reverse=True)
        print(f"⏱️ TOTAL get_all_team_stats_bulk took {time.time() - start_time:.2f} seconds")
        
        return comprehensive_stats
        
    except Exception as e:
        print(f"Error in bulk loading: {e}")
        return []


def calculate_fast_stats(team_name, team_data, opponent_quality_cache):
    """Fast stats calculation using pre-computed opponent qualities"""
    total_games = team_data['wins'] + team_data['losses']
    if total_games == 0:
        return create_default_stats()
    
    # Calculate victory value efficiently
    victory_value = 0
    for game in team_data['games']:
        if game['result'] == 'W':
            opponent = game['opponent']
            
            # ✅ FIX: Check for FCS games first!
            is_fcs_game = (opponent == 'FCS' or opponent.upper() == 'FCS')
            
            if is_fcs_game:
                # ✅ FCS games get minimal credit
                margin = game['team_score'] - game['opp_score']
                margin_bonus = min(0.2, margin * 0.02)  # Max 0.2
                victory_value += min(1.0, 0.5 + margin_bonus)  # Capped at 1.0
            else:
                # Normal calculation for real opponents
                opponent_quality = opponent_quality_cache.get(opponent, 5.0)
                margin = game['team_score'] - game['opp_score']
                location_mult = {'Home': 1.0, 'Away': 1.3, 'Neutral': 1.15}.get(game['home_away'], 1.0)
                
                # FIXED: Use opponent-quality-based margin caps
                margin_bonus = calculate_margin_bonus_capped(margin, opponent_quality)
                
                victory_value += (opponent_quality * location_mult) + margin_bonus
    

    # CONFERENCE MULTIPLIER HERE ←
    team_conf = get_team_conference(team_name)
    if team_conf in G5_CONFERENCES or team_name in G5_INDEPENDENT_TEAMS:
        conference_multiplier = 0.85
    else:
        conference_multiplier = 1.0
    
    adjusted_victory_value = victory_value * conference_multiplier
    

    # Simple loss penalty
    loss_penalty = team_data['losses'] * 3.0
    
    # Final calculation
    adjusted_total = victory_value - loss_penalty + (total_games * 0.18)
    

    return {
        'adjusted_total': round(adjusted_total, 3),
        'total_wins': team_data['wins'],
        'total_losses': team_data['losses'],
        'points_fielded': team_data['points_for'],
        'points_allowed': team_data['points_against'],
        'margin_of_victory': team_data['margin_of_victory_total'],
        'point_differential': team_data['points_for'] - team_data['points_against'],
        'home_wins': team_data['home_wins'],
        'road_wins': team_data['road_wins'],
        'strength_of_schedule': 0.500,  # Simplified for speed
        'totals': round(adjusted_total, 3),
        'scientific_breakdown': {'total_score': adjusted_total},
        'opp_w': 0,  # Simplified for speed
        'opp_l': 0,  # Simplified for speed
        'opp_wl_differential': 0,  # Simplified for speed
        'strength_of_record': 0.500  # Simplified for speed
    }



def create_default_stats():
    """Default stats for teams with no games"""
    return {
        'adjusted_total': 0.0,
        'total_wins': 0,
        'total_losses': 0,
        'points_fielded': 0,
        'points_allowed': 0,
        'margin_of_victory': 0,
        'point_differential': 0,
        'home_wins': 0,
        'road_wins': 0,
        'strength_of_schedule': 0.0,
        'totals': 0.0,
        'scientific_breakdown': {'total_score': 0.0},
        'opp_w': 0,
        'opp_l': 0,
        'opp_wl_differential': 0,
        'strength_of_record': 0.0
    }


def calculate_comprehensive_stats(team_name):
    """
    Calculate comprehensive stats - UPDATED to use database
    """
    # Get team stats from database instead of global variable
    team_stats_record = TeamStats.query.filter_by(team_name=team_name).first()
    
    if not team_stats_record:
        # Return default stats for teams with no games
        return {
            'adjusted_total': 0.0,
            'points_fielded': 0,
            'points_allowed': 0,
            'margin_of_victory': 0,
            'point_differential': 0,
            'home_wins': 0,
            'road_wins': 0,
            'total_wins': 0,
            'total_losses': 0,
            'strength_of_schedule': 0.0,
            'totals': 0.0,
            'scientific_breakdown': {'total_score': 0.0, 'components': {}}
        }
    
    # Convert database record to the format your existing code expects
    team_stats = team_stats_record.to_dict()
    
    # Continue with your existing calculation logic...
    scientific_result = calculate_enhanced_scientific_ranking(team_name)
    
    # Calculate some legacy fields that other parts of code might expect
    total_games = team_stats['wins'] + team_stats['losses']
    
    # Calculate opponent stats for strength of schedule
    opponent_total_wins = 0
    opponent_total_losses = 0
    opponent_total_games = 0
    
    for game in team_stats['games']:
        opponent = game['opponent']
        opp_stats_record = TeamStats.query.filter_by(team_name=opponent).first()
        if opp_stats_record:
            opp_stats = opp_stats_record.to_dict()
            opponent_total_wins += opp_stats['wins']
            opponent_total_losses += opp_stats['losses']
            opponent_total_games += (opp_stats['wins'] + opp_stats['losses'])
    
    strength_of_schedule = opponent_total_wins / opponent_total_games if opponent_total_games > 0 else 0
    point_differential = team_stats['points_for'] - team_stats['points_against']
    opp_wl_differential = opponent_total_wins - opponent_total_losses
    
    return {
        # NEW: Scientific score as main ranking
        'adjusted_total': scientific_result['total_score'],
        
        # LEGACY: Keep all old fields for template compatibility
        'points_fielded': team_stats['points_for'],
        'points_allowed': team_stats['points_against'],
        'margin_of_victory': team_stats['margin_of_victory_total'],
        'point_differential': point_differential,
        'home_wins': team_stats['home_wins'],
        'road_wins': team_stats['road_wins'],
        'opp_w': opponent_total_wins,
        'opp_l': opponent_total_losses,
        'strength_of_schedule': round(strength_of_schedule, 3),
        'opp_wl_differential': opp_wl_differential,
        'totals': scientific_result['components']['victory_value'],
        'total_wins': team_stats['wins'],
        'total_losses': team_stats['losses'],
        'strength_of_record': round(strength_of_schedule * (team_stats['wins'] / max(1, team_stats['wins'] + team_stats['losses'])), 3),
        
        # NEW: Scientific breakdown available for future use
        'scientific_breakdown': scientific_result
    }

# ===============================================
# MODULE 7: GAME CONTEXT ANALYZER
# ===============================================

def get_game_context_bonus(week, opponent):
    """Bonus points for high-stakes games"""
    bonus = 0.0
    
    # Conference Championship Games
    if week == '13' or week == 'Championship':
        bonus += 1.2  # Significant bonus for conference titles
    
    # Rivalry Week (Week 12 typically)
    elif week == '12':
        bonus += 0.3  # Rivalry week intensity
    
    # Late season conference games
    elif week in ['11', '12'] and is_conference_opponent(opponent):
        bonus += 0.2  # Late season conference games matter more
    
    # Bowl games
    elif week == 'Bowls':
        bonus += 0.5  # Bowl games are meaningful
    
    # CFP games
    elif week == 'CFP':
        bonus += 1.5  # Playoff games are crucial
    
    return bonus

def get_game_context_penalty(week, opponent):
    """Additional penalty for bad losses in crucial games"""
    penalty = 0.0
    
    # Conference Championship losses hurt more
    if week == '13' or week == 'Championship':
        penalty += 1.0
    
    # Late season conference losses
    elif week in ['11', '12'] and is_conference_opponent(opponent):
        penalty += 0.3
    
    return penalty

def calculate_travel_adjustment(team_name, opponent_name, location, is_loss=False):
    """Calculate adjustment for cross-country travel"""
    
    # Time zone mappings
    PACIFIC_TEAMS = ['Stanford', 'California', 'UCLA', 'USC', 'Oregon', 'Oregon State', 
                     'Washington', 'Washington State', 'San Diego State', 'San Jose State',
                     'Fresno State', 'Hawaii', 'Nevada', 'UNLV']
    
    MOUNTAIN_TEAMS = ['Colorado', 'Utah', 'Arizona', 'Arizona State', 'Boise State',
                      'Colorado State', 'New Mexico', 'Utah State', 'Wyoming', 'Air Force']
    
    CENTRAL_TEAMS = ['Texas', 'Oklahoma', 'Texas A&M', 'LSU', 'Arkansas', 'Missouri',
                     'Texas Tech', 'Oklahoma State', 'TCU', 'Baylor', 'Houston',
                     'Kansas', 'Kansas State', 'Iowa State', 'Nebraska', 'Iowa',
                     'Minnesota', 'Wisconsin', 'Illinois', 'Northwestern']
    
    EASTERN_TEAMS = ['Florida', 'Georgia', 'Alabama', 'Auburn', 'Tennessee', 'Kentucky',
                     'South Carolina', 'Vanderbilt', 'Mississippi State', 'Ole Miss',
                     'Clemson', 'Florida State', 'Miami', 'North Carolina', 'NC State',
                     'Duke', 'Wake Forest', 'Virginia', 'Virginia Tech', 'Pittsburgh',
                     'Syracuse', 'Boston College', 'Louisville', 'Georgia Tech',
                     'Ohio State', 'Michigan', 'Penn State', 'Michigan State',
                     'Indiana', 'Purdue', 'Maryland', 'Rutgers']
    
    def get_time_zone(team):
        if team in PACIFIC_TEAMS: return 'Pacific'
        elif team in MOUNTAIN_TEAMS: return 'Mountain'
        elif team in CENTRAL_TEAMS: return 'Central'
        elif team in EASTERN_TEAMS: return 'Eastern'
        else: return 'Central'  # Default
    
    # Only apply to away games
    if location != 'Away':
        return 0.0
    
    team_zone = get_time_zone(team_name)
    opp_zone = get_time_zone(opponent_name)
    
    # Calculate time zone difference
    zone_order = {'Pacific': 0, 'Mountain': 1, 'Central': 2, 'Eastern': 3}
    zone_diff = abs(zone_order.get(team_zone, 2) - zone_order.get(opp_zone, 2))
    
    if zone_diff >= 3:  # Cross-country travel (3+ time zones)
        if is_loss:
            return -0.15  # Reduced from -0.3
        else:
            return 0.2   # Reduced from 0.4
    elif zone_diff == 2:  # Moderate travel (2 time zones)
        if is_loss:
            return -0.075  # Reduced from -0.15
        else:
            return 0.1     # Reduced from 0.2
    
    return 0.0

def check_bye_week_advantage(team_games, current_game_index):
    """Check if team had bye week advantage"""
    if current_game_index == 0:
        return 0.0
    
    # This would require tracking weeks between games
    # For now, return 0 - could be enhanced with actual schedule data
    return 0.0

def is_conference_opponent(opponent_name):
    """Check if opponent is in same conference"""
    # Implementation would check if teams are in same conference
    # Simplified for now
    return True  # Most late-season games are conference games


# ===============================================
# MODULE 8: SCHEDULE QUALITY ASSESSOR
# ===============================================

def calculate_schedule_quality_penalty(team_name):
    """Penalize teams for playing too many weak opponents"""
    team_record = TeamStats.query.filter_by(team_name=team_name).first()
    if not team_record:
        return 0.0
    
    games = team_record.to_dict()['games']
    
    if len(games) < 8:  # Not enough games to assess
        return 0.0
    
    # Count opponents by quality tier
    fcs_games = 0
    very_weak_games = 0  # Quality < 2.5
    weak_games = 0       # Quality 2.5-4.0
    decent_games = 0     # Quality 4.0-6.0
    strong_games = 0     # Quality 6.0+
    
    for game in games:
        opponent = game['opponent']
        
        if opponent == 'FCS' or opponent.upper() == 'FCS':
            fcs_games += 1
            continue
        
        opp_quality = get_enhanced_opponent_quality(opponent)
        
        if opp_quality < 2.5:
            very_weak_games += 1
        elif opp_quality < 4.0:
            weak_games += 1
        elif opp_quality < 6.0:
            decent_games += 1
        else:
            strong_games += 1
    
    penalty = 0.0
    
    # FCS game penalty (beyond the normal minimal credit)
    if fcs_games >= 2:
        penalty += 1.5  # Multiple FCS games
    elif fcs_games == 1:
        penalty += 0.3  # One FCS game is acceptable
    
    # Very weak opponent penalty
    if very_weak_games >= 4:
        penalty += 2.5  # Way too many cupcakes
    elif very_weak_games >= 3:
        penalty += 1.5  # Too many cupcakes
    elif very_weak_games >= 2:
        penalty += 0.8  # Some cupcakes
    
    # Weak opponent penalty (cumulative)
    combined_weak = very_weak_games + weak_games
    if combined_weak >= 6:
        penalty += 2.0  # Schedule is majority weak teams
    elif combined_weak >= 5:
        penalty += 1.2
    elif combined_weak >= 4:
        penalty += 0.6
    
    # Bonus for strong schedules
    if strong_games >= 6:
        penalty -= 1.0  # Reward very strong schedules
    elif strong_games >= 4:
        penalty -= 0.5  # Reward strong schedules
    
    # Conference context - P4 teams expected to play stronger schedules
    team_conf = get_team_conference(team_name)
    if team_conf in P4_CONFERENCES:
        penalty *= 1.2  # P4 teams held to higher standard
    else:
        penalty *= 0.8  # G5 teams get some slack
    
    return max(0.0, penalty)

def calculate_strength_of_schedule_rating(team_name):
    """Calculate a comprehensive strength of schedule rating"""
    team_record = TeamStats.query.filter_by(team_name=team_name).first()
    if not team_record:
        return 5.0  # Neutral rating
    
    games = team_record.to_dict()['games']
    
    if not games:
        return 5.0
    
    # Calculate weighted average opponent quality
    total_quality = 0
    total_weight = 0
    
    for game in games:
        opponent = game['opponent']
        week = game.get('week', '7')
        
        # Get opponent quality
        opp_quality = get_enhanced_opponent_quality(opponent)
        
        # Weight by temporal importance
        week_weight = get_temporal_weight_by_week(week)
        
        total_quality += opp_quality * week_weight
        total_weight += week_weight
    
    avg_opp_quality = total_quality / total_weight if total_weight > 0 else 5.0
    
    return round(avg_opp_quality, 2)

def detect_schedule_manipulation(team_name):
    """Detect potential schedule manipulation tactics"""
    team_record = TeamStats.query.filter_by(team_name=team_name).first()
    if not team_record:
        return []
    
    games = team_record.to_dict()['games']
    issues = []
    
    # Check for late-season cupcakes
    late_season_games = [g for g in games if g.get('week', '1') in ['10', '11', '12']]
    late_weak_count = 0
    
    for game in late_season_games:
        opp_quality = get_enhanced_opponent_quality(game['opponent'])
        if opp_quality < 3.0:
            late_weak_count += 1
    
    if late_weak_count >= 2:
        issues.append("Multiple weak opponents late in season")
    
    # Check for FCS scheduling timing
    fcs_games = [g for g in games if g['opponent'].upper() == 'FCS']
    if len(fcs_games) > 1:
        issues.append("Multiple FCS opponents scheduled")
    
    # Check for home game loading
    home_games = [g for g in games if g['home_away'] == 'Home']
    if len(home_games) > len(games) * 0.75:  # More than 75% home games
        issues.append("Excessive home game scheduling")
    
    return issues

def auto_predict_single_game(scheduled_game, overwrite=False):
    """
    Enhanced auto-prediction with over/under and structured factor tracking
    Returns: (success: bool, message: str, prediction_id: int or None)
    """
    try:

        # NEW: Skip FCS games entirely
        if (is_fcs_opponent(scheduled_game.home_team) or 
            is_fcs_opponent(scheduled_game.away_team)):
            return False, f"Skipped FCS game: {scheduled_game.away_team} @ {scheduled_game.home_team}", None


        # Check if prediction already exists
        existing = CFBPredictionLog.query.filter(
            CFBPredictionLog.week == scheduled_game.week,
            CFBPredictionLog.home_team == scheduled_game.home_team,
            CFBPredictionLog.away_team == scheduled_game.away_team,
            CFBPredictionLog.prediction_type == 'automated'
        ).first()
        
        if existing and not overwrite:
            return False, "Automated prediction already exists", existing.id
        
        # Determine location parameter for your prediction function
        if scheduled_game.neutral:
            location = 'neutral'
        else:
            location = 'home'  # Home team gets home field advantage
        
        # Generate prediction using your existing function
        prediction_result = predict_matchup_ultra_enhanced(
            scheduled_game.home_team,
            scheduled_game.away_team, 
            location
        )
        
        # Get team stats for total points prediction
        home_stats = TeamStats.query.filter_by(team_name=scheduled_game.home_team).first()
        away_stats = TeamStats.query.filter_by(team_name=scheduled_game.away_team).first()
        
        # Calculate predicted total (you can enhance this formula)
        predicted_total = None
        if home_stats and away_stats:
            home_games = max(1, home_stats.wins + home_stats.losses)
            away_games = max(1, away_stats.wins + away_stats.losses)
            home_avg = home_stats.points_for / home_games
            away_avg = away_stats.points_for / away_games
            predicted_total = round(home_avg + away_avg, 1)
        
        # Create or update prediction log entry
        if existing and overwrite:
            prediction_log = existing
        else:
            prediction_log = CFBPredictionLog()
        
        # Fill in the basic prediction data
        prediction_log.season_year = 2025  # Or get from config
        prediction_log.week = scheduled_game.week
        prediction_log.home_team = scheduled_game.home_team
        prediction_log.away_team = scheduled_game.away_team
        prediction_log.prediction_type = 'automated'
        
        # Store prediction results
        prediction_log.predicted_winner = prediction_result['winner']
        prediction_log.predicted_margin = abs(prediction_result['final_margin'])
        prediction_log.predicted_total = predicted_total
        prediction_log.win_probability = prediction_result['win_probability']
        prediction_log.confidence_level = prediction_result['confidence']
        
        # ENHANCED: Store structured factor data
        adjustments = prediction_result.get('adjustments', {})
        
        prediction_log.base_strength_diff = prediction_result.get('base_margin', 0)
        prediction_log.schedule_strength_factor = adjustments.get('Enhanced Schedule Strength', 0)
        prediction_log.momentum_factor = adjustments.get('Recent Momentum Edge', 0)
        prediction_log.location_factor = adjustments.get('Enhanced Home Field', 0)
        prediction_log.consistency_factor = adjustments.get('Consistency Advantage', 0)
        prediction_log.common_opponent_factor = adjustments.get('Enhanced Common Opponents', 0) or adjustments.get('Common Opponents', 0)
        
        # Store current algorithm settings
        prediction_log.temporal_weights_json = json.dumps(get_current_temporal_weights())
        prediction_log.algorithm_version = "v1.0"  # Update this when you change your algorithm
        
        # Store prediction factors as JSON (existing functionality)
        factors = {
            'base_margin': prediction_result['base_margin'],
            'adjustments': prediction_result['adjustments'],
            'confidence_score': prediction_result['confidence_score'],
            'methodology': prediction_result['prediction_methodology']
        }
        prediction_log.prediction_factors_json = json.dumps(factors)
        
        # Save to database
        if not existing:
            db.session.add(prediction_log)
        db.session.commit()
        
        return True, f"Successfully predicted {scheduled_game.away_team} @ {scheduled_game.home_team}", prediction_log.id
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error generating prediction: {str(e)}", None

# Add these two routes to your app.py

def get_current_temporal_weights():
    """
    Return current temporal weight settings for ML tracking
    CUSTOMIZE THIS to match your actual temporal weight system
    """
    # Replace these with your actual temporal weights from your algorithm
    # These are example values - update them to match your current system
    return {
        "week_1": 0.65,
        "week_2": 0.70,
        "week_3": 0.75,
        "week_4": 0.80,
        "week_5": 0.85,
        "week_6": 0.90,
        "week_7": 0.95,
        "week_8": 1.00,
        "week_9": 1.05,
        "week_10": 1.10,
        "week_11": 1.15,
        "week_12": 1.20,
        "bowls": 1.25,
        "championship": 1.30
    }


@app.route('/admin/ml/recreate_tables')
@login_required
def recreate_cfb_ml_tables():
    """Drop and recreate CFB ML tables with correct structure"""
    try:
        # Import the models to ensure they're loaded
        from models import CFBPredictionLog, CFBTemporalAnalysis, CFBAlgorithmPerformance
        
        # Use proper SQLAlchemy 2.0 syntax
        with db.engine.connect() as connection:
            # Drop existing tables
            connection.execute(text("DROP TABLE IF EXISTS cfb_prediction_logs CASCADE;"))
            connection.execute(text("DROP TABLE IF EXISTS cfb_temporal_analysis CASCADE;"))
            connection.execute(text("DROP TABLE IF EXISTS cfb_algorithm_performance CASCADE;"))
            connection.commit()
        
        # Recreate with current model structure
        db.create_all()
        
        flash('✅ CFB ML tables recreated with correct structure!', 'success')
        return f"""
        <div style="font-family: Arial; margin: 40px;">
            <h1>✅ CFB ML Tables Recreated Successfully!</h1>
            
            <div style="background: #d4edda; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>Tables Recreated:</h3>
                <ul>
                    <li>cfb_prediction_logs - ✅ Ready for predictions</li>
                    <li>cfb_temporal_analysis - ✅ Ready for temporal tracking</li>
                    <li>cfb_algorithm_performance - ✅ Ready for performance analysis</li>
                </ul>
            </div>
            
            <p><a href="/admin/ml" style="background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">🤖 Test ML Dashboard</a></p>
            <p><a href="/admin" style="background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">← Back to Admin</a></p>
        </div>
        """
        
    except Exception as e:
        return f"""
        <div style="font-family: Arial; margin: 40px;">
            <h1>❌ Error Recreating Tables</h1>
            <div style="background: #f8d7da; padding: 15px; border-radius: 8px;">
                <p><strong>Error:</strong> {e}</p>
            </div>
            <p><a href="/admin">Back to Admin</a></p>
        </div>
        """



# Add this temporary route to test critical functions
@app.route('/admin/test_core_functions')
@login_required
def test_core_functions():
    """Test that core functions still work"""
    try:
        results = []
        
        # Test team stats
        alabama_stats = calculate_comprehensive_stats('Alabama')
        results.append(f"✅ calculate_comprehensive_stats: {alabama_stats['total_wins']}-{alabama_stats['total_losses']}")
        
        # Test bulk loading
        all_stats = get_all_team_stats_bulk()
        results.append(f"✅ get_all_team_stats_bulk: {len(all_stats)} teams")
        
        # Test team logo
        logo_url = get_team_logo_url('Alabama')
        results.append(f"✅ get_team_logo_url: {logo_url}")
        
        # Test week info
        week_info = get_current_week_info()
        results.append(f"✅ get_current_week_info: Week {week_info['current_week']}")
        
        # Test games data
        games = get_games_data()
        results.append(f"✅ get_games_data: {len(games)} games")
        
        return f"""
        <h2>Core Functions Test Results</h2>
        <ul>{''.join(f'<li>{result}</li>' for result in results)}</ul>
        <p><a href="/admin">Back to Admin</a></p>
        """
        
    except Exception as e:
        return f"<h2>❌ Error in core functions:</h2><p>{e}</p>"


@app.route('/admin/ml/predict_week/<int:week>')
@login_required
def auto_predict_week(week):
    """Auto-predict all scheduled FBS vs FBS games for a specific week (excludes FCS games)"""
    try:
        # Get all unpredicted games for this week - EXCLUDE FCS GAMES
        all_unpredicted_games = ScheduledGame.query.filter(
            ScheduledGame.week == str(week),
            ScheduledGame.completed == False
        ).all()
        
        # Filter out FCS games and separate them
        fbs_games = []
        fcs_games_skipped = 0
        
        for game in all_unpredicted_games:
            if (is_fcs_opponent(game.home_team) or is_fcs_opponent(game.away_team)):
                fcs_games_skipped += 1
                continue
            fbs_games.append(game)
        
        # Check if we have any FBS vs FBS games to predict
        if not fbs_games:
            if fcs_games_skipped > 0:
                flash(f'No FBS vs FBS games found for Week {week}. Skipped {fcs_games_skipped} FCS games (not predicted).', 'info')
            else:
                flash(f'No unpredicted games found for Week {week}', 'info')
            return redirect(url_for('cfb_ml_dashboard'))
        
        # Track results
        successful_predictions = 0
        failed_predictions = 0
        skipped_predictions = 0
        results = []
        
        # Process each FBS vs FBS game
        for game in fbs_games:
            # Check if automated prediction already exists for this specific game
            existing = CFBPredictionLog.query.filter(
                CFBPredictionLog.week == str(week),
                CFBPredictionLog.home_team == game.home_team,
                CFBPredictionLog.away_team == game.away_team,
                CFBPredictionLog.prediction_type == 'automated'
            ).first()
            
            if existing:
                skipped_predictions += 1
                results.append(f"Already predicted: {game.away_team} @ {game.home_team}")
                continue
            
            # Generate prediction for this FBS vs FBS game
            success, message, pred_id = auto_predict_single_game(game, overwrite=False)
            
            if success:
                successful_predictions += 1
                results.append(f"Success: {message}")
            else:
                failed_predictions += 1
                results.append(f"Failed: {game.away_team} @ {game.home_team} - {message}")
        
        # Prepare summary message
        summary_parts = [
            f'Week {week} Auto-Prediction Results:',
            f'{successful_predictions} successful',
            f'{failed_predictions} failed', 
            f'{skipped_predictions} already predicted'
        ]
        
        if fcs_games_skipped > 0:
            summary_parts.append(f'{fcs_games_skipped} FCS games excluded')
        
        summary_message = ', '.join(summary_parts)
        
        # Show results with appropriate flash type
        if failed_predictions > 0:
            flash(summary_message, 'warning')
        else:
            flash(summary_message, 'success')
        
        # Generate detailed results HTML for display
        results_html = f"""
        <h2>Week {week} Auto-Prediction Results</h2>
        
        <div class="alert alert-info">
            <strong>Summary:</strong><br>
            • {successful_predictions} predictions created successfully<br>
            • {failed_predictions} predictions failed<br>
            • {skipped_predictions} games already had predictions<br>
            • {len(fbs_games)} total FBS vs FBS games processed<br>
            {f'• {fcs_games_skipped} FCS games excluded from predictions<br>' if fcs_games_skipped > 0 else ''}
        </div>
        
        <h3>Detailed Results:</h3>
        <div class="results-list">
        """
        
        for result in results:
            if result.startswith('Success'):
                results_html += f'<div class="alert alert-success">{result}</div>'
            elif result.startswith('Failed'):
                results_html += f'<div class="alert alert-danger">{result}</div>'
            else:
                results_html += f'<div class="alert alert-secondary">{result}</div>'
        
        results_html += f"""
        </div>
        
        <div class="mt-3">
            <a href="/admin/ml" class="btn btn-primary">Back to ML Dashboard</a>
            <a href="/admin/ml/batch_predict" class="btn btn-secondary">Batch Predict</a>
            <a href="/admin/ml/view_predictions/{week}" class="btn btn-info">View Week {week} Predictions</a>
        </div>
        """
        
        return results_html
        
    except Exception as e:
        flash(f'Error auto-predicting Week {week}: {str(e)}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))


@app.route('/admin/ml/batch_predict')
@login_required  
def batch_predict_interface():
    """Interface to select weeks for batch prediction (excluding FCS games)"""
    try:
        # Get all weeks that have scheduled FBS vs FBS games
        weeks_with_games = db.session.query(ScheduledGame.week).filter(
            ScheduledGame.completed == False,
            # Exclude FCS games
            ~(ScheduledGame.home_team.ilike('%FCS%')),
            ~(ScheduledGame.away_team.ilike('%FCS%')),
            ScheduledGame.home_team != 'FCS',
            ScheduledGame.away_team != 'FCS'
        ).distinct().all()
        
        available_weeks = [week[0] for week in weeks_with_games]
        available_weeks.sort(key=lambda x: int(x) if x.isdigit() else 999)
        
        weeks_data = []
        total_unpredicted = 0
        total_predicted = 0
        total_fcs_excluded = 0
        
        for week in available_weeks:
            # Count FBS vs FBS games only
            fbs_games = ScheduledGame.query.filter(
                ScheduledGame.week == week,
                ScheduledGame.completed == False,
                ~(ScheduledGame.home_team.ilike('%FCS%')),
                ~(ScheduledGame.away_team.ilike('%FCS%')),
                ScheduledGame.home_team != 'FCS',
                ScheduledGame.away_team != 'FCS'
            ).all()
            
            # Count total games including FCS to show what we're excluding
            all_games = ScheduledGame.query.filter(
                ScheduledGame.week == week,
                ScheduledGame.completed == False
            ).count()
            
            fbs_count = len(fbs_games)
            fcs_excluded = all_games - fbs_count
            total_fcs_excluded += fcs_excluded
            
            # Count existing automated predictions for FBS games
            predicted_count = 0
            for game in fbs_games:
                existing = CFBPredictionLog.query.filter(
                    CFBPredictionLog.week == week,
                    CFBPredictionLog.home_team == game.home_team,
                    CFBPredictionLog.away_team == game.away_team,
                    CFBPredictionLog.prediction_type == 'automated'
                ).first()
                if existing:
                    predicted_count += 1
            
            remaining = fbs_count - predicted_count
            
            week_data = {
                'week': week,
                'total_games': fbs_count,  # Only FBS games
                'predicted_count': predicted_count,
                'remaining': remaining,
                'fcs_excluded': fcs_excluded,  # NEW: Track excluded FCS games
                'is_complete': remaining == 0,
                'prediction_percentage': int((predicted_count / fbs_count * 100)) if fbs_count > 0 else 0
            }
            
            weeks_data.append(week_data)
            total_unpredicted += fbs_count
            total_predicted += predicted_count
        
        # Calculate overall stats
        batch_stats = {
            'total_weeks': len(available_weeks),
            'total_games': total_unpredicted,
            'total_predicted': total_predicted,
            'total_remaining': total_unpredicted - total_predicted,
            'total_fcs_excluded': total_fcs_excluded,  # NEW
            'overall_percentage': int((total_predicted / total_unpredicted * 100)) if total_unpredicted > 0 else 0
        }
        
        return render_template('batch_predict.html', 
                             weeks_data=weeks_data,
                             batch_stats=batch_stats)
        
    except Exception as e:
        flash(f'Error loading batch predict interface: {str(e)}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))



# Add this route to your app.py to view predictions

@app.route('/admin/ml/view_predictions/<week>')
@login_required
def view_week_predictions(week):
    """View all predictions for a specific week"""
    try:
        # Get all predictions for this week
        predictions = CFBPredictionLog.query.filter(
            CFBPredictionLog.week == str(week)
        ).order_by(CFBPredictionLog.prediction_date.desc()).all()
        
        if not predictions:
            flash(f'No predictions found for Week {week}', 'info')
            return redirect(url_for('cfb_ml_dashboard'))
        
        # Process predictions data for template
        predictions_data = []
        stats = {
            'total': len(predictions),
            'automated': 0,
            'manual': 0,
            'completed': 0,
            'pending': 0,
            'correct': 0,
            'wrong': 0
        }
        
        for pred in predictions:
            # Calculate stats
            if pred.prediction_type == 'automated':
                stats['automated'] += 1
            else:
                stats['manual'] += 1
                
            if pred.game_completed:
                stats['completed'] += 1
                if pred.winner_correct is True:
                    stats['correct'] += 1
                elif pred.winner_correct is False:
                    stats['wrong'] += 1
            else:
                stats['pending'] += 1
            
            # Process prediction data
            pred_data = {
                'id': pred.id,
                'matchup': f"{pred.away_team} @ {pred.home_team}",
                'predicted_winner': pred.predicted_winner,
                'predicted_margin': pred.predicted_margin,
                'win_probability': pred.win_probability,
                'confidence_level': pred.confidence_level or 'N/A',
                'prediction_type': pred.prediction_type,
                'prediction_date': pred.prediction_date,
                'game_completed': pred.game_completed,
                'winner_correct': pred.winner_correct,
                'actual_winner': pred.actual_winner
            }
            predictions_data.append(pred_data)
        
        # Calculate accuracy if there are completed games
        if stats['completed'] > 0:
            stats['accuracy'] = round((stats['correct'] / stats['completed']) * 100, 1)
        else:
            stats['accuracy'] = 0
        
        return render_template('week_predictions.html', 
                             week=week,
                             predictions=predictions_data,
                             stats=stats)
        
    except Exception as e:
        flash(f'Error loading predictions for Week {week}: {str(e)}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))


@app.route('/admin/ml/predictions')
@login_required
def view_all_predictions():
    """View all recent predictions"""
    try:
        # Get all predictions from last 30 days
        from datetime import datetime, timedelta
        recent_date = datetime.utcnow() - timedelta(days=30)
        
        predictions = CFBPredictionLog.query.filter(
            CFBPredictionLog.prediction_date >= recent_date
        ).order_by(CFBPredictionLog.week, CFBPredictionLog.prediction_date.desc()).all()
        
        # Group by week and calculate stats
        weeks_data = {}
        for pred in predictions:
            if pred.week not in weeks_data:
                weeks_data[pred.week] = {
                    'predictions': [],
                    'automated_count': 0,
                    'manual_count': 0,
                    'total_count': 0
                }
            
            weeks_data[pred.week]['predictions'].append(pred)
            weeks_data[pred.week]['total_count'] += 1
            
            if pred.prediction_type == 'automated':
                weeks_data[pred.week]['automated_count'] += 1
            else:
                weeks_data[pred.week]['manual_count'] += 1
        
        # Sort weeks in descending order (most recent first)
        sorted_weeks = dict(sorted(weeks_data.items(), key=lambda x: x[0], reverse=True))
        
        return render_template('ml_predictions.html', 
                             weeks_data=sorted_weeks,
                             total_predictions=len(predictions))
        
    except Exception as e:
        flash(f'Error loading predictions: {str(e)}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))


@app.route('/admin/ml/export_season_data')
@login_required
def export_season_data():
    """Export all prediction data for ML analysis"""
    try:
        # Get all completed predictions
        predictions = CFBPredictionLog.query.filter(
            CFBPredictionLog.game_completed == True
        ).all()
        
        # Convert to list of dictionaries
        data = []
        for pred in predictions:
            row = {
                'week': pred.week,
                'home_team': pred.home_team,
                'away_team': pred.away_team,
                'predicted_winner': pred.predicted_winner,
                'actual_winner': pred.actual_winner,
                'predicted_margin': pred.predicted_margin,
                'actual_margin': pred.actual_margin,
                'margin_error': pred.margin_error,
                'predicted_total': pred.predicted_total,
                'actual_total': pred.actual_total,
                'total_error': pred.total_error,
                'winner_correct': pred.winner_correct,
                'win_probability': pred.win_probability,
                'confidence_level': pred.confidence_level,
                'prediction_type': pred.prediction_type,
                
                # Structured factors
                'base_strength_diff': pred.base_strength_diff,
                'schedule_strength_factor': pred.schedule_strength_factor,
                'momentum_factor': pred.momentum_factor,
                'location_factor': pred.location_factor,
                'consistency_factor': pred.consistency_factor,
                'common_opponent_factor': pred.common_opponent_factor,
                
                # Algorithm settings
                'temporal_weights': json.loads(pred.temporal_weights_json) if pred.temporal_weights_json else None,
                'algorithm_version': pred.algorithm_version,
                
                'prediction_date': pred.prediction_date.isoformat() if pred.prediction_date else None,
                'result_date': pred.result_date.isoformat() if pred.result_date else None
            }
            data.append(row)
        
        # Return as JSON for easy analysis
        from flask import jsonify
        return jsonify({
            'season_data': data,
            'total_predictions': len(data),
            'export_date': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return f"Export error: {str(e)}"

@app.route('/ai/game_analysis/<int:game_id>')
def ai_game_explanation(game_id):
    """Public AI explanation for a specific game"""
    if not CFB_GEN_AI_ENABLED:
        flash('Gen AI features are not available', 'error')
        return redirect(url_for('rankings'))
    
    try:
        # Get the game from database
        game = Game.query.get_or_404(game_id)
        game_data = game.to_dict()
        
        # Determine winner
        if game_data['home_score'] > game_data['away_score']:
            winner = game_data['home_team']
            loser = game_data['away_team']
        else:
            winner = game_data['away_team'] 
            loser = game_data['home_team']
            
        # Transform data for victory value function
        winner_game_data = {
            'result': 'W',
            'opponent': loser,
            'team_score': game_data['home_score'] if winner == game_data['home_team'] else game_data['away_score'],
            'opp_score': game_data['away_score'] if winner == game_data['home_team'] else game_data['home_score'],
            'home_away': 'Home' if winner == game_data['home_team'] else 'Away',
            'overtime': game_data.get('overtime', False)
        }
        
        # Calculate victory value
        victory_value = calculate_victory_value_with_rivalry(winner_game_data, winner)
        
        # Get AI explanation  
        explanation = explain_game_impact(game_data, victory_value, winner)
        
        # Calculate margin
        margin = abs(game_data['home_score'] - game_data['away_score'])
        
        # Render the template with all the data
        return render_template('ai_game_analysis.html',
                             home_team=game_data['home_team'],
                             away_team=game_data['away_team'],
                             home_score=game_data['home_score'],
                             away_score=game_data['away_score'],
                             winner=winner,
                             week=game_data['week'],
                             margin=margin,
                             victory_value=victory_value,
                             explanation=explanation,
                             overtime=game_data.get('overtime', False),
                             datetime_generated=datetime.now().strftime('%B %d, %Y at %I:%M %p'))
        
    except Exception as e:
        flash(f'Error generating game analysis: {str(e)}', 'error')
        return redirect(url_for('rankings'))

# Add these routes to your app.py after your existing AI routes

@app.route('/ai/weekly_preview/<week>')
def ai_weekly_preview(week):
    """AI-generated weekly preview for scheduled games"""
    if not CFB_GEN_AI_ENABLED:
        flash('Gen AI features are not available', 'error')
        return redirect(url_for('scoreboard', week=week))
    
    try:
        # Get scheduled games for this week
        all_scheduled = get_scheduled_games_list()
        week_games = [game for game in all_scheduled 
                     if game['week'] == week and not game.get('completed', False)]
        
        if not week_games:
            # No games found - still use template
            return render_template('ai_weekly_preview.html',
                                 week=week,
                                 total_games=0,
                                 ranked_matchups=0,
                                 datetime_generated=datetime.now().strftime('%B %d, %Y at %I:%M %p'),
                                 preview_text="No scheduled games found for this week.",
                                 game_previews=[])
        
        # Get current rankings for context
        try:
            all_teams_stats = get_all_team_stats_bulk()
            team_rankings = {}
            for i, team_data in enumerate(all_teams_stats, 1):
                if i <= 25:  # Only rank top 25
                    team_rankings[team_data['team']] = i
        except:
            team_rankings = {}
        
        # Generate AI preview
        preview_text = generate_weekly_preview(week, week_games, team_rankings)
        
        # Count key stats
        total_games = len(week_games)
        ranked_matchups = 0
        for game in week_games:
            home_ranked = team_rankings.get(game.get('home_team'), 'NR') != 'NR'
            away_ranked = team_rankings.get(game.get('away_team'), 'NR') != 'NR'
            if home_ranked and away_ranked:
                ranked_matchups += 1
        
        # Build game list for display
        game_previews = []
        for game in week_games[:10]:  # Show top 10 games
            home_team = game.get('home_team', 'TBD')
            away_team = game.get('away_team', 'TBD')
            
            home_rank = team_rankings.get(home_team, None)
            away_rank = team_rankings.get(away_team, None)
            
            # Format display
            home_display = f"#{home_rank} {home_team}" if home_rank else home_team
            away_display = f"#{away_rank} {away_team}" if away_rank else away_team
            
            vs_symbol = "vs" if game.get('neutral') else "@"
            
            game_previews.append({
                'matchup': f"{away_display} {vs_symbol} {home_display}",
                'time': game.get('game_time', ''),
                'tv': game.get('tv_network', ''),
                'is_ranked_matchup': bool(home_rank and away_rank)
            })
        
        # Render the template with all the data
        return render_template('ai_weekly_preview.html',
                             week=week,
                             total_games=total_games,
                             ranked_matchups=ranked_matchups,
                             datetime_generated=datetime.now().strftime('%B %d, %Y at %I:%M %p'),
                             preview_text=preview_text,
                             game_previews=game_previews)
        
    except Exception as e:
        flash(f'Error generating weekly preview: {str(e)}', 'error')
        return redirect(url_for('scoreboard', week=week))



@app.route('/admin/ml/debug_data_types')
@login_required
def debug_data_types():
    """Debug data types in team stats"""
    try:
        test_team = TeamStats.query.first()
        if test_team:
            return f"""
            <h2>Debug Data Types</h2>
            <p>wins: {test_team.wins} (type: {type(test_team.wins)})</p>
            <p>losses: {test_team.losses} (type: {type(test_team.losses)})</p>
            <p>points_for: {test_team.points_for} (type: {type(test_team.points_for)})</p>
            <p>points_against: {test_team.points_against} (type: {type(test_team.points_against)})</p>
            """
        else:
            return "No team stats found"
    except Exception as e:
        return f"Error: {e}"


@app.route('/ai/explain_ranking/<team_name>')
def ai_explain_ranking(team_name):
    """AI explanation of team's current ranking"""
    if not CFB_GEN_AI_ENABLED:
        flash('Gen AI features are not available', 'error')
        return redirect(url_for('rankings'))
    
    try:
        from urllib.parse import unquote
        decoded_team_name = unquote(team_name)
        
        # Get team's current ranking data
        all_teams_stats = get_all_team_stats_bulk()
        team_ranking_data = None
        current_rank = 'NR'
        
        for i, team_data in enumerate(all_teams_stats):
            if team_data['team'] == decoded_team_name:
                team_ranking_data = team_data
                current_rank = i + 1 if i < 25 else 'NR'
                break
        
        if not team_ranking_data:
            flash(f'{decoded_team_name} not found in current rankings', 'error')
            return redirect(url_for('rankings'))
        
        # Get detailed team stats
        team_stats_record = TeamStats.query.filter_by(team_name=decoded_team_name).first()
        team_stats = team_stats_record.to_dict() if team_stats_record else {}
        
        # Get comparison teams (teams ranked similarly)
        comparison_teams = []
        if current_rank != 'NR':
            start_idx = max(0, current_rank - 3)
            end_idx = min(len(all_teams_stats), current_rank + 2)
            comparison_teams = all_teams_stats[start_idx:end_idx]
            comparison_teams = [t for t in comparison_teams if t['team'] != decoded_team_name]
        
        # Add rank to team_ranking_data
        team_ranking_data['rank'] = current_rank
        
        # Generate AI explanation
        explanation = explain_team_ranking(
            decoded_team_name, 
            team_ranking_data, 
            team_stats, 
            comparison_teams
        )
        
        # Get some key stats for display
        record = f"{team_ranking_data['total_wins']}-{team_ranking_data['total_losses']}"
        conference = team_ranking_data['conference']
        adjusted_total = round(team_ranking_data['adjusted_total'], 2)
        
        # Get notable games
        notable_games = []
        if 'games' in team_stats:
            for game in team_stats['games']:
                opponent = game.get('opponent', '')
                result = game.get('result', '')
                team_score = game.get('team_score', 0)
                opp_score = game.get('opp_score', 0)
                
                # Look for games against ranked opponents or notable teams
                notable_teams = ['Alabama', 'Georgia', 'Ohio State', 'Michigan', 'Texas', 
                               'Notre Dame', 'Oklahoma', 'LSU', 'Florida', 'Penn State', 
                               'Oregon', 'USC', 'Clemson', 'Tennessee', 'Florida State']
                
                if any(notable in opponent for notable in notable_teams):
                    status = "W" if result == 'W' else "L"
                    notable_games.append({
                        'opponent': opponent,
                        'result': status,
                        'score': f"{team_score}-{opp_score}",
                        'color': '#d4edda' if result == 'W' else '#f8d7da'
                    })
        
        # Limit to 5 most notable games
        notable_games = notable_games[:5]
        
        # Render the template with all the data
        return render_template('ai_team_explanation.html',
                             team_name=decoded_team_name,
                             current_rank=current_rank,
                             record=record,
                             conference=conference,
                             adjusted_total=adjusted_total,
                             explanation=explanation,
                             notable_games=notable_games,
                             datetime_generated=datetime.now().strftime('%B %d, %Y at %I:%M %p'))
        
    except Exception as e:
        flash(f'Error generating team analysis: {str(e)}', 'error')
        return redirect(url_for('rankings'))

@app.route('/ai/enhanced_prediction', methods=['POST'])
def ai_enhanced_prediction():
    """Enhanced matchup prediction with AI analysis"""
    if not CFB_GEN_AI_ENABLED:
        return {'error': 'Gen AI not available'}, 503
    
    try:
        team1 = request.form.get('team1')
        team2 = request.form.get('team2')
        location = request.form.get('location', 'neutral')
        
        if not team1 or not team2:
            return {'error': 'Please select both teams'}, 400
        
        if team1 == team2:
            return {'error': 'Please select different teams'}, 400
        
        # Get your existing prediction
        prediction_data = predict_matchup_ultra_enhanced(team1, team2, location)
        
        # Get team stats for AI context
        team1_stats_record = TeamStats.query.filter_by(team_name=team1).first()
        team2_stats_record = TeamStats.query.filter_by(team_name=team2).first()
        
        team1_stats = team1_stats_record.to_dict() if team1_stats_record else {}
        team2_stats = team2_stats_record.to_dict() if team2_stats_record else {}
        
        # Generate AI analysis
        ai_analysis = enhance_matchup_prediction(
            team1, team2, prediction_data, team1_stats, team2_stats
        )
        
        # Return enhanced prediction with AI
        return {
            'prediction': prediction_data,
            'ai_analysis': ai_analysis,
            'teams': {
                'team1': {
                    'name': team1,
                    'record': f"{team1_stats.get('wins', 0)}-{team1_stats.get('losses', 0)}"
                },
                'team2': {
                    'name': team2,
                    'record': f"{team2_stats.get('wins', 0)}-{team2_stats.get('losses', 0)}"
                }
            }
        }
        
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/debug/ai_functions')
@login_required
def debug_ai_functions():
    """Debug what AI functions are available"""
    try:
        import cfb_gen_ai
        
        # List all functions in the module
        functions = [func for func in dir(cfb_gen_ai) if callable(getattr(cfb_gen_ai, func)) and not func.startswith('_')]
        
        return f"""
        <h2>AI Functions Debug</h2>
        <h3>Available functions in cfb_gen_ai.py:</h3>
        <ul>
        {''.join(f'<li>{func}</li>' for func in functions)}
        </ul>
        
        <h3>Expected functions:</h3>
        <ul>
            <li>explain_game_impact ✓</li>
            <li>generate_weekly_preview {'✓' if 'generate_weekly_preview' in functions else '❌'}</li>
            <li>explain_team_ranking {'✓' if 'explain_team_ranking' in functions else '❌'}</li>
            <li>enhance_matchup_prediction {'✓' if 'enhance_matchup_prediction' in functions else '❌'}</li>
        </ul>
        
        <p><a href="/admin">Back to Admin</a></p>
        """
    except Exception as e:
        return f"<h2>Error loading cfb_gen_ai:</h2><p>{e}</p>"

@app.route('/ai/ask', methods=['GET', 'POST'])
def ai_ask():
    """Natural language query interface for CFB rankings"""
    if not CFB_GEN_AI_ENABLED:
        flash('Gen AI features are not available', 'error')
        return redirect(url_for('rankings'))
    
    if request.method == 'GET':
        # Just show the form
        return render_template('ai_ask.html', 
                             query='',
                             response='',
                             recent_queries=[])
    
    # POST - Process the query
    try:
        query = request.form.get('query', '').strip()
        
        if not query:
            flash('Please enter a question!', 'error')
            return render_template('ai_ask.html',
                                 query='',
                                 response='',
                                 recent_queries=[])
        
        # Build context data for the AI
        context_data = {}
        
        # Get current top 25 rankings
        try:
            all_teams_stats = get_all_team_stats_bulk()
            context_data['top_25'] = all_teams_stats[:25]
        except:
            context_data['top_25'] = []
        
        # Get recent games (last 10)
        try:
            recent_games = get_games_data()[-10:]
            context_data['recent_games'] = recent_games
        except:
            context_data['recent_games'] = []
        
        # Extract team names from query and get their stats
        team_stats = {}
        for team_data in all_teams_stats[:50]:  # Check top 50 teams
            team_name = team_data['team']
            # Simple check if team is mentioned in query
            if team_name.lower() in query.lower():
                # Get detailed stats for this team
                try:
                    team_record = TeamStats.query.filter_by(team_name=team_name).first()
                    if team_record:
                        stats = team_record.to_dict()
                        stats['conference'] = team_data['conference']
                        stats['adjusted_total'] = team_data['adjusted_total']
                        stats['rank'] = all_teams_stats.index(team_data) + 1
                        team_stats[team_name] = stats
                except:
                    pass
        
        if team_stats:
            context_data['team_stats'] = team_stats
        
        # Call the AI function
        response = process_natural_language_query(query, context_data)
        
        # Store recent queries in session (optional)
        if 'recent_queries' not in session:
            session['recent_queries'] = []
        
        session['recent_queries'].insert(0, {
            'query': query[:100],  # Truncate long queries
            'timestamp': datetime.now().strftime('%I:%M %p')
        })
        
        # Keep only last 5 queries
        session['recent_queries'] = session['recent_queries'][:5]
        
        return render_template('ai_ask.html',
                             query=query,
                             response=response,
                             recent_queries=session.get('recent_queries', []))
        
    except Exception as e:
        flash(f'Error processing query: {str(e)}', 'error')
        return render_template('ai_ask.html',
                             query=request.form.get('query', ''),
                             response='',
                             recent_queries=session.get('recent_queries', []))

@app.route('/ai/weekly_report')
@app.route('/ai/weekly_report/<week>')
def ai_weekly_report(week=None):
    """Automated weekly summary based on selected week context"""
    if not CFB_GEN_AI_ENABLED:
        flash('Gen AI features are not available', 'error')
        return redirect(url_for('rankings'))

    # Build context data
    context_data = {}
    
    try:
        # Get ALL games
        all_games = get_games_data()
        
        # DEBUG: Print total games found
        print(f"DEBUG: Found {len(all_games)} total games in database")
        
        if week:
            # Filter to games from the specified week
            week_games = [game for game in all_games if game['week'] == week]
            context_data['recent_games'] = week_games
            report_title = f"Week {week} Results"
            print(f"DEBUG: Filtered to {len(week_games)} games for week {week}")
        else:
            # Default: get last 10 games (original behavior)
            recent_games = all_games[-10:] if all_games else []
            context_data['recent_games'] = recent_games
            report_title = "Recent Games"
            print(f"DEBUG: Using last {len(recent_games)} games")
        
        # DEBUG: Print the games being passed to AI
        for i, game in enumerate(context_data['recent_games']):
            print(f"DEBUG Game {i+1}: {game['away_team']} {game['away_score']}-{game['home_score']} {game['home_team']}")
        
    except Exception as e:
        print(f"DEBUG: Error getting games: {e}")
        context_data['recent_games'] = []

    try:
        # Get current top 10 for ranking context
        all_teams_stats = get_all_team_stats_bulk()
        top_teams = all_teams_stats[:10]
        
        ranking_changes = []
        for i, team in enumerate(top_teams, 1):
            ranking_changes.append({
                'team': team['team'],
                'movement_text': f"Ranked #{i}",
                'record': f"{team['total_wins']}-{team['total_losses']}"
            })
        
        context_data['ranking_changes'] = ranking_changes
        print(f"DEBUG: Added {len(ranking_changes)} ranking changes")
        
    except Exception as e:
        print(f"DEBUG: Error getting rankings: {e}")
        context_data['ranking_changes'] = []

    # DEBUG: Print what we're sending to AI
    print(f"DEBUG: Sending to AI - {len(context_data['recent_games'])} games, {len(context_data['ranking_changes'])} rankings")

    # Call the AI function to generate the report
    report_text = generate_weekly_report(context_data)
    
    # DEBUG: Print first 100 chars of AI response
    print(f"DEBUG: AI returned: {report_text[:100]}...")

    # Render the weekly report template
    return render_template('ai_weekly_report.html', 
                         report=report_text, 
                         week=week, 
                         report_title=report_title)


def update_team_stats_simplified(team, opponent, team_score, opp_score, is_home, is_neutral_site=False, is_overtime=False):
    """Update team statistics after a game - SIMPLIFIED without game types"""
    
    # Special case: Don't update stats for FCS placeholder team
    if team == 'FCS' or team.upper() == 'FCS':
        return
    
    # Determine win/loss and margin of victory
    if team_score > opp_score:
        team_stats[team]['wins'] += 1
        # Add margin of victory (only for wins)
        team_stats[team]['margin_of_victory_total'] += (team_score - opp_score)
        
        # Track home/road wins (only if NOT neutral site)
        if not is_neutral_site:
            if is_home:
                team_stats[team]['home_wins'] += 1
            else:
                team_stats[team]['road_wins'] += 1
        
        # REMOVED: P4/G5 win tracking (no longer needed)
    else:
        team_stats[team]['losses'] += 1
        # REMOVED: P4/G5 loss tracking (no longer needed)
    
    # Update points
    team_stats[team]['points_for'] += team_score
    team_stats[team]['points_against'] += opp_score
    
    # Determine game location for display
    if is_neutral_site:
        location = 'Neutral'
    elif is_home:
        location = 'Home'
    else:
        location = 'Away'
    
    # Add game to history - ADDED overtime field
    team_stats[team]['games'].append({
        'opponent': opponent,
        'team_score': team_score,
        'opp_score': opp_score,
        'result': 'W' if team_score > opp_score else 'L',
        'home_away': location,
        'overtime': is_overtime  # NEW: Store overtime status for each game
    })

def analyze_common_opponents(team1_name, team2_name):
    """Analyze how both teams performed against common opponents"""
    team1_record = TeamStats.query.filter_by(team_name=team1_name).first()  # 
    team2_record = TeamStats.query.filter_by(team_name=team2_name).first()  # 
    
    if not team1_record or not team2_record:  # 
        return {  # 
            'has_common': False,  # 
            'comparison': [],  # 
            'advantage': 0,  # 
            'summary': "No common opponents"  # 
        }  # 
    
    team1_games = team1_record.to_dict()['games']  # 
    team2_games = team2_record.to_dict()['games']  # 
    
    # Find common opponents
    team1_opponents = {game['opponent'] for game in team1_games}
    team2_opponents = {game['opponent'] for game in team2_games}
    common_opponents = team1_opponents.intersection(team2_opponents)
    
    if not common_opponents:
        return {
            'has_common': False,
            'comparison': [],
            'advantage': 0,
            'summary': "No common opponents"
        }
    
    comparisons = []
    total_advantage = 0
    
    for opponent in common_opponents:
        # Find team1's game against this opponent
        team1_game = next((g for g in team1_games if g['opponent'] == opponent), None)
        team2_game = next((g for g in team2_games if g['opponent'] == opponent), None)
        
        if team1_game and team2_game:
            # Calculate point differential for each team
            team1_diff = team1_game['team_score'] - team1_game['opp_score']
            team2_diff = team2_game['team_score'] - team2_game['opp_score']
            
            advantage = team1_diff - team2_diff
            total_advantage += advantage
            
            comparisons.append({
                'opponent': opponent,
                'team1_result': f"{team1_game['result']} {team1_game['team_score']}-{team1_game['opp_score']}",
                'team2_result': f"{team2_game['result']} {team2_game['team_score']}-{team2_game['opp_score']}",
                'team1_diff': team1_diff,
                'team2_diff': team2_diff,
                'advantage': advantage
            })
    
    avg_advantage = total_advantage / len(comparisons) if comparisons else 0
    
    return {
        'has_common': True,
        'comparison': comparisons,
        'advantage': round(avg_advantage, 1),
        'summary': f"Common opponents favor {'Team 1' if avg_advantage > 0 else 'Team 2'} by {abs(avg_advantage):.1f} points per game"
    }

def calculate_recent_form(team_name, games_back=4):
    """Calculate recent form over last N games"""
    team_record = TeamStats.query.filter_by(team_name=team_name).first()  # 
    if not team_record:  # 
        return {  # 
            'record': '0-0',  # 
            'avg_margin': 0,  # 
            'trending': 'neutral',  # 
            'last_games': []  # 
        }  # 
    
    games = team_record.to_dict()['games']  # 
    if len(games) < games_back:
        games_back = len(games)
    
    if games_back == 0:
        return {
            'record': '0-0',
            'avg_margin': 0,
            'trending': 'neutral',
            'last_games': []
        }
    
    recent_games = games[-games_back:]
    wins = sum(1 for g in recent_games if g['result'] == 'W')
    losses = len(recent_games) - wins
    
    # Calculate average margin (positive = winning by, negative = losing by)
    total_margin = sum((g['team_score'] - g['opp_score']) for g in recent_games)
    avg_margin = total_margin / len(recent_games)
    
    # Determine trend (are margins improving or declining?)
    if len(recent_games) >= 2:
        first_half = recent_games[:len(recent_games)//2]
        second_half = recent_games[len(recent_games)//2:]
        
        first_avg = sum((g['team_score'] - g['opp_score']) for g in first_half) / len(first_half)
        second_avg = sum((g['team_score'] - g['opp_score']) for g in second_half) / len(second_half)
        
        if second_avg > first_avg + 3:
            trending = 'up'
        elif second_avg < first_avg - 3:
            trending = 'down'
        else:
            trending = 'neutral'
    else:
        trending = 'neutral'
    
    return {
        'record': f"{wins}-{losses}",
        'avg_margin': round(avg_margin, 1),
        'trending': trending,
        'last_games': recent_games[-3:]  # Show last 3 games
    }

def analyze_style_matchup(team1_name, team2_name):
    """Analyze offensive vs defensive matchups"""
    team1_stats = calculate_comprehensive_stats(team1_name)
    team2_stats = calculate_comprehensive_stats(team2_name)
    
    # Calculate per-game averages
    team1_games = team1_stats['total_wins'] + team1_stats['total_losses']
    team2_games = team2_stats['total_wins'] + team2_stats['total_losses']
    
    if team1_games == 0 or team2_games == 0:
        return {
            'team1_offense': 0,
            'team1_defense': 0,
            'team2_offense': 0,
            'team2_defense': 0,
            'analysis': "Insufficient data for style analysis"
        }
    
    team1_ppg = team1_stats['points_fielded'] / team1_games
    team1_papg = team1_stats['points_allowed'] / team1_games
    team2_ppg = team2_stats['points_fielded'] / team2_games
    team2_papg = team2_stats['points_allowed'] / team2_games
    
    # Simple matchup analysis
    matchup_analysis = []
    
    if team1_ppg > team2_papg + 5:
        matchup_analysis.append(f"{team1_name}'s offense vs {team2_name}'s defense favors {team1_name}")
    elif team2_papg > team1_ppg + 5:
        matchup_analysis.append(f"{team1_name}'s offense vs {team2_name}'s defense favors {team2_name}")
    
    if team2_ppg > team1_papg + 5:
        matchup_analysis.append(f"{team2_name}'s offense vs {team1_name}'s defense favors {team2_name}")
    elif team1_papg > team2_ppg + 5:
        matchup_analysis.append(f"{team2_name}'s offense vs {team1_name}'s defense favors {team1_name}")
    
    if not matchup_analysis:
        matchup_analysis.append("Evenly matched on both sides of the ball")
    
    return {
        'team1_offense': round(team1_ppg, 1),
        'team1_defense': round(team1_papg, 1),
        'team2_offense': round(team2_ppg, 1),
        'team2_defense': round(team2_papg, 1),
        'analysis': "; ".join(matchup_analysis)
    }

def head_to_head_history(team1_name, team2_name):
    """Check if teams have played each other recently"""
    team1_record = TeamStats.query.filter_by(team_name=team1_name).first()  # 
    if not team1_record:  # 
        return {  # 
            'has_history': False,  # 
            'summary': "Teams have not played each other"  # 
        }  # 
    
    team1_games = team1_record.to_dict()['games']  # 
    
    # Look for games against each other
    h2h_games = [g for g in team1_games if g['opponent'] == team2_name]
    
    if not h2h_games:
        return {
            'has_history': False,
            'summary': "Teams have not played each other"
        }
    
    # Get most recent game
    recent_game = h2h_games[-1]
    team1_wins = sum(1 for g in h2h_games if g['result'] == 'W')
    team1_losses = len(h2h_games) - team1_wins
    
    return {
        'has_history': True,
        'record': f"{team1_name} leads {team1_wins}-{team1_losses}",
        'last_game': recent_game,
        'summary': f"Last meeting: {team1_name} {recent_game['result']} {recent_game['team_score']}-{recent_game['opp_score']}"
    }

def predict_matchup_enhanced(team1_name, team2_name, location='neutral'):
    """
    ENHANCED comprehensive matchup prediction using scientific ranking system
    """
    # Get scientific ranking breakdowns
    team1_scientific = calculate_scientific_ranking(team1_name)
    team2_scientific = calculate_scientific_ranking(team2_name)
    
    team1_stats = calculate_comprehensive_stats(team1_name)
    team2_stats = calculate_comprehensive_stats(team2_name)
    
    # 1. CORE STRENGTH DIFFERENTIAL (Primary Factor - 60% weight)
    strength_diff = team1_scientific['total_score'] - team2_scientific['total_score']
    base_prediction = strength_diff * 2.2  # Refined scaling factor
    
    # 2. ENHANCED ADJUSTMENTS
    adjustments = {}
    total_adjustment = 0
    
    # A. Common Opponents Analysis (Enhanced)
    common_analysis = analyze_common_opponents_enhanced(team1_name, team2_name)
    if common_analysis['has_common'] and common_analysis['games_count'] >= 2:
        # Weight by number of common opponents and recency
        common_weight = min(0.4, common_analysis['games_count'] * 0.15)
        common_adj = common_analysis['advantage'] * common_weight
        adjustments['Common Opponents'] = round(common_adj, 1)
        total_adjustment += common_adj
    
    # B. Victory Quality Comparison
    victory_quality_diff = analyze_victory_quality_differential(team1_name, team2_name)
    if victory_quality_diff['significant']:
        adjustments['Victory Quality'] = victory_quality_diff['adjustment']
        total_adjustment += victory_quality_diff['adjustment']
    
    # C. Recent Form Analysis (Enhanced)
    team1_form = calculate_enhanced_recent_form(team1_name)
    team2_form = calculate_enhanced_recent_form(team2_name)
    
    form_differential = team1_form['momentum_score'] - team2_form['momentum_score']
    form_adj = form_differential * 0.8  # Increased weight for recent form
    if abs(form_adj) > 0.3:  # Only apply if significant
        adjustments['Recent Momentum'] = round(form_adj, 1)
        total_adjustment += form_adj
    
    # D. Conference Context (More Nuanced)
    conf_adj = calculate_conference_matchup_adjustment(team1_name, team2_name)
    if conf_adj != 0:
        adjustments['Conference Differential'] = conf_adj
        total_adjustment += conf_adj
    
    # E. Schedule Strength Comparison
    schedule_diff = analyze_schedule_strength_differential(team1_name, team2_name)
    if abs(schedule_diff) > 0.5:
        adjustments['Schedule Strength'] = round(schedule_diff, 1)
        total_adjustment += schedule_diff
    
    # F. Consistency Factor
    consistency_diff = (team1_scientific['components']['consistency_factor'] - 
                       team2_scientific['components']['consistency_factor'])
    if abs(consistency_diff) > 0.2:
        consistency_adj = consistency_diff * 2.0  # Amplify consistency impact
        adjustments['Consistency Edge'] = round(consistency_adj, 1)
        total_adjustment += consistency_adj
    
    # G. Home Field Advantage (Enhanced)
    hfa_adj = calculate_enhanced_home_field_advantage(team1_name, team2_name, location)
    if hfa_adj != 0:
        adjustments['Home Field Advantage'] = hfa_adj
        total_adjustment += hfa_adj
    
    # 3. FINAL PREDICTION CALCULATION
    final_margin = base_prediction + total_adjustment
    
    # 4. CONFIDENCE AND WIN PROBABILITY
    confidence_metrics = calculate_prediction_confidence(
        team1_name, team2_name, final_margin, adjustments
    )
    
    # Enhanced win probability calculation
    win_prob = calculate_enhanced_win_probability(final_margin, confidence_metrics)
    
    return {
        'base_margin': round(base_prediction, 1),
        'adjustments': adjustments,
        'final_margin': round(final_margin, 1),
        'win_probability': round(win_prob, 1),
        'winner': team1_name if final_margin > 0 else team2_name,
        'confidence': confidence_metrics['level'],
        'confidence_score': confidence_metrics['score'],
        'key_factors': identify_key_prediction_factors(adjustments, team1_scientific, team2_scientific),
        'detailed_breakdown': {
            'team1_scientific': team1_scientific,
            'team2_scientific': team2_scientific,
            'strength_differential': round(strength_diff, 2)
        }
    }

@track_prediction('ultra_enhanced_matchup')
def predict_matchup_ultra_enhanced(team1_name, team2_name, location='neutral'):
    """
    ULTRA-ENHANCED matchup prediction using all 8 analytical modules
    NOW WITH REALISTIC POINT SPREAD CAPS
    """
    try:
        # Handle FCS matchups first
        if team1_name == 'FCS' and team2_name == 'FCS':
            return {
                'base_margin': 0.0,
                'adjustments': {},
                'final_margin': 3.0,
                'win_probability': 55.0,
                'winner': team1_name,
                'confidence': 'Low',
                'confidence_score': 0.3,
                'prediction_methodology': 'FCS vs FCS Default'
            }
        elif team1_name == 'FCS':
            return {
                'base_margin': 20.0,
                'adjustments': {'FCS Opponent': 'Auto-loss'},
                'final_margin': 20.0,
                'win_probability': 85.0,
                'winner': team2_name,
                'confidence': 'High',
                'confidence_score': 0.85,
                'prediction_methodology': 'FCS Auto-Loss'
            }
        elif team2_name == 'FCS':
            return {
                'base_margin': 20.0,
                'adjustments': {'FCS Opponent': 'Auto-win'},
                'final_margin': 20.0,
                'win_probability': 85.0,
                'winner': team1_name,
                'confidence': 'High',
                'confidence_score': 0.85,
                'prediction_methodology': 'FCS Auto-Win'
            }

        # Get enhanced scientific rankings
        team1_enhanced = calculate_enhanced_scientific_ranking(team1_name)
        team2_enhanced = calculate_enhanced_scientific_ranking(team2_name)
        
        # ✅ FIXED: Much smaller base multiplier
        strength_diff = team1_enhanced['total_score'] - team2_enhanced['total_score']
        base_prediction = strength_diff * 0.85  # Changed from 2.2 to 0.85
        
        # Cap base prediction before adjustments
        base_prediction = max(-21, min(21, base_prediction))
        
        # Enhanced adjustments
        adjustments = {}
        
        # Module 1: Schedule strength (keep existing)
        try:
            team1_schedule_strength = calculate_strength_of_schedule_rating(team1_name)
            team2_schedule_strength = calculate_strength_of_schedule_rating(team2_name)
            schedule_diff = (team1_schedule_strength - team2_schedule_strength) * 0.6  # Reduced from 0.8
            if abs(schedule_diff) > 0.5:
                adjustments['Enhanced Schedule Strength'] = round(schedule_diff, 1)
        except:
            pass
        
        # Module 2: Victory value comparison (reduced impact)
        team1_games = max(1, team1_enhanced['basic_stats']['total_games'])
        team2_games = max(1, team2_enhanced['basic_stats']['total_games'])
        team1_victory_avg = team1_enhanced['components']['adjusted_victory_value'] / team1_games
        team2_victory_avg = team2_enhanced['components']['adjusted_victory_value'] / team2_games
        victory_diff = (team1_victory_avg - team2_victory_avg) * 1.0  # Reduced from 1.5
        if abs(victory_diff) > 0.8:
            adjustments['Victory Quality Edge'] = round(victory_diff, 1)
        
        # Module 4: Momentum (reduced impact)
        team1_momentum = team1_enhanced['components']['temporal_adjustment']
        team2_momentum = team2_enhanced['components']['temporal_adjustment']
        momentum_diff = (team1_momentum - team2_momentum) * 1.0  # Reduced from 1.5
        if abs(momentum_diff) > 0.3:
            adjustments['Recent Momentum Edge'] = round(momentum_diff, 1)
        
        # Module 5: Consistency (keep as is)
        team1_consistency = team1_enhanced['components']['consistency_factor']
        team2_consistency = team2_enhanced['components']['consistency_factor']
        consistency_diff = (team1_consistency - team2_consistency) * 2.0
        if abs(consistency_diff) > 0.2:
            adjustments['Consistency Advantage'] = round(consistency_diff, 1)
        
        # Enhanced location advantage (cap at reasonable values)
        location_adj = calculate_enhanced_location_advantage(team1_name, team2_name, location)
        location_adj = max(-4.5, min(4.5, location_adj))  # Cap home field at ±4.5
        if location_adj != 0:
            adjustments['Enhanced Home Field'] = round(location_adj, 1)
        
        # Enhanced common opponents
        try:
            common_analysis = analyze_common_opponents_enhanced(team1_name, team2_name)
            if common_analysis['has_common'] and common_analysis['games_count'] >= 2:
                common_adj = common_analysis['advantage'] * min(0.4, common_analysis['games_count'] * 0.15)  # Reduced from 0.5
                adjustments['Enhanced Common Opponents'] = round(common_adj, 1)
        except:
            common_analysis = analyze_common_opponents(team1_name, team2_name)
            if common_analysis['has_common']:
                adjustments['Common Opponents'] = round(common_analysis['advantage'] * 0.25, 1)  # Reduced from 0.3
        
        # Calculate final prediction
        total_adjustment = sum(adjustments.values())
        raw_final_margin = base_prediction + total_adjustment
        
        # ✅ NEW: Apply realistic caps based on conference matchup
        team1_conf = get_team_conference(team1_name)
        team2_conf = get_team_conference(team2_name)
        
        # Determine matchup type for capping
        p4_conferences = ['SEC', 'Big Ten', 'Big XII', 'ACC', 'Pac 12']
        team1_p4 = team1_conf in p4_conferences or team1_name == 'Notre Dame'
        team2_p4 = team2_conf in p4_conferences or team2_name == 'Notre Dame'
        
        # Set realistic caps
        if team1_p4 and team2_p4:
            max_spread = 21  # P4 vs P4
        elif team1_p4 or team2_p4:
            max_spread = 28  # P4 vs G5
        else:
            max_spread = 24  # G5 vs G5
        
        # Apply cap
        final_margin = max(-max_spread, min(max_spread, raw_final_margin))
        
        # Additional dampening for anything over 14 points
        if abs(final_margin) > 14:
            sign = 1 if final_margin > 0 else -1
            excess = abs(final_margin) - 14
            dampened_excess = excess * 0.7  # Reduce large spreads by 30%
            final_margin = sign * (14 + dampened_excess)
        
        # Enhanced confidence calculation
        confidence_factors = calculate_ultra_enhanced_confidence(
            team1_enhanced, team2_enhanced, adjustments
        )
        
        # Enhanced win probability
        win_prob = calculate_ultra_enhanced_win_probability(final_margin, confidence_factors)
        
        return {
            'base_margin': round(base_prediction, 1),
            'adjustments': adjustments,
            'final_margin': round(final_margin, 1),
            'win_probability': round(win_prob, 1),
            'winner': team1_name if final_margin > 0 else team2_name,
            'confidence': confidence_factors['level'],
            'confidence_score': confidence_factors['score'],
            'enhanced_breakdown': {
                'team1_enhanced': team1_enhanced,
                'team2_enhanced': team2_enhanced
            },
            'prediction_methodology': 'Ultra-Enhanced Analysis with Realistic Caps'
        }
        
    except Exception as e:
        print(f"Enhanced prediction failed: {e}")
        return predict_matchup_basic_fallback(team1_name, team2_name, location)

def calculate_enhanced_location_advantage(team1_name, team2_name, location):
    """Enhanced location advantage using team-specific home field multipliers"""
    if location == 'neutral':
        return 0.0
    elif location == 'team1_home':
        base_hfa = 3.0
        team1_multiplier = STRONG_HOME_FIELD_TEAMS.get(team1_name, 1.0)
        return base_hfa * team1_multiplier
    elif location == 'team2_home':
        base_hfa = 3.0
        team2_multiplier = STRONG_HOME_FIELD_TEAMS.get(team2_name, 1.0)
        return -base_hfa * team2_multiplier
    return 0.0

def calculate_ultra_enhanced_confidence(team1_enhanced, team2_enhanced, adjustments):
    """Ultra-enhanced confidence calculation using all modules"""
    confidence_score = 0.0
    
    # Sample size confidence
    min_games = min(team1_enhanced['basic_stats']['total_games'], 
                   team2_enhanced['basic_stats']['total_games'])
    if min_games >= 10:
        confidence_score += 0.4
    elif min_games >= 8:
        confidence_score += 0.3
    elif min_games >= 6:
        confidence_score += 0.2
    else:
        confidence_score += 0.1
    
    # Prediction margin confidence
    total_adjustment = sum(adjustments.values()) if adjustments else 0
    if abs(total_adjustment) > 10:
        confidence_score += 0.3
    elif abs(total_adjustment) > 5:
        confidence_score += 0.2
    else:
        confidence_score += 0.1
    
    # Consistency confidence
    avg_consistency = (team1_enhanced['components']['consistency_factor'] + 
                      team2_enhanced['components']['consistency_factor']) / 2
    if avg_consistency > 0.2:
        confidence_score += 0.15
    elif avg_consistency > -0.2:
        confidence_score += 0.1
    
    # Determine confidence level
    if confidence_score >= 0.8:
        level = 'Very High'
    elif confidence_score >= 0.6:
        level = 'High'
    elif confidence_score >= 0.4:
        level = 'Medium'
    else:
        level = 'Low'
    
    return {
        'score': round(confidence_score, 2),
        'level': level
    }

def calculate_ultra_enhanced_win_probability(margin, confidence_metrics):
    """Ultra-enhanced win probability with confidence weighting"""
    # Base probability from margin
    base_prob = 50 + (margin * 2.0)
    
    # Confidence adjustment
    confidence_adj = (confidence_metrics['score'] - 0.5) * 8
    
    # Margin significance adjustment
    if abs(margin) > 14:
        significance_adj = 5
    elif abs(margin) > 7:
        significance_adj = 2
    else:
        significance_adj = 0
    
    final_prob = base_prob + confidence_adj + significance_adj
    
    return max(5, min(95, final_prob))

def predict_matchup_basic_fallback(team1_name, team2_name, location):
    """Basic fallback prediction if enhanced version fails"""
    try:
        team1_stats = calculate_comprehensive_stats(team1_name)
        team2_stats = calculate_comprehensive_stats(team2_name)
        
        strength_diff = team1_stats['adjusted_total'] - team2_stats['adjusted_total']
        base_prediction = strength_diff * 2.0
        
        # Simple location adjustment
        if location == 'team1_home':
            base_prediction += 3.0
        elif location == 'team2_home':
            base_prediction -= 3.0
        
        win_prob = 50 + (base_prediction * 2.5)
        win_prob = max(5, min(95, win_prob))
        
        return {
            'base_margin': round(base_prediction, 1),
            'adjustments': {'Basic Analysis': 0},
            'final_margin': round(base_prediction, 1),
            'win_probability': round(win_prob, 1),
            'winner': team1_name if base_prediction > 0 else team2_name,
            'confidence': 'Low',
            'confidence_score': 0.3,
            'prediction_methodology': 'Basic Fallback Analysis'
        }
    except:
        return {
            'base_margin': 0,
            'adjustments': {},
            'final_margin': 0,
            'win_probability': 50,
            'winner': 'Unknown',
            'confidence': 'Very Low',
            'confidence_score': 0.1,
            'prediction_methodology': 'Error Fallback'
        }


def analyze_common_opponents_enhanced(team1_name, team2_name):
    """Enhanced common opponent analysis with recency weighting"""
    team1_record = TeamStats.query.filter_by(team_name=team1_name).first()  # 
    team2_record = TeamStats.query.filter_by(team_name=team2_name).first()  # 
    
    if not team1_record or not team2_record:  # 
        return {'has_common': False, 'advantage': 0, 'games_count': 0}  # 
    
    team1_games = team1_record.to_dict()['games']  # 
    team2_games = team2_record.to_dict()['games']  # 
    
    # Find common opponents
    team1_opponents = {game['opponent'] for game in team1_games}
    team2_opponents = {game['opponent'] for game in team2_games}
    common_opponents = team1_opponents.intersection(team2_opponents)
    
    if not common_opponents:
        return {'has_common': False, 'advantage': 0, 'games_count': 0}
    
    comparisons = []
    total_advantage = 0
    weighted_advantage = 0
    total_weight = 0
    
    for opponent in common_opponents:
        # Find most recent games against this opponent
        team1_games_vs = [g for g in team1_games if g['opponent'] == opponent]
        team2_games_vs = [g for g in team2_games if g['opponent'] == opponent]
        
        if team1_games_vs and team2_games_vs:
            team1_game = team1_games_vs[-1]  # Most recent
            team2_game = team2_games_vs[-1]  # Most recent
            
            # Calculate opponent quality for weighting
            opponent_quality = get_current_opponent_quality(opponent)
            
            # Calculate performance differential
            team1_diff = team1_game['team_score'] - team1_game['opp_score']
            team2_diff = team2_game['team_score'] - team2_game['opp_score']
            advantage = team1_diff - team2_diff
            
            # Weight by opponent quality (better opponents matter more)
            weight = max(0.5, opponent_quality / 10.0)
            
            weighted_advantage += advantage * weight
            total_weight += weight
            total_advantage += advantage
            
            comparisons.append({
                'opponent': opponent,
                'team1_diff': team1_diff,
                'team2_diff': team2_diff,
                'advantage': advantage,
                'weight': weight,
                'opponent_quality': opponent_quality
            })
    
    avg_advantage = weighted_advantage / total_weight if total_weight > 0 else 0
    
    return {
        'has_common': True,
        'advantage': round(avg_advantage, 1),
        'games_count': len(comparisons),
        'comparisons': comparisons,
        'raw_advantage': round(total_advantage / len(comparisons), 1) if comparisons else 0
    }

def analyze_victory_quality_differential(team1_name, team2_name):
    """Compare the quality of victories between two teams"""
    team1_victory_value, team1_details = calculate_total_victory_value(team1_name)
    team2_victory_value, team2_details = calculate_total_victory_value(team2_name)
    
    # Get games count for normalization
    team1_wins = len(team1_details)
    team2_wins = len(team2_details)
    
    if team1_wins == 0 and team2_wins == 0:
        return {'significant': False, 'adjustment': 0}
    
    # Calculate per-win victory value
    team1_avg_victory = team1_victory_value / max(1, team1_wins)
    team2_avg_victory = team2_victory_value / max(1, team2_wins)
    
    victory_diff = team1_avg_victory - team2_avg_victory
    
    # Only significant if difference is meaningful
    if abs(victory_diff) < 0.8:
        return {'significant': False, 'adjustment': 0}
    
    # Scale the adjustment (cap at reasonable range)
    adjustment = max(-3.0, min(3.0, victory_diff * 1.5))
    
    return {
        'significant': True,
        'adjustment': round(adjustment, 1),
        'team1_avg_victory': round(team1_avg_victory, 2),
        'team2_avg_victory': round(team2_avg_victory, 2)
    }

def calculate_enhanced_recent_form(team_name, games_back=4):
    """Calculate enhanced recent form with momentum scoring"""
    team_record = TeamStats.query.filter_by(team_name=team_name).first()  # 
    if not team_record:  # 
        return {'momentum_score': 0, 'trend': 'insufficient_data'}  # 
    
    games = team_record.to_dict()['games']  # 
    if len(games) < 2:
        return {'momentum_score': 0, 'trend': 'insufficient_data'}
    
    recent_games = games[-games_back:] if len(games) >= games_back else games
    
    momentum_score = 0
    trend_points = []
    
    for i, game in enumerate(recent_games):
        # Recency weight (more recent games matter more)
        recency_weight = (i + 1) / len(recent_games)
        
        # Performance score for this game
        margin = game['team_score'] - game['opp_score']
        opponent_quality = get_current_opponent_quality(game['opponent'])
        
        # Expected margin based on opponent quality
        expected_margin = (5.0 - opponent_quality) * 1.8
        performance = margin - expected_margin
        
        # Weight by recency and add to momentum
        weighted_performance = performance * recency_weight
        momentum_score += weighted_performance
        trend_points.append(performance)
    
    # Determine trend
    if len(trend_points) >= 2:
        early_avg = sum(trend_points[:len(trend_points)//2]) / (len(trend_points)//2)
        late_avg = sum(trend_points[len(trend_points)//2:]) / (len(trend_points) - len(trend_points)//2)
        
        if late_avg > early_avg + 5:
            trend = 'improving'
        elif late_avg < early_avg - 5:
            trend = 'declining'
        else:
            trend = 'stable'
    else:
        trend = 'stable'
    
    return {
        'momentum_score': round(momentum_score / len(recent_games), 1),
        'trend': trend,
        'recent_performance': trend_points
    }

def calculate_conference_matchup_adjustment(team1_name, team2_name):
    """More nuanced conference matchup adjustments"""
    team1_conf = get_team_conference(team1_name)
    team2_conf = get_team_conference(team2_name)
    
    # P4 vs G5 adjustments based on actual performance differential
    if team1_conf in P4_CONFERENCES and team2_conf in G5_CONFERENCES:
        # P4 teams should have some advantage, but not as much if G5 team is strong
        team2_scientific = calculate_scientific_ranking(team2_name)
        base_adj = 2.5
        
        # Reduce advantage if G5 team has high victory value
        if team2_scientific['components']['adjusted_victory_value'] > 25:
            base_adj = 1.5  # Strong G5 team
        elif team2_scientific['components']['adjusted_victory_value'] > 35:
            base_adj = 0.8  # Elite G5 team
        
        return base_adj
        
    elif team2_conf in P4_CONFERENCES and team1_conf in G5_CONFERENCES:
        # Mirror the above logic
        team1_scientific = calculate_scientific_ranking(team1_name)
        base_adj = -2.5
        
        if team1_scientific['components']['adjusted_victory_value'] > 25:
            base_adj = -1.5
        elif team1_scientific['components']['adjusted_victory_value'] > 35:
            base_adj = -0.8
        
        return base_adj
    
    return 0  # Same level conferences

def analyze_schedule_strength_differential(team1_name, team2_name):
    """Analyze difference in schedule difficulty"""
    team1_record = TeamStats.query.filter_by(team_name=team1_name).first()  # 
    team2_record = TeamStats.query.filter_by(team_name=team2_name).first()  # 
    
    if not team1_record or not team2_record:  # 
        return 0  # 
    
    team1_games = team1_record.to_dict()['games']  # 
    team2_games = team2_record.to_dict()['games']  # 
    
    if not team1_games or not team2_games:
        return 0
    
    # Calculate average opponent quality
    team1_opp_quality = sum(get_current_opponent_quality(g['opponent']) for g in team1_games) / len(team1_games)
    team2_opp_quality = sum(get_current_opponent_quality(g['opponent']) for g in team2_games) / len(team2_games)
    
    quality_diff = team1_opp_quality - team2_opp_quality
    
    # Convert to point adjustment (stronger schedule = slight edge)
    adjustment = quality_diff * 0.8
    return max(-2.0, min(2.0, adjustment))

def calculate_enhanced_home_field_advantage(team1_name, team2_name, location):
    """Enhanced home field advantage based on team-specific performance"""
    if location == 'neutral':
        return 0
    
    base_hfa = 3.0  # Standard home field advantage
    
    if location == 'team1_home':
        # Check team1's home performance
        home_performance = analyze_home_performance(team1_name)
        hfa_modifier = home_performance['advantage_modifier']
        return round(base_hfa * hfa_modifier, 1)
    
    elif location == 'team2_home':
        # Check team2's home performance  
        home_performance = analyze_home_performance(team2_name)
        hfa_modifier = home_performance['advantage_modifier']
        return round(-base_hfa * hfa_modifier, 1)
    
    return 0

def analyze_home_performance(team_name):
    """Analyze how much a team benefits from playing at home"""
    team_record = TeamStats.query.filter_by(team_name=team_name).first()  # 
    if not team_record:  # 
        return {'advantage_modifier': 1.0}  # 
    
    games = team_record.to_dict()['games']  # 
    
    home_games = [g for g in games if g['home_away'] == 'Home']
    away_games = [g for g in games if g['home_away'] == 'Away']
    
    if len(home_games) < 2 or len(away_games) < 2:
        return {'advantage_modifier': 1.0}  # Default
    
    # Calculate average margin at home vs away
    home_margins = [g['team_score'] - g['opp_score'] for g in home_games]
    away_margins = [g['team_score'] - g['opp_score'] for g in away_games]
    
    home_avg = sum(home_margins) / len(home_margins)
    away_avg = sum(away_margins) / len(away_margins)
    
    home_advantage = home_avg - away_avg
    
    # Convert to modifier (1.0 = normal, >1.0 = strong home field, <1.0 = weak home field)
    if home_advantage > 8:
        modifier = 1.3  # Strong home field
    elif home_advantage > 4:
        modifier = 1.1  # Slight home field advantage
    elif home_advantage < -4:
        modifier = 0.8  # Actually worse at home
    else:
        modifier = 1.0  # Normal
    
    return {'advantage_modifier': modifier}

def calculate_prediction_confidence(team1_name, team2_name, final_margin, adjustments):
    """Calculate confidence in the prediction"""
    confidence_factors = []
    
    # 1. Sample size (more games = more confidence)
    team1_games = len(team_stats[team1_name]['games'])
    team2_games = len(team_stats[team2_name]['games'])
    min_games = min(team1_games, team2_games)
    
    if min_games >= 8:
        confidence_factors.append(0.3)
    elif min_games >= 5:
        confidence_factors.append(0.2)
    else:
        confidence_factors.append(0.1)
    
    # 2. Margin size (bigger margins = more confidence)
    if abs(final_margin) > 14:
        confidence_factors.append(0.3)
    elif abs(final_margin) > 7:
        confidence_factors.append(0.2)
    else:
        confidence_factors.append(0.1)
    
    # 3. Common opponents (more shared opponents = more confidence)
    common_analysis = analyze_common_opponents_enhanced(team1_name, team2_name)
    if common_analysis['games_count'] >= 3:
        confidence_factors.append(0.2)
    elif common_analysis['games_count'] >= 1:
        confidence_factors.append(0.1)
    
    # 4. Consistency of adjustments (if all point same way = more confidence)
    positive_adj = sum(1 for adj in adjustments.values() if adj > 0.5)
    negative_adj = sum(1 for adj in adjustments.values() if adj < -0.5)
    
    if len(adjustments) > 0:
        consistency = max(positive_adj, negative_adj) / len(adjustments)
        confidence_factors.append(consistency * 0.2)
    
    total_confidence = sum(confidence_factors)
    
    if total_confidence >= 0.7:
        level = 'High'
    elif total_confidence >= 0.4:
        level = 'Medium'
    else:
        level = 'Low'
    
    return {
        'score': round(total_confidence, 2),
        'level': level,
        'factors': confidence_factors
    }

def calculate_enhanced_win_probability(margin, confidence_metrics):
    """Enhanced win probability calculation"""
    # Base probability from margin
    base_prob = 50 + (margin * 2.2)  # Slightly less aggressive than before
    
    # Adjust based on confidence
    confidence_adjustment = (confidence_metrics['score'] - 0.5) * 5
    
    final_prob = base_prob + confidence_adjustment
    
    # Cap between 5-95%
    return max(5, min(95, final_prob))

def identify_key_prediction_factors(adjustments, team1_scientific, team2_scientific):
    """Identify the most important factors in the prediction"""
    factors = []
    
    # Largest adjustments
    sorted_adj = sorted(adjustments.items(), key=lambda x: abs(x[1]), reverse=True)
    for factor, value in sorted_adj[:3]:  # Top 3 adjustments
        if abs(value) > 0.5:
            factors.append(f"{factor}: {value:+.1f}")
    
    # Scientific ranking components
    team1_components = team1_scientific['components']
    team2_components = team2_scientific['components']
    
    victory_diff = team1_components['adjusted_victory_value'] - team2_components['adjusted_victory_value']
    if abs(victory_diff) > 5:
        factors.append(f"Victory Quality Edge: {victory_diff:+.1f}")
    
    return factors[:4]  # Return top 4 factors
# Add this near the top with other global variables
scheduled_games = []

def parse_schedule_text(schedule_text, week, team_clarifications=None):
    """Parse pasted schedule text into structured game data with dates, times, TV, and bowl detection"""
    games = []
    unknown_teams = set()
    lines = [line.strip() for line in schedule_text.split('\n') if line.strip()]
    
    current_date = None
    current_year = datetime.now().year
    current_bowl_game = None  # NEW: Track bowl game from previous lines
    
    def resolve_team_name(team_name):
        """Resolve team name using clarifications or existing mappings"""
        original_name = team_name
        team_name = clean_team_name(team_name)

        # First check if we have a clarification for this session
        if team_clarifications and team_name in team_clarifications:
            
            return team_clarifications[team_name]
        
        # Check if it's a known FBS team
        if team_name in TEAMS:
            return team_name
        
        # Check common variations
        for standard_name, variants in TEAM_VARIATIONS.items():
            if team_name in variants:
                
                return standard_name
        
        # If we get here, it's unknown
        
        unknown_teams.add(team_name)
        return team_name  # Return as-is for now
    
    def parse_date_line(line):
        """Try to parse a date from a line"""
        import re
        
        # Remove common words
        line_clean = re.sub(r'\b(matchup|time|tv|mobile|tickets)\b', '', line, flags=re.IGNORECASE).strip()
        
        # Pattern 1: "Saturday, August 23" or "Saturday, August 23, 2025"
        match = re.search(r'(\w+day),?\s+(\w+)\s+(\d{1,2})(?:,?\s+(\d{4}))?', line_clean, re.IGNORECASE)
        if match:
            day_name, month_name, day_num, year = match.groups()
            year = int(year) if year else current_year
            
            # Convert month name to number
            months = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 
                'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            
            month_num = months.get(month_name.lower())
            if month_num:
                try:
                    return datetime(year, month_num, int(day_num)).strftime('%Y-%m-%d')
                except:
                    pass
        
        # Pattern 2: "8/23" or "8/23/25" or "8/23/2025"
        match = re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', line_clean)
        if match:
            month, day, year = match.groups()
            if year:
                year = int(year)
                if year < 100:  # 2-digit year
                    year += 2000
            else:
                year = current_year
            
            try:
                return datetime(year, int(month), int(day)).strftime('%Y-%m-%d')
            except:
                pass
        
        return None
    
    def detect_bowl_game_line(line):
        """Detect if a line contains just a bowl game name"""
        line_lower = line.lower().strip()
        
        # Check if this line is just a bowl name (no teams)
        # Use word boundaries to avoid matching "at" in "Raton", etc.
        import re
        has_vs = bool(re.search(r'\bvs\b', line_lower))
        has_at = bool(re.search(r'\bat\b', line_lower))
        has_atsign = '@' in line_lower
        
        if 'bowl' in line_lower and not (has_vs or has_at or has_atsign):
            # This might be a bowl name line
            # Clean up common prefixes/suffixes
            cleaned = line.strip()
            
            # Remove common words that appear with bowl names
            cleaned = re.sub(r'\b(game|championship|presented by|sponsored by)\b', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            
            if 'bowl' in cleaned.lower():
                return cleaned
        
        return None

    def detect_cfp_designation(line):
        """Detect CFP designation lines like 'CFP Semifinal', 'CFP Quarterfinal'"""
        line_lower = line.lower().strip()
        
        # Remove hyphens for more flexible matching
        line_normalized = line_lower.replace('-', ' ')
        
        cfp_designations = [
            'cfp semifinal',
            'cfp quarterfinal', 
            'cfp championship',
            'cfp national championship',
            'cfp first round',
            'cfp first round game',  # Add this
            'national championship'
        ]
        
        for designation in cfp_designations:
            if designation in line_normalized:
                # Return cleaned version
                return line.strip()
        
        return None

    
    def extract_time_and_tv(line):
        """Extract time and TV info from game line"""
        import re
        
        time_match = None
        tv_info = None
        
        # Extract time (12:00pm, 6:30pm, etc.)
        time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)'
        time_search = re.search(time_pattern, line)

        if time_search:
            hour, minute, period = time_search.groups()
            minute = minute or '00'
            time_match = f"{hour}:{minute} {period.upper()}"
        
        # Extract TV networks
        tv_networks = [
            'Big Ten Network', 'SEC Network', 'ACC Network', 'Amazon Prime', 'YouTube TV', 'Apple TV+',
            'Paramount+', 'ESPNEWS', 'ESPN+', 'ESPN2', 'ESPNU', 'CBSSN', 'Sling TV', 'ESPN',
            'FOX', 'CBS', 'NBC', 'ABC', 'FS1', 'FS2', 'BTN', 'SECN', 'ACCN', 'Peacock', 'Netflix', 'Hulu'
        ]
        
        tv_networks_sorted = sorted(tv_networks, key=len, reverse=True)
        line_upper = line.upper()
        
        for network in tv_networks_sorted:
            network_upper = network.upper()
            if network_upper in line_upper:
                tv_info = network
                break
        
        return time_match, tv_info
    
    for i, line in enumerate(lines):
        try:
            # Skip empty or very short lines
            line_lower = line.lower().strip()
            if len(line_lower) < 3:
                continue
            
            # Skip obvious header/table content
            skip_phrases = [
                'matchup time', 'time (et)', 'tv/mobile', 'tickets', 'buy tickets',
                'matchup', 'tv/mobile tickets', 'time (et) tv', 'network', 'channel', 
                'broadcast', 'status', '(et)', 'mobile tickets', 'location'
            ]
            
            if any(phrase in line_lower for phrase in skip_phrases):
                print(f"SKIPPING: {line}")
                continue
            
            # Try to parse as date header first
            parsed_date = parse_date_line(line)
            if parsed_date:
                current_date = parsed_date
                current_bowl_game = None  # Reset bowl game on new date
                continue
            
            # NEW: Check if this line is a bowl game name
            bowl_name = detect_bowl_game_line(line)
            if bowl_name:
                current_bowl_game = bowl_name
                continue

            # NEW: Check if this line is a CFP designation
            cfp_designation = detect_cfp_designation(line)
            print(f"DEBUG CFP: Testing '{line}' -> Result: {cfp_designation}")
            if cfp_designation:
                if current_bowl_game:
                    # Append to existing bowl game (e.g., "Peach Bowl (CFP Semifinal)")
                    current_bowl_game = f"{current_bowl_game} ({cfp_designation})"
                    print(f"DEBUG CFP: Appended to bowl, now: {current_bowl_game}")
                else:
                    # No bowl game, so this IS the game name (e.g., "CFP First Round")
                    current_bowl_game = cfp_designation
                    print(f"DEBUG CFP: Set as game name: {current_bowl_game}")
                continue

            
            game = None
            
            # Look ahead to next line for time/TV info
            next_line = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                import re
                if re.search(r'\d{1,2}:?\d{2}?\s*(am|pm|AM|PM)', next_line) or any(net in next_line.upper() for net in ['ESPN', 'FOX', 'CBS', 'NBC']):
                    
                    combined_line = f"{line} {next_line}"
                    game_time, tv_network = extract_time_and_tv(combined_line)
                else:
                    game_time, tv_network = extract_time_and_tv(line)
            else:
                game_time, tv_network = extract_time_and_tv(line)
            
        
            
            # Clean the line for team parsing (remove time/TV info and venue info)
            import re
            line_clean = re.sub(r'\d{1,2}:?\d{2}?\s*(am|pm|AM|PM)', '', line)
            line_clean = re.sub(r'\b(ESPN|FOX|CBS|NBC|ABC|FS1|FS2|BTN|SECN|ACCN|ESPN2|ESPNU|CBSSN|Paramount\+|Peacock|ESPNEWS)\b', '', line_clean, flags=re.IGNORECASE)

            # NEW: Remove venue information (words like "Stadium", "Arena", "Center", etc.)
            line_clean = re.sub(r'\b(Stadium|Arena|Center|Field|Dome|Coliseum|Memorial|Municipal|County|High|School|Complex|Park|Facility)\b.*$', '', line_clean, flags=re.IGNORECASE)

            # NEW: Split on tabs and take only the first part (team matchup)
            if '\t' in line_clean:
                line_clean = line_clean.split('\t')[0].strip()

            line_clean = re.sub(r'\s+', ' ', line_clean).strip()

            
            
            # Format 1: "Team A vs Team B (in City, ST)" - neutral site with location
            if (' vs ' in line_clean or ' vs. ' in line_clean) and '(in ' in line_clean.lower():
                parts = line_clean.split(' vs ')
                teams_part = line_clean.split('(')[0].strip()
                location = line_clean.split('(')[1].split(')')[0].strip()
                team1, team2 = [t.strip() for t in teams_part.split(' vs ')]
                
                team1_resolved = resolve_team_name(team1)
                team2_resolved = resolve_team_name(team2)
                
                game = {
                    'week': week,
                    'home_team': team1_resolved,
                    'away_team': team2_resolved,
                    'neutral': True,
                    'completed': False,
                    'location_note': location,
                    'original_home': team1,
                    'original_away': team2,
                    'game_date': current_date,
                    'game_time': game_time,
                    'tv_network': tv_network,
                    'bowl_game_name': current_bowl_game  # NEW: Use tracked bowl game
                }
            
            # Format 2: "Team A at Team B" - Team B is home
            elif ' at ' in line_clean:
                away_team, home_team = [t.strip() for t in line_clean.split(' at ')]
                
                home_resolved = resolve_team_name(home_team)
                away_resolved = resolve_team_name(away_team)
                
                game = {
                    'week': week,
                    'home_team': home_resolved,
                    'away_team': away_resolved,
                    'neutral': False,
                    'completed': False,
                    'original_home': home_team,
                    'original_away': away_team,
                    'game_date': current_date,
                    'game_time': game_time,
                    'tv_network': tv_network,
                    'bowl_game_name': current_bowl_game  # NEW: Use tracked bowl game
                }
            
            # Format 3: "Team A vs Team B" - Check if it's a bowl game (neutral) or regular game (Team A home)
            elif ' vs ' in line_clean or ' vs. ' in line_clean:
                split_parts = line_clean.split(' vs ')
                if len(split_parts) < 2:
                    # Try splitting on ' vs. ' instead
                    split_parts = line_clean.split(' vs. ')

                if len(split_parts) >= 2:
                    team1, team2 = [t.strip() for t in split_parts]
                else:
                    continue
                
                team1_resolved = resolve_team_name(team1)
                team2_resolved = resolve_team_name(team2)
                
                # NEW: If we have a bowl game name, this is automatically a neutral site game
                if current_bowl_game:
                    is_neutral = True
                    location_note = None
                    
                else:
                    is_neutral = False
                    location_note = None
                
                game = {
                    'week': week,
                    'home_team': team1_resolved,
                    'away_team': team2_resolved,
                    'neutral': is_neutral,  # ✅ MAKE SURE THIS USES is_neutral VARIABLE
                    'completed': False,
                    'location_note': location_note,
                    'original_home': team1,
                    'original_away': team2,
                    'game_date': current_date,
                    'game_time': game_time,
                    'tv_network': tv_network,
                    'bowl_game_name': current_bowl_game
                }
                
            
            if game:
                games.append(game)
                
        except Exception as e:
            print(f"Error parsing line '{line}': {e}")
            continue
    
    return games, list(unknown_teams)

def normalize_team_name(team_name):
    """Normalize team names for matching"""
    # Handle common variations
    variations = {
        'Western Kentucky': ['WKU', 'Western Kentucky'],
        'Miami': ['Miami', 'Miami (FL)', 'Miami Florida'],
        'FCS': ['FCS', 'Idaho State']  # Map specific FCS teams to generic FCS
    }
    
    for standard_name, variants in variations.items():
        if team_name in variants:
            return standard_name
    
    return team_name

def find_matching_scheduled_game(home_team, away_team, week):
    """Find a scheduled game that matches the completed game"""
    home_normalized = normalize_team_name(home_team)
    away_normalized = normalize_team_name(away_team)
    
    for i, scheduled in enumerate(scheduled_games):
        if scheduled['week'] != week or scheduled['completed']:
            continue
            
        sched_home = normalize_team_name(scheduled['home_team'])
        sched_away = normalize_team_name(scheduled['away_team'])
        
        # Check both orientations (home/away might be swapped)
        if ((sched_home == home_normalized and sched_away == away_normalized) or
            (sched_home == away_normalized and sched_away == home_normalized)):
            return i
    
    return None

def update_team_stats_in_db(team, opponent, team_score, opp_score, is_home, is_neutral_site, is_overtime):
    """Update team statistics in database after a game"""
    
    # Special case: Don't update stats for FCS placeholder team
    if team == 'FCS' or team.upper() == 'FCS':
        return
    
    try:
        # Get existing team stats or create new record
        team_stats = TeamStats.query.filter_by(team_name=team).first()
        if not team_stats:
            team_stats = TeamStats(team_name=team)
            db.session.add(team_stats)
            # Flush to get the ID and ensure defaults are applied
            db.session.flush()
        
        # SAFETY: Ensure all fields have integer values (not None)
        if team_stats.wins is None:
            team_stats.wins = 0
        if team_stats.losses is None:
            team_stats.losses = 0
        if team_stats.points_for is None:
            team_stats.points_for = 0
        if team_stats.points_against is None:
            team_stats.points_against = 0
        if team_stats.home_wins is None:
            team_stats.home_wins = 0
        if team_stats.road_wins is None:
            team_stats.road_wins = 0
        if team_stats.margin_of_victory_total is None:
            team_stats.margin_of_victory_total = 0
        if team_stats.games_json is None:
            team_stats.games_json = '[]'
        
        # Determine win/loss and update stats
        if team_score > opp_score:
            team_stats.wins += 1
            # Add margin of victory (only for wins)
            team_stats.margin_of_victory_total += (team_score - opp_score)
            
            # Track home/road wins (only if NOT neutral site)
            if not is_neutral_site:
                if is_home:
                    team_stats.home_wins += 1
                else:
                    team_stats.road_wins += 1
        else:
            team_stats.losses += 1
        
        # Update points
        team_stats.points_for += team_score
        team_stats.points_against += opp_score
        
        # Determine game location for display
        if is_neutral_site:
            location = 'Neutral'
        elif is_home:
            location = 'Home'
        else:
            location = 'Away'
        
        # Add game to history
        games_list = team_stats.games  # This uses the @property from models.py
        games_list.append({
            'opponent': opponent,
            'team_score': team_score,
            'opp_score': opp_score,
            'result': 'W' if team_score > opp_score else 'L',
            'home_away': location,
            'overtime': is_overtime
        })
        team_stats.games = games_list  # This triggers the JSON serialization
        
        # Save to database
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating team stats for {team}: {e}")
        raise e

def get_current_week_from_snapshots():
    """
    Determine the current week based on the most recent weekly snapshot.
    Logic: If you snapshot Week N, then Week N+1 becomes current.
    """
    try:
        # Get the most recent snapshot
        latest_snapshot = WeeklySnapshot.query.order_by(WeeklySnapshot.snapshot_date.desc()).first()
        
        if not latest_snapshot:
            return '1'  # Default to Week 1 if no snapshots exist
        
        week_name = latest_snapshot.week_name  # e.g., "Week 5"
        
        # Handle standard week format: "Week N"
        if week_name.startswith('Week '):
            try:
                week_num = int(week_name.split(' ')[1])
                next_week = week_num + 1
                
                # Handle season progression
                if next_week <= 15:  # Regular season goes to Week 15
                    return str(next_week)
                elif next_week == 16:  # After Week 15 comes Bowls
                    return 'Bowls'
                else:  # After Week 16+ would be CFP
                    return 'CFP'
                    
            except (ValueError, IndexError):
                print(f"Could not parse week number from: {week_name}")
                return '1'  # Fallback to Week 1
        
        # Handle special week transitions
        elif week_name == 'Bowls':
            return 'CFP'  # After Bowls comes CFP
        elif week_name == 'CFP':
            return 'CFP'  # Stay on CFP (season is over)
        
        # Handle other formats - try to extract number
        else:
            import re
            numbers = re.findall(r'\d+', week_name)
            if numbers:
                try:
                    week_num = int(numbers[0])
                    return str(week_num + 1)
                except:
                    pass
        
        # Ultimate fallback
        return '1'
        
    except Exception as e:
        print(f"Error determining current week from snapshots: {e}")
        return '1'  # Safe fallback



def complete_schedule_import_db(games, week):
    """Complete the schedule import to database"""
    try:
        # Check if there are existing scheduled games for this week
        existing_games = ScheduledGame.query.filter_by(week=week, completed=False).count()
        
        if existing_games > 0:
            flash(f'ℹ️ Adding {len(games)} more games to Week {week} (you already had {existing_games} scheduled games)', 'info')
        
        # Add new scheduled games to database
        games_added = 0
        for game_data in games:
            try:
                scheduled_game = ScheduledGame(
                    week=game_data['week'],
                    home_team=game_data['home_team'],
                    away_team=game_data['away_team'],
                    neutral=game_data.get('neutral', False),
                    completed=game_data.get('completed', False),
                    game_date=datetime.strptime(game_data['game_date'], '%Y-%m-%d').date() if game_data.get('game_date') else None,
                    game_time=game_data.get('game_time'),
                    tv_network=game_data.get('tv_network'),
                    location_note=game_data.get('location_note'),
                    original_home=game_data.get('original_home'),
                    original_away=game_data.get('original_away'),
                    bowl_game_name=game_data.get('bowl_game_name')
                )
                db.session.add(scheduled_game)
                games_added += 1
            except Exception as e:
                print(f"Error adding scheduled game {game_data}: {e}")
                continue
        
        # Save to database
        db.session.commit()
        
        total_scheduled = ScheduledGame.query.filter_by(week=week, completed=False).count()
        flash(f'✅ Successfully imported {games_added} games for Week {week}! (Total scheduled: {total_scheduled})', 'success')
        return redirect(url_for('scoreboard', week=week))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error completing import: {e}', 'error')
        return redirect(url_for('scoreboard', week=week))


@app.route('/compare')
def team_compare():
    """Team comparison page"""
    return render_template('team_compare.html', conferences=CONFERENCES)

@app.route('/team_bowl_status/<team_name>')
def team_bowl_status_detail(team_name):
    """Show detailed bowl eligibility breakdown"""
    status = get_team_bowl_status(team_name)
    if not status:
        return "Team not found"
    
    return render_template_string("""
    <div class="card">
        <div class="card-header">{{ team_name }} Bowl Eligibility</div>
        <div class="card-body">
            <p><strong>Record:</strong> {{ status.total_wins }}-{{ status.losses }}</p>
            <p><strong>Real Wins:</strong> {{ status.real_wins }} (FCS wins don't count)</p>
            {% if status.fcs_wins > 0 %}
                <p><strong>FCS Wins:</strong> {{ status.fcs_wins }} (not counted for bowl eligibility)</p>
            {% endif %}
            
            {% if status.bowl_eligible %}
                <div class="alert alert-success">✅ Bowl Eligible</div>
            {% else %}
                <div class="alert alert-warning">
                    ❌ Not Bowl Eligible<br>
                    Needs {{ status.wins_needed }} more wins against FBS opponents
                </div>
            {% endif %}
        </div>
    </div>
    """, team_name=team_name, status=status)    


@app.route('/weekly_results')
@app.route('/weekly_results/<week>')
def weekly_results_redirect(week=None):
    """Redirect old URLs to new scoreboard"""
    if week:
        return redirect(url_for('scoreboard', week=week), code=301)
    return redirect(url_for('scoreboard'), code=301)


# Add this route to fix the NULL scores issue
@app.route('/fix_null_scores')
@login_required
def fix_null_scores():
    """Fix completed scheduled games that have NULL final scores"""
    try:
        # Get database connection
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Find completed scheduled games with NULL scores
        cursor.execute("""
            SELECT s.id, s.week, s.home_team, s.away_team, s.final_home_score, s.final_away_score,
                   g.home_score, g.away_score, g.overtime as game_overtime
            FROM scheduled_games s
            LEFT JOIN games g ON (
                s.week = g.week AND 
                ((s.home_team = g.home_team AND s.away_team = g.away_team) OR
                 (s.home_team = g.away_team AND s.away_team = g.home_team))
            )
            WHERE s.completed = true 
            AND (s.final_home_score IS NULL OR s.final_away_score IS NULL)
            AND g.home_score IS NOT NULL;
        """)
        
        games_to_fix = cursor.fetchall()
        
        fixed_count = 0
        results = []
        
        for game in games_to_fix:
            sched_id, week, sched_home, sched_away, final_home, final_away, game_home_score, game_away_score, game_ot = game
            
            # Determine correct scores based on team orientation
            if sched_home == sched_home:  # Same orientation
                correct_home_score = game_home_score
                correct_away_score = game_away_score
            else:  # Flipped orientation
                correct_home_score = game_away_score
                correct_away_score = game_home_score
            
            # Update the scheduled game with correct final scores
            cursor.execute("""
                UPDATE scheduled_games 
                SET final_home_score = %s, final_away_score = %s, overtime = %s
                WHERE id = %s;
            """, (correct_home_score, correct_away_score, game_ot, sched_id))
            
            results.append(f"Fixed: {sched_home} {correct_home_score}-{correct_away_score} {sched_away}")
            fixed_count += 1
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return f"""
        <h1>Fix NULL Scores Complete!</h1>
        
        <h2>Fixed {fixed_count} games:</h2>
        <ul>
        {''.join(f'<li>{result}</li>' for result in results)}
        </ul>
        
        <p>Now check your weekly results page to see if scores show correctly!</p>
        <p><a href="/weekly_results">Check Weekly Results</a> | <a href="/admin">Back to Admin</a></p>
        """
        
    except Exception as e:
        return f"<h1>Error</h1><p>{e}</p>"

# Replace your compare_teams route with this simpler debug version first

@app.route('/compare_teams', methods=['POST'])
def compare_teams():
    """Debug version of team comparison"""
    try:
        team1 = request.form['team1']
        team2 = request.form['team2']
        location = request.form.get('location', 'neutral')
                
        if team1 == team2:
            flash('Please select two different teams!', 'error')
            return redirect(url_for('team_compare'))
        
        # Check if teams exist
        team1_record = TeamStats.query.filter_by(team_name=team1).first()  # 
        if not team1_record:  # 
            flash(f'{team1} not found in database!', 'error')
            return redirect(url_for('team_compare'))
        
        team2_record = TeamStats.query.filter_by(team_name=team2).first()  # 
        if not team2_record:  # 
            flash(f'{team2} not found in database!', 'error') 
            return redirect(url_for('team_compare'))
        
        # Check if teams have played games
        team1_games = len(team1_record.to_dict()['games'])  # 
        team2_games = len(team2_record.to_dict()['games'])  # 
        
        
        if team1_games == 0:
            flash(f'{team1} has not played any games yet! Please add some games first.', 'error')
            return redirect(url_for('team_compare'))
            
        if team2_games == 0:
            flash(f'{team2} has not played any games yet! Please add some games first.', 'error')
            return redirect(url_for('team_compare'))
        
        # Get basic stats (using your existing functions)
        
        team1_stats = calculate_comprehensive_stats(team1)
        team2_stats = calculate_comprehensive_stats(team2)
        
        
        team1_scientific = calculate_enhanced_scientific_ranking(team1) 
        team2_scientific = calculate_enhanced_scientific_ranking(team2)  
        
        
        # Use your ORIGINAL prediction function for now
        prediction = predict_matchup_ultra_enhanced(team1, team2, location)
        
        
        # Use your existing analysis functions
        common_opponents = analyze_common_opponents(team1, team2)
        team1_form = calculate_recent_form(team1)
        team2_form = calculate_recent_form(team2)
        style_matchup = analyze_style_matchup(team1, team2)
        h2h_history = head_to_head_history(team1, team2)
        
        
        comparison_data = {
            'team1': team1,
            'team2': team2,
            'team1_stats': team1_stats,
            'team2_stats': team2_stats,
            'team1_scientific': team1_scientific,
            'team2_scientific': team2_scientific,
            'prediction': prediction,
            'common_opponents': common_opponents,
            'team1_form': team1_form,
            'team2_form': team2_form,
            'style_matchup': style_matchup,
            'h2h_history': h2h_history,
            'location': location
        }
        
        
        # Use your existing template for now
        return render_template('comparison_results.html', **comparison_data)
        
    except Exception as e:
        print(f"ERROR in compare_teams: {e}")
        flash(f'Error comparing teams: {str(e)}', 'error')
        return redirect(url_for('team_compare'))



# Also add this simple team preview route
@app.route('/team_preview/<team_name>')
def team_preview(team_name):
    """Simple team preview for comparison page"""
    try:
        team_record = TeamStats.query.filter_by(team_name=team_name).first()
        if not team_record:
            return {'error': 'Team not found'}, 404
        
        basic_stats = team_record.to_dict()
        
        # Check if team has played games
        if basic_stats['wins'] + basic_stats['losses'] == 0:
            return {'error': 'No games played'}, 404
        
        stats = calculate_comprehensive_stats(team_name)
        
        # Get enhanced recent form
        enhanced_form = calculate_enhanced_recent_form(team_name)
        
        # Convert enhanced form to old structure for compatibility
        if enhanced_form['trend'] == 'improving':
            trending = 'up'
        elif enhanced_form['trend'] == 'declining':
            trending = 'down'
        else:
            trending = 'stable'
        
        # Calculate simple recent record (last 4 games)
        total_games = len(basic_stats['games'])
        if total_games >= 4:
            recent_games = basic_stats['games'][-4:]
        else:
            recent_games = basic_stats['games']
        
        recent_wins = sum(1 for g in recent_games if g['result'] == 'W')
        recent_record = f"{recent_wins}-{len(recent_games) - recent_wins}"
        
        # Get current rank (simplified)
        current_rank = "NR"  # You can enhance this later
        
        preview_data = {
            'team': team_name,
            'rank': current_rank,
            'record': f"{basic_stats['wins']}-{basic_stats['losses']}",
            'conference': get_team_conference(team_name),
            'adjusted_total': round(stats['adjusted_total'], 1),
            'recent_form': recent_record,  # ✅ Now provides the expected 'record' format
            'trending': trending,  # ✅ Now provides the expected 'trending' format
            'logo_url': get_team_logo_url(team_name)
        }
        
        return preview_data
        
    except Exception as e:
        print(f"ERROR in team_preview: {e}")
        return {'error': str(e)}, 500


@app.route('/ranking_methodology')
def ranking_methodology():
    """Explain how the scientific ranking system works"""
    return render_template('ranking_methodology.html')

@app.route('/manage_rivalries')
@login_required
def manage_rivalries():
    """Admin page to view and manage rivalries"""
    return render_template_string("""
    <html>
    <head><title>Manage Rivalries</title></head>
    <body style="font-family: Arial; margin: 40px;">
        <h1>Rivalry Management</h1>
        
        <h2>Current Rivalries</h2>
        <div style="columns: 3; column-gap: 30px;">
        {% for team, rivals in rivalries.items() %}
            <div style="break-inside: avoid; margin-bottom: 15px;">
                <strong>{{ team }}:</strong><br>
                {% for rival in rivals %}
                    <span style="margin-left: 10px;">• {{ rival }}</span>
                    {% if is_rivalry_tier_1(team, rival) %}
                        <span style="color: red; font-weight: bold;">(Tier 1)</span>
                    {% endif %}
                    <br>
                {% endfor %}
            </div>
        {% endfor %}
        </div>
        
        <h2>Recent Rivalry Games</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr style="background: #f0f0f0;">
                <th style="border: 1px solid #ddd; padding: 8px;">Team</th>
                <th style="border: 1px solid #ddd; padding: 8px;">vs</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Result</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Bonus</th>
            </tr>
            {% for game in recent_rivalry_games %}
            <tr>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.team }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.opponent }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.result }} {{ game.score }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">+{{ game.bonus }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <p><a href="/admin">Back to Admin</a></p>
    </body>
    </html>
    """, 
    rivalries=RIVALRIES, 
    recent_rivalry_games=get_recent_rivalry_games(),
    is_rivalry_tier_1=lambda t1, t2: get_rivalry_bonus(t1, t2) >= 1.0)

def get_recent_rivalry_games():
    """Get recent rivalry games for display"""
    rivalry_games = []
    
    all_games = get_games_data()  # 
    for game in all_games[-20:]:  #   # Last 20 games
        home_team = game['home_team']
        away_team = game['away_team']
        
        if is_rivalry_game(home_team, away_team):
            # Home team perspective
            home_bonus = get_rivalry_bonus(home_team, away_team)
            if game['home_score'] > game['away_score']:
                rivalry_games.append({
                    'team': home_team,
                    'opponent': away_team,
                    'result': 'W',
                    'score': f"{game['home_score']}-{game['away_score']}",
                    'bonus': home_bonus
                })
            else:
                # Away team won
                away_bonus = get_rivalry_bonus(away_team, home_team)
                rivalry_games.append({
                    'team': away_team,
                    'opponent': home_team,
                    'result': 'W',
                    'score': f"{game['away_score']}-{game['home_score']}",
                    'bonus': away_bonus
                })
    
    return rivalry_games

def clean_team_name(team_name):
    """Clean team name by removing ranking numbers and extra formatting"""
    import re
    
    if not team_name:
        return team_name
    
    # Remove common ranking patterns
    patterns_to_remove = [
        r'^\d+\.\s*',           # "1. Alabama"
        r'^\d+\s+',             # "1 Alabama" 
        r'\s+\d+$',             # "Alabama 1"
        r'^\(\d+\)\s*',         # "(1) Alabama"
        r'\s*\(\d+\)$',         # "Alabama (1)"
        r'^#\d+\s+',            # "#1 Alabama"
        r'\s+#\d+$',            # "Alabama #1"
        r'^\d+\)\s*',           # "1) Alabama"
        r'^\d+-\s*',            # "1- Alabama"
    ]
    
    cleaned_name = team_name.strip()
    
    for pattern in patterns_to_remove:
        cleaned_name = re.sub(pattern, '', cleaned_name).strip()
    
    return cleaned_name


def clean_scraped_team_name(raw_name):
    """Clean and standardize scraped team names"""
    if not raw_name:
        return None
    
    # Clean the name first
    cleaned = raw_name.strip()
    
    # PRIORITY 1: Handle specific problematic cases FIRST
    specific_fixes = {
        'Tennessee Volunteers': 'Tennessee',
        'South Carolina Gamecocks': 'South Carolina', 
        'SMU Mustangs': 'SMU',
        'Texas Longhorns': 'Texas',
        'Georgia Bulldogs': 'Georgia',
        'Alabama Crimson Tide': 'Alabama',
        'Ohio State Buckeyes': 'Ohio State',
        'Penn State Nittany Lions': 'Penn State',
        'Notre Dame Fighting Irish': 'Notre Dame',
        'USC Trojans': 'USC',
        'UCLA Bruins': 'UCLA',
        'Stanford Cardinal': 'Stanford',
        'Florida State Seminoles': 'Florida State',
        'Miami Hurricanes': 'Miami',
        'Clemson Tigers': 'Clemson',
        'North Carolina Tar Heels': 'North Carolina',
        'NC State Wolfpack': 'NC State',
        'Virginia Tech Hokies': 'Virginia Tech',
        'Texas A&M Aggies': 'Texas A&M',
        'LSU Tigers': 'LSU',
        'Ole Miss Rebels': 'Ole Miss',
        'Mississippi State Bulldogs': 'Mississippi State',
        'Arkansas Razorbacks': 'Arkansas',
        'Missouri Tigers': 'Missouri',
        'Kentucky Wildcats': 'Kentucky',
        'Vanderbilt Commodores': 'Vanderbilt',
        'Florida Gators': 'Florida',
        'Auburn Tigers': 'Auburn',
        'Michigan Wolverines': 'Michigan',
        'Michigan State Spartans': 'Michigan State',
        'Wisconsin Badgers': 'Wisconsin',
        'Iowa Hawkeyes': 'Iowa',
        'Minnesota Golden Gophers': 'Minnesota',
        'Illinois Fighting Illini': 'Illinois',
        'Northwestern Wildcats': 'Northwestern',
        'Indiana Hoosiers': 'Indiana',
        'Purdue Boilermakers': 'Purdue',
        'Maryland Terrapins': 'Maryland',
        'Rutgers Scarlet Knights': 'Rutgers',
        'Nebraska Cornhuskers': 'Nebraska',
        'Oregon Ducks': 'Oregon',
        'Washington Huskies': 'Washington',
        'Oklahoma Sooners': 'Oklahoma',
        'Oklahoma State Cowboys': 'Oklahoma State',
        'Texas Tech Red Raiders': 'Texas Tech',
        'Baylor Bears': 'Baylor',
        'TCU Horned Frogs': 'TCU',
        'Kansas Jayhawks': 'Kansas',
        'Kansas State Wildcats': 'Kansas State',
        'Iowa State Cyclones': 'Iowa State',
        'West Virginia Mountaineers': 'West Virginia',
        'Cincinnati Bearcats': 'Cincinnati',
        'Houston Cougars': 'Houston',
        'UCF Knights': 'UCF',
        'BYU Cougars': 'BYU',
        'Colorado Buffaloes': 'Colorado',
        'Utah Utes': 'Utah',
        'Arizona Wildcats': 'Arizona',
        'Arizona State Sun Devils': 'Arizona State'
    }
    
    # Check specific fixes first
    if cleaned in specific_fixes:
        return specific_fixes[cleaned]
    
    # PRIORITY 2: Remove common mascot suffixes
    mascot_suffixes = [
        'Volunteers', 'Gamecocks', 'Mustangs', 'Crimson Tide', 'Bulldogs', 'Tigers', 
        'Buckeyes', 'Nittany Lions', 'Longhorns', 'Aggies', 'Sooners', 'Cowboys', 
        'Wolverines', 'Spartans', 'Fighting Irish', 'Trojans', 'Bruins', 'Cardinal', 
        'Bears', 'Wildcats', 'Eagles', 'Panthers', 'Hurricanes', 'Seminoles', 
        'Blue Devils', 'Tar Heels', 'Wolfpack', 'Hokies', 'Cavaliers', 'Yellow Jackets',
        'Demon Deacons', 'Orange', 'Red Raiders', 'Horned Frogs', 'Jayhawks',
        'Cyclones', 'Mountaineers', 'Boilermakers', 'Hoosiers', 'Hawkeyes',
        'Golden Gophers', 'Badgers', 'Cornhuskers', 'Scarlet Knights',
        'Terrapins', 'Ducks', 'Beavers', 'Huskies', 'Cougars', 'Sun Devils',
        'Utes', 'Buffaloes', 'Golden Bears', 'Rainbow Warriors', 'Aztecs',
        'Broncos', 'Rams', 'Wolf Pack', 'Rebels', 'Lobos', 'Razorbacks',
        'Commodores', 'Gators', 'Fighting Illini', 'Bearcats', 'Knights'
    ]
    
    # Remove mascot suffixes (case-insensitive)
    for suffix in mascot_suffixes:
        if cleaned.lower().endswith(f' {suffix.lower()}'):
            cleaned = cleaned[:-len(f' {suffix}')].strip()
            break
    
    # PRIORITY 3: Handle specific ESPN variations
    espn_mappings = {
        'Mississippi': 'Ole Miss',
        'Louisiana State': 'LSU',
        'Texas Christian': 'TCU',
        'Southern California': 'USC',
        'Central Florida': 'UCF',
        'Southern Methodist': 'SMU',
        'Brigham Young': 'BYU',
        'Florida International': 'Florida Intl',
        'Louisiana Monroe': 'UL Monroe',
        'Miami (Ohio)': 'Miami (OH)',
        'Appalachian State': 'Appalachian St',
        'New Mexico State': 'New Mexico St',
        'Sam Houston State': 'Sam Houston',
        'North Carolina State': 'NC State'
    }
    
    if cleaned in espn_mappings:
        return espn_mappings[cleaned]
    
    # PRIORITY 4: Apply your existing TEAM_VARIATIONS logic
    for standard_name, variants in TEAM_VARIATIONS.items():
        if cleaned in variants:
            return standard_name
    
    return cleaned


@app.route('/create_snapshot', methods=['POST'])
@login_required
def create_snapshot():
    try:
        week_name = request.form.get('week_name', '').strip()
        if not week_name:
            flash('Please enter a week name (e.g., "Week 5", "Week 10")!', 'error')
            return redirect(url_for('admin'))
        
        # Check if snapshot already exists for this week
        existing_snapshot = WeeklySnapshot.query.filter_by(week_name=week_name).first()
        if existing_snapshot:
            flash(f'Snapshot for "{week_name}" already exists! Delete it first if you want to recreate.', 'warning')
            return redirect(url_for('admin'))
        
        # Get current rankings (top 50 to catch movement in/out of top 25)
        comprehensive_stats = get_all_team_stats_bulk()
        
        # Prepare rankings data for storage
        rankings_data = []
        for rank, team_data in enumerate(comprehensive_stats[:50], 1):  # Top 50
            rankings_data.append({
                'rank': rank,
                'team': team_data['team'],
                'conference': team_data['conference'],
                'adjusted_total': round(team_data['adjusted_total'], 3),
                'record': f"{team_data['total_wins']}-{team_data['total_losses']}",
                'total_wins': team_data['total_wins'],
                'total_losses': team_data['total_losses']
            })
        
        # Create and save snapshot
        snapshot = WeeklySnapshot(
            week_name=week_name,
            rankings_json=json.dumps(rankings_data)
        )
        
        db.session.add(snapshot)
        db.session.commit()
        
        flash(f'✅ Weekly snapshot "{week_name}" created successfully! ({len(rankings_data)} teams saved)', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating snapshot: {e}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/weekly_movement')
def weekly_movement():
    """Show week-to-week ranking movements"""
    try:
        # Get all snapshots ordered by date (most recent first)
        snapshots = WeeklySnapshot.query.order_by(WeeklySnapshot.snapshot_date.desc()).all()
        
        if len(snapshots) < 2:
            flash('Need at least 2 weekly snapshots to show movement!', 'info')
            return render_template('weekly_movement.html', 
                                 movement_data=[], 
                                 current_week=None, 
                                 previous_week=None,
                                 snapshots=[s.to_dict() for s in snapshots])

        # ✅ FIX: Compare the two most recent snapshots instead of current vs snapshot
        current_snapshot = snapshots[0]    # Most recent (Week 2)
        previous_snapshot = snapshots[1]   # Second most recent (Week 1)
        
        current_rankings = current_snapshot.rankings[:25]   # Week 2 top 25
        previous_rankings = previous_snapshot.rankings[:25] # Week 1 top 25
        
        # Calculate movement
        movement_data = calculate_ranking_movement(current_rankings, previous_rankings)
        
        return render_template('weekly_movement.html',
                             movement_data=movement_data,
                             current_week=current_snapshot.week_name,    # Week 2
                             previous_week=previous_snapshot.week_name,  # Week 1
                             snapshots=[s.to_dict() for s in snapshots])
        
    except Exception as e:
        flash(f'Error loading movement data: {e}', 'error')
        print(f"ERROR in weekly_movement: {e}")
        return render_template('weekly_movement.html', 
                             movement_data=[], 
                             current_week=None, 
                             previous_week=None,
                             snapshots=[])

# Route to compare specific weeks
@app.route('/compare_weeks/<int:current_id>/<int:previous_id>')
def compare_weeks(current_id, previous_id):
    """Compare two specific weekly snapshots"""
    try:
        current_snapshot = WeeklySnapshot.query.get_or_404(current_id)
        previous_snapshot = WeeklySnapshot.query.get_or_404(previous_id)
        
        current_rankings = current_snapshot.rankings[:25]
        previous_rankings = previous_snapshot.rankings[:25]
        
        movement_data = calculate_ranking_movement(current_rankings, previous_rankings)
        
        # Get all snapshots for dropdown
        all_snapshots = WeeklySnapshot.query.order_by(WeeklySnapshot.snapshot_date.desc()).all()
        
        return render_template('weekly_movement.html',
                             movement_data=movement_data,
                             current_week=current_snapshot.week_name,
                             previous_week=previous_snapshot.week_name,
                             snapshots=[s.to_dict() for s in all_snapshots],
                             current_snapshot_id=current_id,
                             previous_snapshot_id=previous_id)
        
    except Exception as e:
        flash(f'Error comparing weeks: {e}', 'error')
        return redirect(url_for('weekly_movement'))

# Route to delete a snapshot
@app.route('/delete_snapshot/<int:snapshot_id>', methods=['POST'])
@login_required
def delete_snapshot(snapshot_id):
    """Delete a weekly snapshot"""
    try:
        snapshot = WeeklySnapshot.query.get_or_404(snapshot_id)
        week_name = snapshot.week_name
        
        db.session.delete(snapshot)
        db.session.commit()
        
        flash(f'✅ Deleted snapshot "{week_name}"', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting snapshot: {e}', 'error')
    
    return redirect(url_for('weekly_movement'))

def calculate_ranking_movement(current_rankings, previous_rankings):
    """Calculate movement between two sets of rankings"""
    movement_data = []
    
    # Create lookup dictionaries
    current_lookup = {team['team']: i + 1 for i, team in enumerate(current_rankings)}
    previous_lookup = {team['team']: i + 1 for i, team in enumerate(previous_rankings)}
    
    # Process current top 25
    for current_rank, team_data in enumerate(current_rankings, 1):
        team_name = team_data['team']
        
        if team_name in previous_lookup:
            # Team was ranked before
            previous_rank = previous_lookup[team_name]
            movement = previous_rank - current_rank  # Positive = moved up
            
            if movement > 0:
                movement_text = f'<span class="movement-arrow-up">▲</span>{movement}'
                movement_class = "rank-up"
            elif movement < 0:
                movement_text = f'<span class="movement-arrow-down">▼</span>{abs(movement)}'
                movement_class = "rank-down"
            else:
                movement_text = "—"
                movement_class = "rank-same"
        else:
            # New to rankings
            movement_text = "NEW!"
            movement_class = "rank-new"
        
        # Create record string from wins/losses (handle both formats)
        if 'record' in team_data:
            record = team_data['record']
        else:
            # Build record from total_wins and total_losses
            wins = team_data.get('total_wins', 0)
            losses = team_data.get('total_losses', 0)
            record = f"{wins}-{losses}"
        
        movement_data.append({
            'current_rank': current_rank,
            'team': team_name,
            'conference': team_data['conference'],
            'record': record,
            'adjusted_total': team_data['adjusted_total'],
            'movement_text': movement_text,
            'movement_class': movement_class,
            'previous_rank': previous_lookup.get(team_name, None)
        })
    
    return movement_data

@app.route('/admin')
@login_required
def admin():
    # NEW: Fast bulk loading instead of individual team calculations
    comprehensive_stats = get_all_team_stats_bulk()
    
    # Keep the existing template variables your admin.html expects
    recent_games = get_games_data()[-10:]
    all_games = get_games_data()
    
    # NEW: Add current week information
    week_info = get_current_week_info()
    
    return render_template('admin.html', 
                         comprehensive_stats=comprehensive_stats, 
                         recent_games=recent_games,
                         games_data=all_games,
                         historical_rankings=[],
                         get_current_week_info=get_current_week_info)



@app.route('/admin/clear_cache', methods=['POST'])
@login_required
def clear_cache_route():
    """Clear cache via route"""
    try:
        clear_cache()
        flash('✅ Cache cleared successfully!', 'success')
    except Exception as e:
        flash(f'Error clearing cache: {e}', 'error')
    
    return redirect(url_for('cache_management'))



@app.route('/cfp_bracket')
def cfp_bracket():
    """CFP bracket with correct automatic qualifiers"""
    cache_key = 'cfp_bracket_correct_data'
    
    # Check cache first (3 minute cache)
    if cache_key in performance_cache:
        cached_bracket, timestamp = performance_cache[cache_key]
        if time.time() - timestamp < 180:
            return render_template('cfp_bracket.html', bracket=cached_bracket)
    
    try:
        # Use the corrected CFP bracket generation
        bracket = generate_correct_cfp_bracket()  # ← Use new function
        
        # Cache the result
        performance_cache[cache_key] = (bracket, time.time())
        
        return render_template('cfp_bracket.html', bracket=bracket)
        
    except Exception as e:
        return f"""
        <html><body style="font-family: Arial; margin: 40px;">
        <h1>CFP Bracket Temporarily Unavailable</h1>
        <p><strong>Error:</strong> {e}</p>
        <p><a href="/">Back to Home</a></p>
        </body></html>
        """


def generate_correct_cfp_bracket():
    """Generate 12-team CFP bracket with correct automatic qualifier logic"""
    try:
        # Get all teams ranked by adjusted total
        all_teams_stats = get_all_team_stats_bulk()
        
        # Step 1: Find the champion of each conference
        conference_champions = {}
        conferences_to_check = ['SEC', 'Big Ten', 'ACC', 'Big XII', 'American', 'Conference USA', 'MAC', 'Mountain West', 'Sun Belt']
        
        for conf_name in conferences_to_check:
            # Find highest-ranked team from this conference
            conf_teams = [team for team in all_teams_stats if team['conference'] == conf_name]
            if conf_teams:
                champion = conf_teams[0]  # Highest ranked team from conference
                champion['champion_of'] = conf_name
                conference_champions[conf_name] = champion
        
        # Step 2: Rank all conference champions by their overall ranking
        all_champions = list(conference_champions.values())
        all_champions.sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        # Step 3: Top 5 conference champions get automatic qualifiers
        automatic_qualifiers = all_champions[:5]
        for i, champion in enumerate(automatic_qualifiers):
            champion['auto_qualifier_rank'] = i + 1
            champion['is_auto_qualifier'] = True
            champion['auto_qualifier_title'] = f"{champion['champion_of']} Champion"
        
        # Step 4: Get top 12 overall teams for the playoff
        playoff_teams = all_teams_stats[:12]
        
        # Step 5: Ensure all 5 auto-qualifiers are in the playoff
        auto_qualifier_names = {aq['team'] for aq in automatic_qualifiers}
        
        # Remove any auto-qualifiers already in top 12
        non_auto_in_top12 = [team for team in playoff_teams if team['team'] not in auto_qualifier_names]
        
        # Start with auto-qualifiers, then fill with highest at-large teams
        final_playoff_teams = automatic_qualifiers.copy()
        spots_remaining = 12 - len(automatic_qualifiers)
        
        # Add best at-large teams
        for team in non_auto_in_top12[:spots_remaining]:
            team['is_auto_qualifier'] = False
            final_playoff_teams.append(team)
        
        # Sort final teams by ranking and assign seeds
        final_playoff_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
        for i, team in enumerate(final_playoff_teams):
            team['seed'] = i + 1
        
        # Create bracket structure
        first_round_byes = final_playoff_teams[:4]  # Seeds 1-4
        at_large_display = final_playoff_teams[4:]   # Seeds 5-12
        
        # First round games: 5v12, 6v11, 7v10, 8v9
        first_round_games = []
        if len(final_playoff_teams) >= 12:
            first_round_games = [
                {'higher_seed': final_playoff_teams[4], 'lower_seed': final_playoff_teams[11], 'game_num': 1},
                {'higher_seed': final_playoff_teams[5], 'lower_seed': final_playoff_teams[10], 'game_num': 2},
                {'higher_seed': final_playoff_teams[6], 'lower_seed': final_playoff_teams[9], 'game_num': 3},
                {'higher_seed': final_playoff_teams[7], 'lower_seed': final_playoff_teams[8], 'game_num': 4},
            ]
        
        return {
            'first_round_byes': first_round_byes,
            'first_round_games': first_round_games,
            'all_teams': final_playoff_teams,
            'automatic_qualifiers': automatic_qualifiers,
            'at_large_display': at_large_display,
            'conference_champions': conference_champions
        }
        
    except Exception as e:
        print(f"Error in CFP bracket generation: {e}")
        return {
            'first_round_byes': [],
            'first_round_games': [],
            'all_teams': [],
            'automatic_qualifiers': [],
            'at_large_display': [],
            'conference_champions': {}
        }

def generate_fast_cfp_bracket(all_teams_stats):
    """Fast CFP bracket generation using pre-calculated stats"""
    try:
        # Get top 12 teams (already sorted by adjusted_total)
        top_12 = all_teams_stats[:12] if len(all_teams_stats) >= 12 else all_teams_stats
        
        # Add seeds
        for i, team in enumerate(top_12):
            team['seed'] = i + 1
        
        # Create bracket structure
        bracket = {
            'first_round_byes': top_12[:4],  # Seeds 1-4 get byes
            'first_round_games': create_simple_first_round_games(top_12),
            'all_teams': top_12,
            'automatic_qualifiers': top_12[:5],  # Top 5 as auto-qualifiers
            'at_large_display': top_12[5:] if len(top_12) > 5 else [],
            'conference_champions': {}  # Simplified for speed
        }
        
        return bracket
        
    except Exception as e:
        print(f"Error in fast CFP bracket: {e}")
        return {
            'first_round_byes': [],
            'first_round_games': [],
            'all_teams': [],
            'automatic_qualifiers': [],
            'at_large_display': [],
            'conference_champions': {}
        }   


def calculate_p4_g5_records(team_name, games):
    """Calculate P4/G5 records from games data"""
    p4_wins = 0
    p4_losses = 0
    g5_wins = 0
    g5_losses = 0
    
    for game in games:
        opponent = game['opponent']
        result = game['result']
        
        # Skip FCS games
        if opponent == 'FCS' or opponent.upper() == 'FCS':
            continue
        
        # Determine opponent type
        opponent_conf = get_team_conference(opponent)
        
        is_p4_opponent = (
            opponent_conf in P4_CONFERENCES or 
            opponent in P4_INDEPENDENT_TEAMS  # Notre Dame
        )
        
        is_g5_opponent = (
            opponent_conf in G5_CONFERENCES or 
            opponent in G5_INDEPENDENT_TEAMS  # Connecticut
        )
        
        # Count wins/losses by opponent type
        if is_p4_opponent:
            if result == 'W':
                p4_wins += 1
            else:
                p4_losses += 1
        elif is_g5_opponent:
            if result == 'W':
                g5_wins += 1
            else:
                g5_losses += 1
    
    return {
        'p4_wins': p4_wins,
        'p4_losses': p4_losses,
        'g5_wins': g5_wins,
        'g5_losses': g5_losses
    }

@app.route('/team_detail/<team_name>')
def team_detail(team_name):
    """Redirect to public team detail (for template compatibility)"""
    return redirect(url_for('public_team_detail', team_name=team_name))

@app.route('/team/<team_name>')
@time_route 
def public_team_detail(team_name):
    """Team detail page - works even for teams with no games"""
    from urllib.parse import unquote
    
    # Decode URL-encoded team name
    decoded_team_name = unquote(team_name)
    
    
    # First check if this is a valid team name
    if decoded_team_name not in TEAMS:
        flash(f'Team "{decoded_team_name}" is not a valid FBS team!', 'error')
        return redirect(url_for('public_rankings'))
    
    # Get team stats from database (might not exist)
    team_stats_record = TeamStats.query.filter_by(team_name=decoded_team_name).first()
    
    if team_stats_record:
        # Team has games - use bulk data (same as rankings page)
        basic_stats = team_stats_record.to_dict()
        has_games = (basic_stats['wins'] + basic_stats['losses']) > 0
        
        if has_games:
            try:
                # Use the SAME data source as the rankings page
                all_teams_stats = get_all_team_stats_bulk()
                
                # Find this team in the bulk data
                team_data = None
                current_rank = 'NR'
                for i, team in enumerate(all_teams_stats):
                    if team['team'] == decoded_team_name:
                        team_data = team
                        current_rank = i + 1
                        break
                
                if team_data:
                    adjusted_total = team_data['adjusted_total']
                    total_teams_ranked = len(all_teams_stats)
                    
                    # Get detailed breakdown for components
                    try:
                        enhanced_scientific = calculate_enhanced_scientific_ranking(decoded_team_name)
                        components = enhanced_scientific.get('components', {})
                    except Exception as e:
                        components = {}
                    
                    scientific_result = {
                        'total_score': adjusted_total,  # Use the same score as rankings
                        'components': components,
                        'basic_stats': {
                            'wins': basic_stats['wins'],
                            'losses': basic_stats['losses'],
                            'total_games': basic_stats['wins'] + basic_stats['losses']
                        }
                    }
                else:
                    # Fallback if not found in bulk data
                    comprehensive_stats = calculate_comprehensive_stats(decoded_team_name)
                    adjusted_total = comprehensive_stats['adjusted_total']
                    current_rank = 'NR'
                    total_teams_ranked = 0
                    
                    scientific_result = {
                        'total_score': adjusted_total,
                        'components': comprehensive_stats.get('scientific_breakdown', {}).get('components', {}),
                        'basic_stats': {
                            'wins': basic_stats['wins'],
                            'losses': basic_stats['losses'],
                            'total_games': basic_stats['wins'] + basic_stats['losses']
                        }
                    }
                    
            except Exception as e:
                print(f"Stats calculation failed for {decoded_team_name}: {e}")
                scientific_result = create_default_ranking_result()
                adjusted_total = 0.0
                current_rank = 'NR'
                total_teams_ranked = 0
        else:
            # Team exists in database but no games
            scientific_result = create_default_ranking_result()
            adjusted_total = 0.0
            current_rank = 'NR'
            total_teams_ranked = 0
    else:
        # Team not in database at all - create empty stats
        basic_stats = {
            'wins': 0,
            'losses': 0,
            'points_for': 0,
            'points_against': 0,
            'home_wins': 0,
            'road_wins': 0,
            'margin_of_victory_total': 0,
            'games': [],
            'p4_wins': 0,
            'p4_losses': 0,
            'g5_wins': 0,
            'g5_losses': 0
        }
        scientific_result = create_default_ranking_result()
        adjusted_total = 0.0
        has_games = False
        current_rank = 'NR'
        total_teams_ranked = 0
    
    # Calculate chart data directly instead of using broken function
    if basic_stats['games']:
        # Victory values and weeks
        game_weeks = []
        victory_values = []
        
        # Win breakdown by location
        home_wins = 0
        away_wins = 0
        neutral_wins = 0
        
        # Opponent quality distribution
        quality_buckets = [0, 0, 0, 0]  # weak, average, strong, elite
        
        # Victory margins
        win_opponents = []
        win_margins = []
        
        for game in basic_stats['games']:
            # Victory values (only for wins)
            if game['result'] == 'W':
                week = game.get('week', 'Unknown')
                game_weeks.append(f"Week {week}")
                
                # Calculate victory value for this win
                try:
                    value = calculate_victory_value_with_rivalry(game, decoded_team_name)
                    victory_values.append(round(value, 2))
                except:
                    victory_values.append(1.0)  # Fallback value
                
                # Count wins by location
                if game['home_away'] == 'Home':
                    home_wins += 1
                elif game['home_away'] == 'Away':
                    away_wins += 1
                elif game['home_away'] == 'Neutral':
                    neutral_wins += 1
                
                # Victory margins
                win_opponents.append(game['opponent'])
                win_margins.append(game['team_score'] - game['opp_score'])
            
            # Opponent quality distribution (all games)
            try:
                opponent_quality = get_current_opponent_quality(game['opponent'])
                if opponent_quality <= 3:
                    quality_buckets[0] += 1  # Weak
                elif opponent_quality <= 6:
                    quality_buckets[1] += 1  # Average
                elif opponent_quality <= 8:
                    quality_buckets[2] += 1  # Strong
                else:
                    quality_buckets[3] += 1  # Elite
            except:
                quality_buckets[1] += 1  # Default to average if error
        
        # Calculate team stats
        total_wins = len([g for g in basic_stats['games'] if g['result'] == 'W'])
        avg_victory_value = sum(victory_values) / max(1, len(victory_values))
        avg_win_margin = sum(win_margins) / max(1, len(win_margins))
        
        chart_data = {
            'game_weeks': game_weeks,
            'victory_values': victory_values,
            'home_wins': home_wins,
            'away_wins': away_wins,
            'neutral_wins': neutral_wins,
            'total_losses': basic_stats['losses'],
            'opponent_quality_distribution': quality_buckets,
            'win_opponents': win_opponents,
            'win_margins': win_margins,
            'recent_games': basic_stats['games'][-5:] if len(basic_stats['games']) >= 5 else basic_stats['games'],
            'team_stats': {
                'avg_victory_value': avg_victory_value,
                'avg_margin': avg_win_margin,
                'strongest_win': {'opponent': win_opponents[0] if win_opponents else 'None', 'value': max(victory_values) if victory_values else 0},
                'avg_opp_quality': 5.0
            }
        }
    else:
        # No games - use empty data
        chart_data = create_empty_chart_data()
    
    # Prepare opponent details
    opponent_details = []
    for game in basic_stats['games']:
        try:
            opponent_quality = get_current_opponent_quality(game['opponent'])
            is_rival = is_rivalry_game(decoded_team_name, game['opponent'])
            rivalry_bonus = get_rivalry_bonus(decoded_team_name, game['opponent']) if is_rival else 0
        except:
            opponent_quality = 5.0
            is_rival = False
            rivalry_bonus = 0
        
        opponent_details.append({
            'opponent': game['opponent'],
            'opponent_quality': round(opponent_quality, 1),
            'result': game['result'],
            'team_score': game['team_score'],
            'opp_score': game['opp_score'],
            'margin': game['team_score'] - game['opp_score'],
            'location': game['home_away'],
            'is_rivalry': is_rival,
            'rivalry_bonus': rivalry_bonus,
            'overtime': game.get('overtime', False)
        })
    
    # Calculate P4/G5 records
    p4_g5_records = calculate_p4_g5_records(decoded_team_name, basic_stats['games'])
    
    # Add P4/G5 records to basic_stats
    enhanced_stats = basic_stats.copy()
    enhanced_stats.update(p4_g5_records)
    
    # Template data
    template_data = {
        'team_name': decoded_team_name,
        'conference': get_team_conference(decoded_team_name),
        'current_rank': current_rank,
        'record': f"{basic_stats['wins']}-{basic_stats['losses']}",
        'scientific_result': scientific_result,
        'opponent_details': opponent_details,
        'total_teams_ranked': total_teams_ranked,
        'has_games': len(basic_stats['games']) > 0,
        
        # Chart data
        'game_weeks': chart_data['game_weeks'],
        'victory_values': chart_data['victory_values'],
        'home_wins': chart_data['home_wins'],
        'away_wins': chart_data['away_wins'],
        'neutral_wins': chart_data['neutral_wins'],
        'total_losses': chart_data['total_losses'],
        'opponent_quality_distribution': chart_data['opponent_quality_distribution'],
        'win_opponents': chart_data['win_opponents'],
        'win_margins': chart_data['win_margins'],
        'recent_games': chart_data['recent_games'],
        'team_stats': chart_data['team_stats'],
        
        'stats': enhanced_stats,
        'adjusted_total': adjusted_total
    }
    
    return render_template('public_team_detail.html', **template_data)

def create_empty_chart_data():
    """Create empty chart data for teams with no games"""
    return {
        'game_weeks': [],
        'victory_values': [],
        'home_wins': 0,
        'away_wins': 0,
        'neutral_wins': 0,
        'total_losses': 0,
        'opponent_quality_distribution': [0, 0, 0, 0],
        'win_opponents': [],
        'win_margins': [],
        'recent_games': [],
        'team_stats': {
            'avg_victory_value': 0,
            'avg_margin': 0,
            'strongest_win': {'opponent': 'None', 'value': 0},
            'avg_opp_quality': 5.0
        }
    }


@app.route('/')
def home():
    """Redirect to public landing page"""
    return redirect(url_for('public_landing'))

@app.route('/public')
def public_landing():
    """Public landing page with Top 25 preview"""
    # Get top 25 teams for preview
    comprehensive_stats = get_all_team_stats_bulk()
    top_25 = comprehensive_stats[:25]  # Get top 25 teams
    
    return render_template('public_landing.html', top_25=top_25)

@app.route('/rankings')
@app.route('/rankings/<conference>')
@time_route
def rankings(conference=None):
    """Main rankings page with comprehensive team statistics and conference filtering"""
    
    # Get all team stats
    comprehensive_stats = get_all_team_stats_bulk()
    
    # Apply conference filter if specified
    if conference and conference != 'all':
        # Decode URL-encoded conference name (handles spaces, etc.)
        from urllib.parse import unquote
        decoded_conference = unquote(conference)
        
        # Validate conference exists
        if decoded_conference in CONFERENCES:
            comprehensive_stats = [team for team in comprehensive_stats 
                                 if team['conference'] == decoded_conference]
            selected_conference = decoded_conference
        else:
            flash(f'Conference "{decoded_conference}" not found. Showing all teams.', 'warning')
            selected_conference = 'All Conferences'
    else:
        selected_conference = 'All Conferences'
    
    # Get recent games
    recent_games = get_games_data()[-10:]
    
    # Create conference list for dropdown (sorted)
    conference_list = sorted(CONFERENCES.keys())
    
    return render_template('rankings.html', 
                         comprehensive_stats=comprehensive_stats, 
                         recent_games=recent_games,
                         CFB_GEN_AI_ENABLED=CFB_GEN_AI_ENABLED,
                         selected_conference=selected_conference,
                         conference_list=conference_list,
                         total_teams=len(comprehensive_stats))


def prepare_team_chart_data(team_name):
    """Prepare data for team detail page visualizations"""
    team_record = TeamStats.query.filter_by(team_name=team_name).first()
    if not team_record:
        return None
    
    team_stats = team_record.to_dict()
    games = team_stats['games']
    
    # ... existing victory value code stays the same ...
    
    # 2. Win/Loss Breakdown - FIXED to include neutral site wins
    home_wins = 0
    away_wins = 0
    neutral_wins = 0
    total_losses = team_stats['losses']
    
    # Count wins by location
    for game in games:
        if game['result'] == 'W':
            if game['home_away'] == 'Home':
                home_wins += 1
            elif game['home_away'] == 'Away':
                away_wins += 1
            elif game['home_away'] == 'Neutral':
                neutral_wins += 1
    
    # ... rest of function stays the same ...
    
    return {
        'game_weeks': game_weeks,
        'victory_values': victory_values,
        'home_wins': home_wins,        # ✅ Now calculated from games
        'away_wins': away_wins,        # ✅ Now calculated from games  
        'neutral_wins': neutral_wins,  # ✅ NEW: Neutral site wins
        'total_losses': total_losses,
        'opponent_quality_distribution': quality_buckets,
        'win_opponents': win_opponents,
        'win_margins': win_margins,
        'recent_games': recent_games,
        'team_stats': {
            'avg_victory_value': avg_victory_value,
            'avg_margin': avg_win_margin,
            'strongest_win': strongest_win,
            'avg_opp_quality': avg_opp_quality
        }
    }


@app.route('/import_schedule', methods=['POST'])
@login_required
def import_schedule():
    """Import schedule from pasted text - DATABASE VERSION"""
    try:
        schedule_text = request.form.get('schedule_text', '').strip()
        week = request.form.get('week', '')
        
        if not schedule_text or not week:
            flash('Please provide both schedule text and week!', 'error')
            return redirect(url_for('scoreboard', week=week))
        
        # Parse the schedule text (your existing function should work)
        result = parse_schedule_text(schedule_text, week)
        
        try:
            games, unknown_teams = result
        except Exception as e:
            flash(f'Error parsing schedule: {e}', 'error')
            return redirect(url_for('scoreboard', week=week))
        
        if not games:
            flash('No games could be parsed from the text. Please check the format.', 'error')
            return redirect(url_for('scoreboard', week=week))
        
        # If we have unknown teams, go to clarification
        if unknown_teams:
            session['pending_schedule'] = {
                'schedule_text': schedule_text,
                'week': week,
                'unknown_teams': unknown_teams
            }
            return redirect(url_for('clarify_teams'))
        
        # No unknown teams - save to database
        return complete_schedule_import_db(games, week)
        
    except Exception as e:
        flash(f'Error importing schedule: {e}', 'error')
        return redirect(url_for('scoreboard', week=week))

def complete_schedule_import(games, week):
    """Complete the schedule import after clarifications - DATABASE VERSION"""
    return complete_schedule_import_db(games, week)


@app.route('/clarify_teams')
@login_required
def clarify_teams():
    """Show team clarification page"""
    pending = session.get('pending_schedule')
    if not pending:
        flash('No pending schedule to clarify!', 'error')
        return redirect(url_for('weekly_results'))
    
    unknown_teams = pending['unknown_teams']
    team_suggestions = {}
    team_contexts = {}
    
    # Parse the schedule to get game contexts
    lines = [line.strip() for line in pending['schedule_text'].split('\n') if line.strip()]
    
    # Find which games each unknown team appears in
    for unknown_team in unknown_teams:
        team_contexts[unknown_team] = []
        for line in lines:
            if unknown_team.lower() in line.lower() and any(indicator in line.lower() for indicator in ['vs', 'at', '@']):
                team_contexts[unknown_team].append(line.strip())
    
    # Get suggestions for each unknown team
    for team in unknown_teams:
        team_suggestions[team] = get_team_suggestions(team)
    
    return render_template('clarify_teams.html', 
                         unknown_teams=unknown_teams,
                         team_suggestions=team_suggestions,
                         team_contexts=team_contexts,
                         week=pending['week'])

@app.route('/process_clarifications', methods=['POST'])
@login_required
def process_clarifications():
    """Process team clarifications and complete import"""
    try:
        pending = session.get('pending_schedule')
        if not pending:
            flash('No pending schedule to process!', 'error')
            return redirect(url_for('weekly_results'))
        
        # Get clarifications from form
        clarifications = {}
        for unknown_team in pending['unknown_teams']:
            clarification_type = request.form.get(f'type_{unknown_team}')
            
            if clarification_type == 'fcs':
                clarifications[unknown_team] = 'FCS'
            elif clarification_type == 'map':
                mapped_team = request.form.get(f'map_{unknown_team}')
                if mapped_team and mapped_team in TEAMS:
                    clarifications[unknown_team] = mapped_team
                else:
                    flash(f'Invalid mapping for {unknown_team}', 'error')
                    return redirect(url_for('clarify_teams'))
            elif clarification_type == 'custom':
                custom_name = request.form.get(f'custom_{unknown_team}', '').strip()
                if custom_name:
                    clarifications[unknown_team] = custom_name
                else:
                    flash(f'Please provide a custom name for {unknown_team}', 'error')
                    return redirect(url_for('clarify_teams'))
        
        # Save mappings for future use (keeping in session only)
        # Team mappings are temporary for schedule import session
        
        # Re-parse with clarifications
        games, _ = parse_schedule_text(pending['schedule_text'], pending['week'], clarifications)
        
        # Clear pending schedule from session
        session.pop('pending_schedule', None)
        
        # Complete the import
        return complete_schedule_import(games, pending['week'])
        
    except Exception as e:
        flash(f'Error processing clarifications: {e}', 'error')
        return redirect(url_for('clarify_teams'))

@app.route('/scoreboard')
@app.route('/scoreboard/<week>')
@time_route
def scoreboard(week=None):
    
    if not week:
        week = get_current_week_from_snapshots()

    # Get all unique weeks from DATABASE instead of games_data
    all_games = get_games_data()  # Use our database function
    
    weeks_with_games = sorted(set(game['week'] for game in all_games), key=lambda x: (
        # Sort by numeric value if it's a number, otherwise by string
        int(x) if x.isdigit() else (100 if x == 'Bowls' else 101 if x == 'CFP' else 999)
    ))
    
    # If no week specified, default to the most recent week with games
    if not week and weeks_with_games:
        week = weeks_with_games[-1]
    elif not week:
        week = '1'  # Default to week 1 if no games exist
    
    # NEW: Get current rankings for display
    try:
        all_teams_stats = get_all_team_stats_bulk()
        team_rankings = {}
        for i, team_data in enumerate(all_teams_stats, 1):
            if i <= 25:  # Only rank top 25
                team_rankings[team_data['team']] = i
    except Exception as e:
        print(f"Error getting rankings: {e}")
        team_rankings = {}
    
    # NEW: Get scheduled games for the selected week - separate completed from uncompleted
    all_scheduled = get_scheduled_games_list()  # Use database function
    week_scheduled = [game for game in all_scheduled 
                     if game['week'] == week and not game.get('completed', False)]
    week_completed_scheduled = [game for game in all_scheduled 
                               if game['week'] == week and game.get('completed', False)]
    
    # Sort scheduled games by date and time
    def sort_key(game):
        game_date = game.get('game_date', '9999-12-31')
        game_time = game.get('game_time', '11:59 PM')
        
        try:
            if game_time:
                from datetime import datetime
                time_obj = datetime.strptime(game_time, '%I:%M %p')
                time_24h = time_obj.strftime('%H:%M')
            else:
                time_24h = '23:59'
        except:
            time_24h = '23:59'
        
        return f"{game_date} {time_24h}"
    
    week_scheduled.sort(key=sort_key)
    week_completed_scheduled.sort(key=sort_key)
    
    # NEW: Sort function for games (ranked teams first)
    def sort_games_by_ranking(games_list):
        def get_game_rank_priority(game):
            home_rank = team_rankings.get(game.get('home_team', ''), 999)
            away_rank = team_rankings.get(game.get('away_team', ''), 999)
            best_rank = min(home_rank, away_rank)
            return best_rank
        
        return sorted(games_list, key=get_game_rank_priority)
    
    # Group scheduled games by date
    scheduled_by_date = {}
    for game in week_scheduled:
        game_date = game.get('game_date')
        if game_date:
            if game_date not in scheduled_by_date:
                scheduled_by_date[game_date] = []
            scheduled_by_date[game_date].append(game)
        else:
            # Games without dates go in a "TBD" group
            if 'No Date' not in scheduled_by_date:
                scheduled_by_date['No Date'] = []
            scheduled_by_date['No Date'].append(game)
    
    # Group completed scheduled games by date - HANDLE NONE SCORES
    # Group completed scheduled games by date - HANDLE NONE SCORES
    completed_by_date = {}
    for game in week_completed_scheduled:
        game_date = game.get('game_date')
        if game_date:
            if game_date not in completed_by_date:
                completed_by_date[game_date] = []
            # Convert completed scheduled game to look like a regular completed game
            completed_game = {
                'home_team': game['home_team'],
                'away_team': game['away_team'],
                'home_score': game.get('final_home_score') or 0,
                'away_score': game.get('final_away_score') or 0,
                'is_neutral_site': game.get('neutral', False),
                'overtime': game.get('overtime', False),
                'week': game['week'],
                'tv_network': game.get('tv_network'),
                'date_added': 'Scheduled Game',
                'from_schedule': True,
                'bowl_game_name': game.get('bowl_game_name')
            }
            # NEW: Find corresponding Game record for AI analysis (flexible matching)
            corresponding_game = Game.query.filter_by(week=game['week']).filter(
                db.or_(
                    db.and_(Game.home_team == game['home_team'], Game.away_team == game['away_team']),
                    db.and_(Game.home_team == game['away_team'], Game.away_team == game['home_team'])
                )
            ).first()

            if corresponding_game:
                completed_game['id'] = corresponding_game.id
                
            completed_by_date[game_date].append(completed_game)
        else:  # <-- FIXED: Now properly aligned with "if game_date:"
            if 'No Date' not in completed_by_date:
                completed_by_date['No Date'] = []
            completed_game = {
                'home_team': game['home_team'],
                'away_team': game['away_team'],
                'home_score': game.get('final_home_score') or 0,
                'away_score': game.get('final_away_score') or 0,
                'is_neutral_site': game.get('neutral', False),
                'overtime': game.get('overtime', False),
                'week': game['week'],
                'tv_network': game.get('tv_network'),
                'date_added': 'Scheduled Game',
                'from_schedule': True
            }
            # NEW: Find corresponding Game record for AI analysis
            corresponding_game = Game.query.filter_by(
                week=game['week'],
                home_team=game['home_team'],
                away_team=game['away_team']
            ).first()
            if corresponding_game:
                completed_game['id'] = corresponding_game.id
                
            completed_by_date['No Date'].append(completed_game)
    
    # Also add any manually added games (not from schedule) - these might be from before the schedule system
    week_games = [game for game in all_games if game['week'] == week]
    for game in week_games:
        # Check if this game is already represented by a completed scheduled game
        found_scheduled = False
        for scheduled in week_completed_scheduled:
            if ((scheduled['home_team'] == game['home_team'] and scheduled['away_team'] == game['away_team']) or
                (scheduled['home_team'] == game['away_team'] and scheduled['away_team'] == game['home_team'])):
                found_scheduled = True
                break
        
        # Only add if not already represented by scheduled game
        if not found_scheduled:
            game_date = 'No Date'  # Manual games don't have scheduled dates
            if game_date not in completed_by_date:
                completed_by_date[game_date] = []
            # Manual games keep their original date_added format
            game['from_schedule'] = False  # Flag to indicate this was manually added
            completed_by_date[game_date].append(game)
    
    # NEW: Apply sorting to games within each date (ranked teams first)
    for date in scheduled_by_date:
        scheduled_by_date[date] = sort_games_by_ranking(scheduled_by_date[date])
    
    for date in completed_by_date:
        completed_by_date[date] = sort_games_by_ranking(completed_by_date[date])
    
    # Sort dates for display
    all_dates = set(list(scheduled_by_date.keys()) + list(completed_by_date.keys()))
    if 'No Date' in all_dates:
        all_dates.remove('No Date')
        sorted_dates = sorted([d for d in all_dates if d != 'No Date']) + ['No Date']
    else:
        sorted_dates = sorted(all_dates)
    
    return render_template('scoreboard.html', 
                         selected_week=week, 
                         weeks_with_games=weeks_with_games,
                         week_games=week_games,  # Keep for backwards compatibility
                         scheduled_games=week_scheduled,
                         scheduled_by_date=scheduled_by_date,
                         completed_by_date=completed_by_date,
                         sorted_dates=sorted_dates,
                         all_weeks=WEEKS,
                         team_rankings=team_rankings)  # NEW: Pass rankings to template





def get_current_week_info():
    """Get information about the current week for admin display"""
    try:
        current_week = get_current_week_from_snapshots()
        latest_snapshot = WeeklySnapshot.query.order_by(WeeklySnapshot.snapshot_date.desc()).first()
        
        if latest_snapshot:
            return {
                'current_week': current_week,
                'last_snapshot': latest_snapshot.week_name,
                'snapshot_date': latest_snapshot.snapshot_date.strftime('%Y-%m-%d %H:%M'),
                'has_snapshots': True
            }
        else:
            return {
                'current_week': current_week,
                'last_snapshot': 'None',
                'snapshot_date': 'Never',
                'has_snapshots': False
            }
    except Exception as e:
        return {
            'current_week': '1',
            'last_snapshot': 'Error',
            'snapshot_date': 'Error',
            'has_snapshots': False
        }




@app.route('/debug_espn_date')
@login_required
def debug_espn_date():
    """Debug ESPN date extraction"""
    try:
        import requests
        from bs4 import BeautifulSoup
        from datetime import datetime
        import re
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        url = "https://www.espn.com/college-football/fpi"
        
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        debug_info = f"""
        <h2>ESPN Date Extraction Debug</h2>
        <p><strong>URL:</strong> {url}</p>
        <p><strong>Response Status:</strong> {response.status_code}</p>
        
        <h3>Strategy 1: Meta Tags</h3>
        """
        
        # Check meta tags
        meta_tags = soup.find_all('meta')
        found_meta_date = False
        for meta in meta_tags:
            if meta.get('property') in ['article:published_time', 'article:modified_time'] or \
               meta.get('name') in ['publishdate', 'date', 'last-modified']:
                content = meta.get('content', '')
                debug_info += f"<p>Found meta: {meta.get('property') or meta.get('name')} = {content}</p>"
                found_meta_date = True
        
        if not found_meta_date:
            debug_info += "<p>No relevant meta tags found</p>"
        
        debug_info += "<h3>Strategy 2: Page Text Date Patterns</h3>"
        
        # Check page text for dates
        page_text = soup.get_text()
        date_patterns = [
            r'([A-Za-z]+ \d{{1,2}}, \d{{4}})',  # "January 15, 2024"
            r'(\d{{1,2}}/\d{{1,2}}/\d{{4}})',     # "1/15/2024"
            r'Updated:?\s*([A-Za-z]+ \d{{1,2}}, \d{{4}})',  # "Updated: January 15, 2024"
            r'Last updated:?\s*([A-Za-z]+ \d{{1,2}}, \d{{4}})',
            r'as of ([A-Za-z]+ \d{{1,2}}, \d{{4}})',
        ]
        
        found_text_dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, page_text[:3000], re.IGNORECASE)  # Check first 3000 chars
            if matches:
                found_text_dates.extend(matches)
        
        if found_text_dates:
            debug_info += "<p>Found dates in page text:</p><ul>"
            for date in found_text_dates[:10]:  # Show first 10 matches
                debug_info += f"<li>{date}</li>"
            debug_info += "</ul>"
        else:
            debug_info += "<p>No date patterns found in page text</p>"
        
        debug_info += "<h3>Strategy 3: Search for 'June 2' specifically</h3>"
        
        # Search specifically for June 2 since you said that's what shows
        if "June 2" in page_text:
            june_matches = re.findall(r'(June \d{1,2},? \d{4})', page_text, re.IGNORECASE)
            if june_matches:
                debug_info += f"<p>Found June dates: {june_matches}</p>"
            else:
                debug_info += "<p>Found 'June 2' in text but couldn't extract full date</p>"
        else:
            debug_info += "<p>'June 2' not found in page text</p>"
        
        debug_info += f"""
        <h3>First 2000 characters of page:</h3>
        <textarea style="width: 100%; height: 300px;">{page_text[:2000]}</textarea>
        
        <p><a href="/admin">Back to Admin</a></p>
        """
        
        return debug_info
        
    except Exception as e:
        return f"<h2>Debug Error:</h2><p>{str(e)}</p><p><a href='/admin'>Back to Admin</a></p>"

@app.route('/poll_comparison')
def poll_comparison():
    """Poll comparison page with shared external poll timestamp"""
    try:
        # Get our current top 25
        our_rankings = get_all_team_stats_bulk()[:25]
        
        # Fetch all external polls with shared timestamp
        poll_data = fetch_all_polls()
        
        return render_template('poll_comparison.html', 
                             our_rankings=our_rankings,
                             ap_poll=poll_data['ap_poll'],
                             coaches_poll=poll_data['coaches_poll'],
                             espn_poll=poll_data['espn_poll'],
                             sagarin_poll=poll_data['sagarin_poll'],
                             cfp_poll=poll_data['cfp_poll'],
                             # Use the shared timestamp for all external polls
                             external_polls_updated=poll_data['external_polls_updated'])
    except Exception as e:
        return f"Error: {e}"
# Add this function to your app.py file, preferably near your other utility functions

def fetch_all_polls():
    """
    Fetch all polls with ESPN FPI timestamp used for all external polls
    """
    import requests
    from bs4 import BeautifulSoup
    from datetime import datetime
    import re
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    polls = {
        'ap_poll': [],
        'coaches_poll': [],
        'cfp_poll': [],
        'sagarin_poll': [],
        'espn_poll': [],
        'external_polls_updated': 'Unknown'  # Single timestamp for all external polls
    }
    
    def apply_team_variations(team_name):
        """Apply your existing TEAM_VARIATIONS to clean up team names"""
        if not team_name:
            return team_name
            
        # Check if this team name should be converted using your TEAM_VARIATIONS
        for standard_name, variants in TEAM_VARIATIONS.items():
            if team_name in variants:
                return standard_name
        
        # Common poll variations
        poll_mappings = {
            'Mississippi': 'Ole Miss',
            'Miami-Florida': 'Miami',
            'Southern California': 'USC',
            'Texas Christian': 'TCU',
            'Brigham Young': 'BYU',
            'Southern Methodist': 'SMU',
            'Louisiana State': 'LSU',
            'Central Florida': 'UCF',
            'North Carolina State': 'NC State',
            'Virginia Tech': 'Virginia Tech',
            'Boston College': 'Boston College',
            'Florida International': 'Florida Intl',
            'Western Kentucky': 'Western Kentucky',
            'Miami-Ohio': 'Miami (OH)',
            'Appalachian State': 'Appalachian St'
        }
        
        if team_name in poll_mappings:
            return poll_mappings[team_name]
            
        return team_name
    
    # FIRST: Get timestamp from ESPN FPI page for all polls
    # FIXED: Get timestamp from ESPN FPI page for all external polls
    try:
        print("✅ Getting timestamp from ESPN FPI for all external polls...")
        url = "https://www.espn.com/college-football/fpi"
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        external_timestamp = None
        
        # Strategy 1: Look for meta tags with dates
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            if meta.get('property') in ['article:published_time', 'article:modified_time'] or \
               meta.get('name') in ['publishdate', 'date', 'last-modified']:
                content = meta.get('content', '')
                if content:
                    try:
                        dt = datetime.fromisoformat(content.replace('Z', '+00:00'))
                        external_timestamp = dt.strftime('%B %d, %Y')
                        print(f"DEBUG: Found meta date: {external_timestamp}")
                        break
                    except:
                        pass
        
        # Strategy 2: Use the working pattern that found June 2, 2025
        if not external_timestamp:
            page_text = soup.get_text()
            
            # Use the same pattern that worked in the debug for all months
            months = ['January', 'February', 'March', 'April', 'May', 'June', 
                     'July', 'August', 'September', 'October', 'November', 'December']
            
            all_found_dates = []
            for month in months:
                # Use the exact same pattern that found June 2, 2025
                pattern = f'({month} \d{{1,2}}, \d{{4}})'
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    all_found_dates.extend(matches)
            
            # Use the first valid recent date found
            if all_found_dates:
                for date_str in all_found_dates:
                    try:
                        # Validate it's a reasonable recent date
                        test_date = datetime.strptime(date_str, '%B %d, %Y')
                        if 2024 <= test_date.year <= 2025:
                            external_timestamp = date_str
                            break
                    except:
                        continue
        
        # Strategy 3: Look for "Updated" or "Last updated" with more flexible patterns
        if not external_timestamp:
            
            # Look for text around "updated" keywords
            updated_patterns = [
                r'Updated:?\s*([A-Za-z]+ \d{1,2}, \d{4})',
                r'Last updated:?\s*([A-Za-z]+ \d{1,2}, \d{4})',
                r'as of ([A-Za-z]+ \d{1,2}, \d{4})',
            ]
            
            for pattern in updated_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    for match in matches:
                        try:
                            test_date = datetime.strptime(match, '%B %d, %Y')
                            if 2024 <= test_date.year <= 2025:
                                external_timestamp = match
                                break
                        except:
                            continue
                    if external_timestamp:
                        break
        
        # Fallback: Use current date with note
        if not external_timestamp:
            external_timestamp = f"~{datetime.now().strftime('%B %d, %Y')}"
        
        polls['external_polls_updated'] = external_timestamp
        print(f"✅ Final external polls timestamp: {external_timestamp}")
        
    except Exception as e:
        print(f"❌ Failed to get timestamp: {e}")
        polls['external_polls_updated'] = f"~{datetime.now().strftime('%B %d, %Y')}"

    # AP Poll - EXISTING CODE (no timestamp extraction needed)
    try:
        url = "https://www.espn.com/college-football/rankings/_/poll/1"
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        ap_teams = []
        table = soup.find('table')
        if table:
            rows = table.find_all('tr')[1:]
            for i, row in enumerate(rows[:25]):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    team_cell = cells[1]
                    raw_team_name = team_cell.get_text(separator=' ', strip=True)
                    
                    import re
                    clean_name = re.sub(r'\s*\(\s*\d+\s*\).*$', '', raw_team_name)
                    clean_name = clean_name.strip()
                    
                    words = clean_name.split()
                    if len(words) >= 2 and words[0].isupper() and len(words[0]) <= 5:
                        clean_name = ' '.join(words[1:]).strip()
                    
                    if clean_name:
                        ap_teams.append({'rank': i+1, 'team': clean_name})
        
        polls['ap_poll'] = ap_teams
        print(f"✅ AP Poll: {len(ap_teams)} teams")
        
    except Exception as e:
        print(f"❌ AP poll failed: {e}")
        polls['ap_poll'] = []

    # Coaches Poll - EXISTING CODE (no timestamp extraction needed)
    try:
        url = "https://www.espn.com/college-football/rankings/_/poll/2"
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        coaches_teams = []
        table = soup.find('table')
        if table:
            rows = table.find_all('tr')[1:]
            for i, row in enumerate(rows[:25]):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    team_cell = cells[1]
                    raw_team_name = team_cell.get_text(separator=' ', strip=True)
                    
                    import re
                    clean_name = re.sub(r'\s*\(\s*\d+\s*\).*$', '', raw_team_name)
                    clean_name = clean_name.strip()
                    
                    words = clean_name.split()
                    if len(words) >= 2 and words[0].isupper() and len(words[0]) <= 5:
                        clean_name = ' '.join(words[1:]).strip()
                    
                    if clean_name:
                        coaches_teams.append({'rank': i+1, 'team': clean_name})
        
        polls['coaches_poll'] = coaches_teams
        print(f"✅ Coaches Poll: {len(coaches_teams)} teams")
        
    except Exception as e:
        print(f"❌ Coaches poll failed: {e}")
        polls['coaches_poll'] = []

    # Sagarin - EXISTING WORKING CODE
    try:
        url = "https://sagarin.com/sports/cfsend.htm"
        
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        content = response.text
        
        sagarin_teams = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 0 and line[0].isdigit():
                if ' A  = ' in line:
                    before_rating = line.split(' A  = ')[0].strip()
                    parts = before_rating.split()
                    if len(parts) >= 2:
                        try:
                            rank = int(parts[0])
                            raw_team_name = ' '.join(parts[1:]).strip()
                            
                            if 1 <= rank <= 25 and raw_team_name:
                                clean_team_name = apply_team_variations(raw_team_name)
                                sagarin_teams.append({'rank': rank, 'team': clean_team_name})
                                
                                if len(sagarin_teams) >= 25:
                                    break
                        except:
                            continue
        
        polls['sagarin_poll'] = sagarin_teams
        print(f"✅ Sagarin: {len(sagarin_teams)} teams")
        
    except Exception as e:
        print(f"❌ Sagarin failed: {e}")
        polls['sagarin_poll'] = []

    # ESPN FPI - EXISTING CODE (already handled above for timestamp)
    try:
        url = "https://www.espn.com/college-football/fpi"
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        espn_teams = []
        all_valid_teams = set()
        for teams_list in CONFERENCES.values():
            all_valid_teams.update(teams_list)
        
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for i, row in enumerate(rows[1:]):
                if len(espn_teams) >= 25:
                    break
                    
                cells = row.find_all(['td', 'th'])
                team_found = False
                for cell in cells:
                    if team_found:
                        break
                        
                    links = cell.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '')
                        if '/college-football/team/' in href:
                            raw_team_name = link.get_text(strip=True)
                            
                            if raw_team_name and len(raw_team_name) > 2:
                                clean_team_name = clean_scraped_team_name(raw_team_name)
                                
                                if clean_team_name and clean_team_name in all_valid_teams:
                                    if not any(team['team'] == clean_team_name for team in espn_teams):
                                        rank = len(espn_teams) + 1
                                        espn_teams.append({'rank': rank, 'team': clean_team_name})
                                        team_found = True
                                        break
                
                if len(espn_teams) >= 25:
                    break
            
            if len(espn_teams) >= 25:
                break
        
        espn_teams = espn_teams[:25]
        polls['espn_poll'] = espn_teams
        print(f"✅ ESPN FPI: {len(espn_teams)} teams")
        
    except Exception as e:
        print(f"❌ ESPN FPI failed: {e}")
        polls['espn_poll'] = []

    # CFP Poll
    try:
        print("🏈 Fetching CFP Rankings...")
        
        # CFP Rankings are published on the College Football Playoff website
        cfp_url = "https://www.collegefootballplayoff.com/sports/2017/10/16/rankings.aspx"
        
        response = requests.get(cfp_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        cfp_teams = []
        
        # Method 1: Try to find rankings table
        rankings_table = soup.find('table')
        if rankings_table:
            rows = rankings_table.find_all('tr')[1:]  # Skip header
            for row in rows[:25]:  # Top 25
                cols = row.find_all('td')
                if len(cols) >= 2:
                    rank = cols[0].get_text(strip=True)
                    team = cols[1].get_text(strip=True)
                    
                    # Clean up team name
                    team = apply_team_variations(team)
                    
                    cfp_teams.append({
                        'rank': int(rank) if rank.isdigit() else len(cfp_teams) + 1,
                        'team': team
                    })
        
        # Method 2: Try alternative structure with divs/spans
        if not cfp_teams:
            ranking_items = soup.find_all(['div', 'article', 'li'], class_=lambda x: x and ('rank' in x.lower() or 'team' in x.lower()))
            
            for idx, item in enumerate(ranking_items[:25]):
                team_name = item.get_text(strip=True)
                
                # Clean up team name
                team_name = apply_team_variations(team_name)
                
                # Filter out non-team text
                if len(team_name) > 3 and team_name not in ['Rank', 'Team', 'Record', 'Previous']:
                    cfp_teams.append({
                        'rank': idx + 1,
                        'team': team_name
                    })
        
        polls['cfp_poll'] = cfp_teams
        print(f"✅ CFP Rankings: {len(cfp_teams)} teams")
        
    except Exception as e:
        print(f"❌ CFP Rankings failed: {e}")
        polls['cfp_poll'] = []

    return polls


@app.route('/team_leaders')
def team_leaders():
    """Team statistical leaders page"""
    try:
        import time
        start_time = time.time()
        
        print(f"🕐 Starting team_leaders route...")
        
        # Get all team stats using our bulk loading function
        t = time.time()
        all_teams_stats = get_all_team_stats_bulk()
        print(f"✅ get_all_team_stats_bulk: {time.time() - t:.2f}s")
        
        # Filter out teams with no games
        teams_with_games = [team for team in all_teams_stats if team['total_wins'] + team['total_losses'] > 0]
        
        if not teams_with_games:
            flash('No team data available yet. Add some games first!', 'info')
            return render_template('team_leaders.html', leaders={})
        
        # Calculate leaders for each category
        leaders = {}
        
        # OFFENSIVE LEADERS
        t = time.time()
        leaders['highest_scoring'] = calculate_points_per_game_leaders(teams_with_games, 'offense')
        print(f"✅ highest_scoring: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['most_total_points'] = sorted(teams_with_games, key=lambda x: x['points_fielded'], reverse=True)[:10]
        print(f"✅ most_total_points: {time.time() - t:.2f}s")
        
        # DEFENSIVE LEADERS  
        t = time.time()
        leaders['best_defense'] = calculate_points_per_game_leaders(teams_with_games, 'defense')
        print(f"✅ best_defense: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['fewest_total_points'] = sorted(teams_with_games, key=lambda x: x['points_allowed'])[:10]
        print(f"✅ fewest_total_points: {time.time() - t:.2f}s")
        
        # RECORD LEADERS
        t = time.time()
        leaders['best_record'] = calculate_best_records(teams_with_games)
        print(f"✅ best_record: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['most_wins'] = sorted(teams_with_games, key=lambda x: x['total_wins'], reverse=True)[:10]
        print(f"✅ most_wins: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['best_road_record'] = calculate_road_leaders(teams_with_games)
        print(f"✅ best_road_record: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['best_home_record'] = calculate_home_leaders(teams_with_games)
        print(f"✅ best_home_record: {time.time() - t:.2f}s")
        
        # MARGIN LEADERS
        t = time.time()
        leaders['best_margin'] = calculate_margin_leaders(teams_with_games)
        print(f"✅ best_margin: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['worst_margin'] = calculate_margin_leaders(teams_with_games, reverse=True)
        print(f"✅ worst_margin: {time.time() - t:.2f}s")
        
        # STRENGTH LEADERS
        t = time.time()
        leaders['toughest_schedule'] = sorted(teams_with_games, key=lambda x: x['strength_of_schedule'], reverse=True)[:10]
        print(f"✅ toughest_schedule: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['easiest_schedule'] = sorted(teams_with_games, key=lambda x: x['strength_of_schedule'])[:10]
        print(f"✅ easiest_schedule: {time.time() - t:.2f}s")
        
        # INDIVIDUAL GAME RECORDS
        t = time.time()
        leaders['biggest_wins'] = get_biggest_wins()
        print(f"✅ biggest_wins: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['biggest_losses'] = get_biggest_losses()
        print(f"✅ biggest_losses: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['highest_scoring_games'] = get_highest_scoring_games()
        print(f"✅ highest_scoring_games: {time.time() - t:.2f}s")
        
        # QUALITY METRICS
        t = time.time()
        leaders['best_ranking'] = teams_with_games[:10]  # Top 10 by ranking
        print(f"✅ best_ranking: {time.time() - t:.2f}s")
        
        t = time.time()
        leaders['most_improved'] = calculate_improvement_leaders(teams_with_games)
        print(f"✅ most_improved: {time.time() - t:.2f}s")
        
        print(f"🏁 TOTAL team_leaders time: {time.time() - start_time:.2f}s")
        
        return render_template('team_leaders.html', leaders=leaders)
        
    except Exception as e:
        flash(f'Error loading team leaders: {e}', 'error')
        return render_template('team_leaders.html', leaders={})

def calculate_points_per_game_leaders(teams, category):
    """Calculate points per game leaders for offense or defense"""
    leaders = []
    
    for team in teams:
        total_games = team['total_wins'] + team['total_losses']
        if total_games == 0:
            continue
            
        if category == 'offense':
            ppg = team['points_fielded'] / total_games
        else:  # defense
            ppg = team['points_allowed'] / total_games
            
        leaders.append({
            'team': team['team'],
            'conference': team['conference'],
            'ppg': round(ppg, 1),
            'total_points': team['points_fielded'] if category == 'offense' else team['points_allowed'],
            'games': total_games,
            'record': f"{team['total_wins']}-{team['total_losses']}"
        })
    
    # Sort by PPG (ascending for defense, descending for offense)
    reverse_sort = (category == 'offense')
    return sorted(leaders, key=lambda x: x['ppg'], reverse=reverse_sort)[:10]

def calculate_best_records(teams):
    """Calculate best records by winning percentage (minimum 6 games)"""
    leaders = []
    
    for team in teams:
        total_games = team['total_wins'] + team['total_losses']
        if total_games < 6:  # Minimum games requirement
            continue
            
        win_pct = team['total_wins'] / total_games
        
        leaders.append({
            'team': team['team'],
            'conference': team['conference'],
            'wins': team['total_wins'],
            'losses': team['total_losses'],
            'win_pct': round(win_pct, 3),
            'record': f"{team['total_wins']}-{team['total_losses']}"
        })
    
    return sorted(leaders, key=lambda x: (x['win_pct'], x['wins']), reverse=True)[:10]

def calculate_road_leaders(teams):
    """Calculate best road records"""
    leaders = []
    
    for team in teams:
        if team['road_wins'] + team.get('road_losses', 0) < 3:  # Need some road games
            continue
            
        # Calculate road losses from team stats if available
        road_games = team['road_wins']
        
        # Get road losses from detailed stats if possible
        try:
            team_record = TeamStats.query.filter_by(team_name=team['team']).first()
            if team_record:
                games = team_record.to_dict()['games']
                road_losses = len([g for g in games if g['result'] == 'L' and g['home_away'] == 'Away'])
                road_games_total = team['road_wins'] + road_losses
                
                if road_games_total > 0:
                    road_win_pct = team['road_wins'] / road_games_total
                    
                    leaders.append({
                        'team': team['team'],
                        'conference': team['conference'],
                        'road_wins': team['road_wins'],
                        'road_losses': road_losses,
                        'road_win_pct': round(road_win_pct, 3),
                        'road_record': f"{team['road_wins']}-{road_losses}"
                    })
        except:
            # Fallback if detailed stats not available
            if team['road_wins'] > 0:
                leaders.append({
                    'team': team['team'],
                    'conference': team['conference'],
                    'road_wins': team['road_wins'],
                    'road_losses': 0,
                    'road_win_pct': 1.000,
                    'road_record': f"{team['road_wins']}-0"
                })
    
    return sorted(leaders, key=lambda x: (x['road_win_pct'], x['road_wins']), reverse=True)[:10]

def calculate_home_leaders(teams):
    """Calculate best home records"""
    leaders = []
    
    for team in teams:
        if team['home_wins'] == 0:
            continue
            
        try:
            team_record = TeamStats.query.filter_by(team_name=team['team']).first()
            if team_record:
                games = team_record.to_dict()['games']
                home_losses = len([g for g in games if g['result'] == 'L' and g['home_away'] == 'Home'])
                home_games_total = team['home_wins'] + home_losses
                
                if home_games_total > 0:
                    home_win_pct = team['home_wins'] / home_games_total
                    
                    leaders.append({
                        'team': team['team'],
                        'conference': team['conference'],
                        'home_wins': team['home_wins'],
                        'home_losses': home_losses,
                        'home_win_pct': round(home_win_pct, 3),
                        'home_record': f"{team['home_wins']}-{home_losses}"
                    })
        except:
            # Fallback
            if team['home_wins'] > 0:
                leaders.append({
                    'team': team['team'],
                    'conference': team['conference'],
                    'home_wins': team['home_wins'],
                    'home_losses': 0,
                    'home_win_pct': 1.000,
                    'home_record': f"{team['home_wins']}-0"
                })
    
    return sorted(leaders, key=lambda x: (x['home_win_pct'], x['home_wins']), reverse=True)[:10]

def calculate_margin_leaders(teams, reverse=False):
    """Calculate margin of victory leaders"""
    leaders = []
    
    for team in teams:
        total_games = team['total_wins'] + team['total_losses']
        if total_games == 0:
            continue
            
        avg_margin = team['point_differential'] / total_games
        
        leaders.append({
            'team': team['team'],
            'conference': team['conference'],
            'avg_margin': round(avg_margin, 1),
            'total_differential': team['point_differential'],
            'record': f"{team['total_wins']}-{team['total_losses']}"
        })
    
    return sorted(leaders, key=lambda x: x['avg_margin'], reverse=not reverse)[:10]

def get_biggest_wins():
    """Get the biggest margin of victory games (excluding FCS games)"""
    biggest_wins = []
    
    all_games = get_games_data()
    
    for game in all_games:
        # Skip games involving FCS teams
        if game['home_team'] == 'FCS' or game['away_team'] == 'FCS':
            continue
            
        home_margin = game['home_score'] - game['away_score']
        away_margin = game['away_score'] - game['home_score']
        
        if home_margin > 0:  # Home team won
            biggest_wins.append({
                'winner': game['home_team'],
                'loser': game['away_team'],
                'score': f"{game['home_score']}-{game['away_score']}",
                'margin': home_margin,
                'week': game['week'],
                'location': 'vs' if not game.get('is_neutral_site', False) else 'N'
            })
        else:  # Away team won
            biggest_wins.append({
                'winner': game['away_team'],
                'loser': game['home_team'],
                'score': f"{game['away_score']}-{game['home_score']}",
                'margin': away_margin,
                'week': game['week'],
                'location': '@' if not game.get('is_neutral_site', False) else 'N'
            })
    
    return sorted(biggest_wins, key=lambda x: x['margin'], reverse=True)[:10]

def get_biggest_losses():
    """Get the most shocking losses (to lowest-ranked opponents)"""
    # This is complex without opponent rankings, so we'll use a simplified version
    return get_biggest_wins()  # For now, same as biggest wins but could be enhanced

def get_highest_scoring_games():
    """Get the highest total point games (excluding FCS games)"""
    high_scoring = []
    
    all_games = get_games_data()
    
    for game in all_games:
        # Skip games involving FCS teams
        if game['home_team'] == 'FCS' or game['away_team'] == 'FCS':
            continue
            
        total_points = game['home_score'] + game['away_score']
        
        high_scoring.append({
            'home_team': game['home_team'],
            'away_team': game['away_team'],
            'score': f"{game['home_score']}-{game['away_score']}",
            'total_points': total_points,
            'week': game['week'],
            'overtime': game.get('overtime', False)
        })
    
    return sorted(high_scoring, key=lambda x: x['total_points'], reverse=True)[:10]

def calculate_improvement_leaders(teams):
    """Calculate most improved teams (DISABLED - too expensive)"""
    # This was taking 173+ seconds to calculate
    # Disabled until we implement a more efficient version
    return []


@app.route('/add_game', methods=['GET', 'POST'])
@login_required
def add_game():
    if request.method == 'POST':
        try:
            # Get form data
            week = request.form['week']
            home_team = request.form['home_team']
            away_team = request.form['away_team']
            home_score = int(request.form['home_score'])
            away_score = int(request.form['away_score'])
            is_neutral_site = 'neutral_site' in request.form
            is_overtime = 'overtime' in request.form
            is_bowl_game = 'is_bowl_game' in request.form
            bowl_game_name = request.form.get('bowl_name', '').strip() if is_bowl_game else None
            
            # Validate that teams are different
            if home_team == away_team:
                flash('Teams must be different!', 'error')
                return redirect(url_for('add_game', selected_week=week))
            
            # FCS warning check
            if is_fcs_opponent(home_team) or is_fcs_opponent(away_team):
                flash('⚠️ FCS game detected - minimal ranking credit will be awarded for this victory', 'warning')
            
            # DEBUG: Show what we're looking for
            flash(f'🔍 DEBUG: Looking for scheduled game: {home_team} vs {away_team} in Week {week}', 'info')
            
            # STEP 1: First, add the game and update team stats
            game = Game(
                week=week,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                is_neutral_site=is_neutral_site,
                overtime=is_overtime,
                is_bowl_game=is_bowl_game,
                bowl_game_name=bowl_game_name
            )
            db.session.add(game)
            
            # Update team statistics
            update_team_stats_in_db(home_team, away_team, home_score, away_score, True, is_neutral_site, is_overtime)
            update_team_stats_in_db(away_team, home_team, away_score, home_score, False, is_neutral_site, is_overtime)
            
            # Commit the game addition first
            db.session.commit()
            flash(f'✅ Game added to database successfully', 'success')
            
            # 🤖 CFB ML TRACKING: Log the actual game result
            if CFB_ML_ENABLED:
                log_game_result_to_ml(home_team, away_team, home_score, away_score, week, is_overtime)
            
            # STEP 2: Look for scheduled game
            try:
                # Check what scheduled games exist for this week
                all_week_games = ScheduledGame.query.filter_by(week=week).all()
                flash(f'📊 Found {len(all_week_games)} total scheduled games for week {week}', 'info')
                
                # Show what games we found
                game_list = []
                for g in all_week_games:
                    status = "✅ Completed" if g.completed else "❌ Uncompleted"
                    game_list.append(f"{g.home_team} vs {g.away_team} ({status})")
                
                if game_list:
                    flash(f'Games found: {"; ".join(game_list)}', 'info')
                
                # Look for the specific matching game
                scheduled_game = ScheduledGame.query.filter_by(
                    week=week,
                    completed=False
                ).filter(
                    db.or_(
                        db.and_(ScheduledGame.home_team == home_team, ScheduledGame.away_team == away_team),
                        db.and_(ScheduledGame.home_team == away_team, ScheduledGame.away_team == home_team)
                    )
                ).first()
                
                if scheduled_game:
                    flash(f'🎯 FOUND MATCHING SCHEDULED GAME: {scheduled_game.home_team} vs {scheduled_game.away_team} (ID: {scheduled_game.id})', 'info')
                    
                    # Store original state for debugging
                    original_completed = scheduled_game.completed
                    game_id = scheduled_game.id
                    
                    # Update the scheduled game
                    scheduled_game.completed = True
                    
                    # Assign scores
                    if scheduled_game.home_team == home_team:
                        scheduled_game.final_home_score = home_score
                        scheduled_game.final_away_score = away_score
                        flash(f'📝 Setting scores (same orientation): {home_score}-{away_score}', 'info')
                    else:
                        scheduled_game.final_home_score = away_score
                        scheduled_game.final_away_score = home_score
                        flash(f'📝 Setting scores (flipped orientation): {away_score}-{home_score}', 'info')
                    
                    scheduled_game.overtime = is_overtime
                    
                    # Commit the scheduled game update
                    db.session.add(scheduled_game)  # Make sure it's tracked
                    db.session.commit()
                    flash(f'💾 Committed scheduled game update to database', 'info')
                    
                    # VERIFICATION: Check if it actually worked
                    verification_game = ScheduledGame.query.get(game_id)
                    if verification_game and verification_game.completed:
                        flash(f'🎉 SUCCESS! Scheduled game marked as completed with scores {verification_game.final_home_score}-{verification_game.final_away_score}', 'success')
                    else:
                        completed_status = verification_game.completed if verification_game else "NOT FOUND"
                        flash(f'❌ FAILED! Verification shows completed = {completed_status}', 'error')
                        
                        # Try a more aggressive update
                        flash(f'🔧 Trying direct SQL update...', 'warning')
                        db.session.execute(
                            text("UPDATE scheduled_games SET completed = true, final_home_score = :home, final_away_score = :away WHERE id = :id"),
                            {"home": scheduled_game.final_home_score, "away": scheduled_game.final_away_score, "id": game_id}
                        )
                        db.session.commit()
                        flash(f'🔧 Direct SQL update completed', 'warning')
                
                else:
                    flash(f'❌ NO MATCHING SCHEDULED GAME FOUND', 'warning')
                    uncompleted_games = ScheduledGame.query.filter_by(week=week, completed=False).all()
                    if uncompleted_games:
                        uncompleted_list = [f"{g.home_team} vs {g.away_team}" for g in uncompleted_games]
                        flash(f'Available uncompleted games: {"; ".join(uncompleted_list)}', 'info')
                    else:
                        flash(f'No uncompleted scheduled games found for week {week}', 'info')
                
            except Exception as e:
                flash(f'❌ ERROR in scheduled game update: {str(e)}', 'error')
                import traceback
                flash(f'Full error: {traceback.format_exc()}', 'error')
            
            # Remember the selected week for next time
            session['last_selected_week'] = week
            
            return redirect(url_for('add_game'))
            
        except ValueError:
            flash('Please enter valid scores (numbers only)', 'error')
            return redirect(url_for('add_game'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding game: {e}', 'error')
            return redirect(url_for('add_game'))
    
    # GET request - render the form
    selected_week = request.args.get('selected_week') or session.get('last_selected_week', '')
    recent_games = get_games_data()[-10:]
    return render_template('add_game.html', 
                         conferences=CONFERENCES, 
                         weeks=WEEKS, 
                         recent_games=recent_games, 
                         selected_week=selected_week)


def log_game_result_to_ml(home_team, away_team, home_score, away_score, week, is_overtime=False):
    """Enhanced game result logging with correct point spread logic"""
    if not CFB_ML_ENABLED:
        print("🤖 ML tracking disabled")
        return
    
    try:
        print(f"🤖 ML tracking called: {home_team} vs {away_team}, week {week}")
        
        # Determine actual winner and margin
        if home_score > away_score:
            actual_winner = home_team
            actual_margin = home_score - away_score
        else:
            actual_winner = away_team
            actual_margin = away_score - home_score
        
        # Calculate actual total
        actual_total = home_score + away_score
        
        # Find all matching predictions for this game
        predictions = CFBPredictionLog.query.filter(
            CFBPredictionLog.home_team == home_team,
            CFBPredictionLog.away_team == away_team,
            CFBPredictionLog.week == str(week),
            CFBPredictionLog.game_completed == False
        ).all()
        
        print(f"🤖 Found {len(predictions)} matching predictions to update")
        
        results_updated = 0
        
        for prediction in predictions:
            print(f"🤖 Updating prediction ID {prediction.id}: {prediction.home_team} vs {prediction.away_team}")
            
            # Update actual results
            prediction.actual_winner = actual_winner
            prediction.actual_margin = actual_margin
            prediction.actual_total = actual_total
            prediction.game_completed = True
            prediction.result_date = datetime.utcnow()
            
            # CORRECT: Point spread logic
            predicted_spread = prediction.predicted_margin if prediction.predicted_margin else 0
            
            if prediction.predicted_winner == actual_winner:
                # Winner predicted correctly, check if they covered the spread
                prediction.winner_correct = (actual_margin >= predicted_spread)
            else:
                # Wrong winner predicted = automatically wrong
                prediction.winner_correct = False
            
            # Margin error
            if prediction.predicted_margin is not None:
                prediction.margin_error = abs(prediction.predicted_margin - actual_margin)
            
            # Total error (over/under)
            if prediction.predicted_total is not None:
                prediction.total_error = abs(prediction.predicted_total - actual_total)
            
            results_updated += 1
        
        # Commit all updates
        db.session.commit()
        print(f"🤖 Committed {results_updated} prediction updates")
        
        if results_updated > 0:
            flash(f'🤖 ML Tracking: Updated {results_updated} prediction(s) with actual result', 'info')
        
        return results_updated
    
    except Exception as e:
        db.session.rollback()
        print(f"🤖 Enhanced ML tracking error: {e}")
        return 0



@app.route('/admin/ml/reprocess_week_results/<int:week>')
@login_required
def reprocess_week_results(week):
    """Re-log all game results with flexible team matching for neutral site games (excluding FCS)"""
    try:
        # Reset predictions back to incomplete - but only for FBS games
        predictions_to_reset = CFBPredictionLog.query.filter(
            CFBPredictionLog.week == str(week),
            CFBPredictionLog.game_completed == True,
            # Only reset FBS vs FBS predictions
            ~(CFBPredictionLog.home_team.ilike('%FCS%')),
            ~(CFBPredictionLog.away_team.ilike('%FCS%')),
            CFBPredictionLog.home_team != 'FCS',
            CFBPredictionLog.away_team != 'FCS'
        ).all()
        
        for pred in predictions_to_reset:
            pred.game_completed = False
            pred.actual_winner = None
            pred.actual_margin = None
            pred.winner_correct = None
        
        db.session.commit()
        
        # Get all FBS games for this week (exclude FCS)
        week_games = Game.query.filter(
            Game.week == str(week),
            ~(Game.home_team.ilike('%FCS%')),
            ~(Game.away_team.ilike('%FCS%')),
            Game.home_team != 'FCS',
            Game.away_team != 'FCS'
        ).all()
        
        results_updated = 0
        fcs_games_total = Game.query.filter_by(week=str(week)).count()
        fcs_games_excluded = fcs_games_total - len(week_games)
        
        for game in week_games:
            # Find predictions for this game (check both orientations)
            predictions = CFBPredictionLog.query.filter(
                CFBPredictionLog.week == str(week),
                CFBPredictionLog.game_completed == False
            ).filter(
                db.or_(
                    db.and_(CFBPredictionLog.home_team == game.home_team, CFBPredictionLog.away_team == game.away_team),
                    db.and_(CFBPredictionLog.home_team == game.away_team, CFBPredictionLog.away_team == game.home_team)
                )
            ).all()
            
            # Update each matching prediction
            for prediction in predictions:
                if game.home_score > game.away_score:
                    actual_winner = game.home_team
                    actual_margin = game.home_score - game.away_score
                else:
                    actual_winner = game.away_team
                    actual_margin = game.away_score - game.home_score
                
                prediction.actual_winner = actual_winner
                prediction.actual_margin = actual_margin
                prediction.game_completed = True
                
                # Apply your spread logic
                predicted_spread = prediction.predicted_margin if prediction.predicted_margin else 0
                if prediction.predicted_winner != actual_winner:
                    prediction.winner_correct = False
                else:
                    prediction.winner_correct = (actual_margin >= predicted_spread)
                
                results_updated += 1
        
        db.session.commit()
        
        # Updated flash message
        if fcs_games_excluded > 0:
            flash(f'Re-processed {len(week_games)} FBS games, updated {results_updated} predictions. Excluded {fcs_games_excluded} FCS games.', 'success')
        else:
            flash(f'Re-processed {len(week_games)} games, updated {results_updated} predictions', 'success')
        
        return redirect(url_for('cfb_ml_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))

@app.route('/admin/ml/predict_completed_week/<int:week>')
@login_required
def predict_completed_week(week):
    """Create predictions for already-completed games with full debugging (excluding FCS games)"""
    try:
        # Get completed games for this week - EXCLUDE FCS GAMES
        completed_games = ScheduledGame.query.filter(
            ScheduledGame.week == str(week),
            ScheduledGame.completed == True,
            # NEW: Filter out FCS games
            ~(ScheduledGame.home_team.ilike('%FCS%')),
            ~(ScheduledGame.away_team.ilike('%FCS%')),
            ScheduledGame.home_team != 'FCS',
            ScheduledGame.away_team != 'FCS'
        ).all()
        
        # Additional Python-level filtering for safety
        fbs_completed_games = []
        fcs_games_skipped = 0
        
        for game in completed_games:
            if (is_fcs_opponent(game.home_team) or is_fcs_opponent(game.away_team)):
                fcs_games_skipped += 1
                continue
            fbs_completed_games.append(game)
        
        print(f"DEBUG: Found {len(fbs_completed_games)} completed FBS vs FBS games for week {week}")
        if fcs_games_skipped > 0:
            print(f"DEBUG: Skipped {fcs_games_skipped} FCS games")
        
        if not fbs_completed_games:
            if fcs_games_skipped > 0:
                flash(f'No completed FBS vs FBS games found for Week {week}. Skipped {fcs_games_skipped} FCS games.', 'info')
            else:
                flash(f'No completed FBS games found for Week {week}', 'info')
            return redirect(url_for('cfb_ml_dashboard'))
        
        predictions_created = 0
        errors = []
        
        for i, scheduled_game in enumerate(fbs_completed_games):
            try:
                print(f"DEBUG: Processing game {i+1}: {scheduled_game.home_team} vs {scheduled_game.away_team}")
                
                # Check if prediction already exists
                existing = CFBPredictionLog.query.filter(
                    CFBPredictionLog.home_team == scheduled_game.home_team,
                    CFBPredictionLog.away_team == scheduled_game.away_team,
                    CFBPredictionLog.week == str(week)
                ).first()
                
                if existing:
                    print(f"DEBUG: Skipping - prediction already exists")
                    continue
                
                # Generate prediction
                location = 'neutral' if scheduled_game.neutral else 'home'
                print(f"DEBUG: Calling predict_matchup_ultra_enhanced with location: {location}")
                
                prediction_result = predict_matchup_ultra_enhanced(
                    scheduled_game.home_team,
                    scheduled_game.away_team, 
                    location
                )
                
                print(f"DEBUG: Prediction result keys: {list(prediction_result.keys())}")
                print(f"DEBUG: Winner: {prediction_result.get('winner')} (type: {type(prediction_result.get('winner'))})")
                print(f"DEBUG: Final margin: {prediction_result.get('final_margin')} (type: {type(prediction_result.get('final_margin'))})")
                print(f"DEBUG: Win probability: {prediction_result.get('win_probability')} (type: {type(prediction_result.get('win_probability'))})")
                print(f"DEBUG: Confidence: {prediction_result.get('confidence')} (type: {type(prediction_result.get('confidence'))})")
                
                # Create prediction log entry
                prediction_log = CFBPredictionLog()
                prediction_log.season_year = 2025
                prediction_log.week = str(week)
                prediction_log.home_team = scheduled_game.home_team
                prediction_log.away_team = scheduled_game.away_team
                prediction_log.prediction_type = 'automated'
                
                print(f"DEBUG: About to assign prediction values...")
                
                prediction_log.predicted_winner = prediction_result['winner']
                print(f"DEBUG: Assigned winner")
                
                prediction_log.predicted_margin = abs(prediction_result['final_margin'])
                print(f"DEBUG: Assigned margin")
                
                prediction_log.win_probability = prediction_result['win_probability']
                print(f"DEBUG: Assigned win probability")
                
                prediction_log.confidence_level = prediction_result['confidence']
                print(f"DEBUG: Assigned confidence")
                
                prediction_log.game_completed = False
                print(f"DEBUG: About to add to session...")
                
                db.session.add(prediction_log)
                print(f"DEBUG: Added to session, about to commit...")
                
                db.session.commit()
                print(f"DEBUG: Committed successfully")
                
                predictions_created += 1
                
            except Exception as e:
                error_msg = f"Game {i+1} ({scheduled_game.home_team} vs {scheduled_game.away_team}): {str(e)}"
                errors.append(error_msg)
                print(f"DEBUG ERROR: {error_msg}")
                db.session.rollback()
                
                # Print the full traceback for this specific error
                import traceback
                print(f"DEBUG TRACEBACK: {traceback.format_exc()}")
                continue
        
        if errors:
            print(f"DEBUG: All errors encountered:")
            for error in errors:
                print(f"  - {error}")
        
        # Updated flash message to include FCS exclusion info
        if fcs_games_skipped > 0:
            flash(f'Created {predictions_created} predictions for FBS games. {len(errors)} errors occurred. Excluded {fcs_games_skipped} FCS games.', 'warning' if errors else 'success')
        else:
            flash(f'Created {predictions_created} predictions. {len(errors)} errors occurred.', 'warning' if errors else 'success')
        
        return redirect(url_for('cfb_ml_dashboard'))
        
    except Exception as e:
        print(f"DEBUG: Major error in outer try block: {str(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        flash(f'Error: {e}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))




@app.route('/admin/ml/debug_week/<int:week>')
@login_required
def debug_week_games(week):
    """Debug what games exist for a week"""
    
    all_games = ScheduledGame.query.filter(ScheduledGame.week == str(week)).all()
    completed_games = [g for g in all_games if g.completed]
    
    game_list = []
    for game in all_games:
        status = "COMPLETED" if game.completed else "SCHEDULED"
        game_list.append(f"{game.home_team} vs {game.away_team} - {status}")
    
    return f"""
    <h2>Week {week} Games Debug</h2>
    <p>Total games: {len(all_games)}</p>
    <p>Completed games: {len(completed_games)}</p>
    <ul>
    {''.join(f'<li>{game}</li>' for game in game_list)}
    </ul>
    <a href="/admin/ml">Back</a>
    """



@app.route('/add_bulk_games', methods=['POST'])
@login_required
def add_bulk_games():
    """Add multiple games at once WITH scheduled game matching"""
    try:
        games_data = request.form.to_dict(flat=False)
        games_added = 0
        scheduled_games_updated = 0
        
        # Parse the games array
        game_indices = set()
        for key in games_data.keys():
            if key.startswith('games[') and '][' in key:
                index = key.split('[')[1].split(']')[0]
                game_indices.add(int(index))
        
        for index in sorted(game_indices):
            # Extract game data for this index
            week = games_data.get(f'games[{index}][week]', [''])[0]
            home_team = games_data.get(f'games[{index}][home_team]', [''])[0]
            away_team = games_data.get(f'games[{index}][away_team]', [''])[0]
            home_score = games_data.get(f'games[{index}][home_score]', [''])[0]
            away_score = games_data.get(f'games[{index}][away_score]', [''])[0]
            neutral_site = f'games[{index}][neutral_site]' in games_data
            overtime = f'games[{index}][overtime]' in games_data
            is_bowl_game = f'games[{index}][is_bowl_game]' in games_data
            bowl_game_name = games_data.get(f'games[{index}][bowl_name]', [''])[0].strip() if is_bowl_game else None
            
            # Validate required fields
            if not all([week, home_team, away_team, home_score, away_score]):
                continue  # Skip incomplete games
            
            try:
                home_score = int(home_score)
                away_score = int(away_score)
            except ValueError:
                continue  # Skip invalid scores
            
            # Add the game (reuse existing logic)
            game = Game(
                week=week,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                is_neutral_site=neutral_site,
                overtime=overtime,
                is_bowl_game=is_bowl_game,
                bowl_game_name=bowl_game_name
            )
            db.session.add(game)
            
            # Update team stats
            update_team_stats_in_db(home_team, away_team, home_score, away_score, True, neutral_site, overtime)
            update_team_stats_in_db(away_team, home_team, away_score, home_score, False, neutral_site, overtime)
            
            games_added += 1

            if CFB_ML_ENABLED:
                log_game_result_to_ml(home_team, away_team, home_score, away_score, week, overtime)
            
            # NEW: Check for matching scheduled game and mark it completed
            try:
                scheduled_game = ScheduledGame.query.filter_by(
                    week=week,
                    completed=False
                ).filter(
                    db.or_(
                        db.and_(ScheduledGame.home_team == home_team, ScheduledGame.away_team == away_team),
                        db.and_(ScheduledGame.home_team == away_team, ScheduledGame.away_team == home_team)
                    )
                ).first()
                
                if scheduled_game:
                    # Mark the scheduled game as completed
                    scheduled_game.completed = True
                    
                    # Assign scores based on team orientation
                    if scheduled_game.home_team == home_team:
                        scheduled_game.final_home_score = home_score
                        scheduled_game.final_away_score = away_score
                    else:
                        scheduled_game.final_home_score = away_score
                        scheduled_game.final_away_score = home_score
                    
                    scheduled_game.overtime = overtime
                    scheduled_games_updated += 1
                    
            except Exception as e:
                flash(f'Warning: Could not update scheduled game for {home_team} vs {away_team}: {e}', 'warning')
        
        # Commit all changes at once
        db.session.commit()
        
        if games_added > 0:
            if scheduled_games_updated > 0:
                flash(f'✅ Successfully added {games_added} games and updated {scheduled_games_updated} scheduled games!', 'success')
            else:
                flash(f'✅ Successfully added {games_added} games!', 'success')
        else:
            flash('❌ No valid games were added. Please check your input.', 'error')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding games: {e}', 'error')
    
    return redirect(url_for('add_game'))


@app.route('/admin/ml')
@login_required
def cfb_ml_dashboard():
    """Enhanced CFB ML tracking dashboard with automated predictions"""
    if not CFB_ML_ENABLED:
        flash('CFB ML tracking is not available. Please check cfb_ml_tracking.py', 'error')
        return redirect(url_for('admin'))
    
    try:
        # Import the enhanced function
        from cfb_ml_tracking import get_enhanced_ml_dashboard_data
        
        dashboard_data = get_enhanced_ml_dashboard_data()
        if not dashboard_data:
            flash('Error loading enhanced ML dashboard data', 'error')
            return redirect(url_for('admin'))
        
        return render_template('ml_dashboard.html', 
                             dashboard_data=dashboard_data)
        
    except Exception as e:
        flash(f'Error loading enhanced CFB ML dashboard: {e}', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/ml/export/<format>')
@login_required
def cfb_ml_export(format):
    """Export CFB ML prediction data"""
    if not CFB_ML_ENABLED:
        return {'error': 'CFB ML tracking not available'}, 400
    
    try:
        weeks = request.args.getlist('weeks')
        data = export_prediction_data(format=format, weeks=weeks if weeks else None)
        
        if format == 'json':
            return data
        elif format == 'csv':
            from flask import Response
            return Response(
                data,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=cfb_predictions_{datetime.now().year}.csv'}
            )
        else:
            return {'error': 'Unsupported format'}, 400
            
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/admin/ml/temporal_weights')
@login_required
def cfb_ml_temporal_weights():
    """View temporal weight analysis and suggestions"""
    if not CFB_ML_ENABLED:
        flash('CFB ML tracking is not available', 'error')
        return redirect(url_for('admin'))
    
    try:
        from cfb_ml_tracking import CFBTemporalAnalysis
        
        # Get temporal analysis data
        temporal_data = CFBTemporalAnalysis.query.filter_by(
            season_year=datetime.now().year
        ).order_by(CFBTemporalAnalysis.week).all()
        
        # Compare current weights with suggested weights
        weight_comparison = []
        for week_data in temporal_data:
            if week_data.predictions_verified and week_data.predictions_verified > 0:
                current_weight = get_temporal_weight_by_week(week_data.week)
                suggested_weight = week_data.suggested_weight
                
                weight_comparison.append({
                    'week': week_data.week,
                    'current_weight': current_weight,
                    'suggested_weight': suggested_weight,
                    'difference': suggested_weight - current_weight,
                    'accuracy': week_data.average_accuracy,
                    'predictions': week_data.predictions_verified,
                    'confidence': week_data.average_confidence
                })
        
        return render_template('cfb_temporal_weights.html', 
                             weight_comparison=weight_comparison,
                             temporal_data=temporal_data)
        
    except Exception as e:
        flash(f'Error loading temporal weights analysis: {e}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))

@app.route('/admin/ml/prediction_factors')
@login_required
def cfb_ml_prediction_factors():
    """Analyze prediction factor performance"""
    if not CFB_ML_ENABLED:
        flash('CFB ML tracking is not available', 'error')
        return redirect(url_for('admin'))
    
    try:
        from cfb_ml_tracking import CFBAlgorithmPerformance
        
        # Get algorithm performance data
        performance = CFBAlgorithmPerformance.query.filter_by(
            season_year=datetime.now().year
        ).first()
        
        if not performance:
            flash('No CFB ML performance data available yet', 'info')
            return redirect(url_for('cfb_ml_dashboard'))
        
        # Parse factor importance and optimization suggestions
        factor_importance = {}
        optimization_suggestions = []
        
        if performance.factor_importance:
            factor_importance = json.loads(performance.factor_importance)
        
        if performance.optimization_suggestions:
            optimization_suggestions = json.loads(performance.optimization_suggestions)
        
        return render_template('cfb_prediction_factors.html',
                             performance=performance,
                             factor_importance=factor_importance,
                             optimization_suggestions=optimization_suggestions)
        
    except Exception as e:
        flash(f'Error loading prediction factors analysis: {e}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))

@app.route('/admin/ml/reset_tracking', methods=['POST'])
@login_required
def cfb_ml_reset_tracking():
    """Reset CFB ML tracking data (for testing)"""
    if not CFB_ML_ENABLED:
        flash('CFB ML tracking is not available', 'error')
        return redirect(url_for('admin'))
    
    try:
        confirm_text = request.form.get('reset_confirm', '').strip()
        if confirm_text != 'RESET ML':
            flash('Reset confirmation failed. Please type "RESET ML" exactly.', 'error')
            return redirect(url_for('cfb_ml_dashboard'))
        
        # Clear all CFB ML tracking data
        from cfb_ml_tracking import CFBPredictionLog, CFBTemporalAnalysis, CFBAlgorithmPerformance
        
        CFBPredictionLog.query.delete()
        CFBTemporalAnalysis.query.delete()
        CFBAlgorithmPerformance.query.delete()
        
        db.session.commit()
        
        # Reinitialize
        cfb_ml_tracking.setup_cfb_ml_tracking()
        
        flash('🗑️ CFB ML tracking data has been reset. Ready for fresh predictions!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting CFB ML tracking: {e}', 'error')
    
    return redirect(url_for('cfb_ml_dashboard'))


@app.route('/admin/ml/recalculate_performance')
@login_required
def recalculate_performance():
    """Manually recalculate performance metrics"""
    debug_output = ["=== RECALCULATE DEBUG ==="]
    
    try:
        debug_output.append("Attempting import...")
        from cfb_ml_tracking import update_algorithm_performance
        debug_output.append("Import successful")
        
        debug_output.append("Getting weeks...")
        weeks = db.session.query(CFBPredictionLog.week).distinct().all()
        debug_output.append(f"Found weeks: {[w[0] for w in weeks]}")
        
        debug_output.append("Starting performance updates...")
        for week_tuple in weeks:
            week = week_tuple[0]
            debug_output.append(f"Processing week {week}")
            update_algorithm_performance(week)
            debug_output.append(f"Finished week {week}")
        
        debug_output.append("All done successfully!")
        return f"<pre>{'<br>'.join(debug_output)}</pre><br><a href='/admin/ml/prediction_factors'>Check Results</a>"
        
    except Exception as e:
        debug_output.append(f"ERROR: {str(e)}")
        debug_output.append(f"Error type: {type(e)}")
        import traceback
        debug_output.append(f"Traceback: {traceback.format_exc()}")
        return f"<pre>{'<br>'.join(debug_output)}</pre><br><a href='/admin/ml'>Back</a>"


@app.route('/admin/ml/debug_predictions')
@login_required
def debug_predictions():
    """Debug what predictions actually exist"""
    try:
        # Get ALL predictions regardless of filters
        all_preds = CFBPredictionLog.query.all()
        
        # Get first prediction to see its structure
        sample_pred = CFBPredictionLog.query.first()
        
        debug_info = {
            'total_predictions': len(all_preds),
            'sample_prediction_type': type(sample_pred).__name__ if sample_pred else 'None'
        }
        
        if sample_pred:
            # Show available attributes
            debug_info['sample_attributes'] = [attr for attr in dir(sample_pred) if not attr.startswith('_')]
            debug_info['has_automated'] = hasattr(sample_pred, 'automated')
            debug_info['prediction_type'] = getattr(sample_pred, 'prediction_type', 'N/A')
        
        return f"<pre>{json.dumps(debug_info, indent=2, default=str)}</pre><br><a href='/admin/ml'>Back</a>"
        
    except Exception as e:
        return f"Debug Error: {str(e)}<br><a href='/admin/ml'>Back</a>"

@app.route('/admin/ml/create_test_prediction')
@login_required
def create_test_prediction():
    """Create a dummy prediction to test ML dashboard"""
    try:
        test_pred = CFBPredictionLog()
        test_pred.season_year = 2025
        test_pred.week = "1"
        test_pred.home_team = "Alabama"
        test_pred.away_team = "Georgia"
        test_pred.prediction_type = "automated"
        test_pred.predicted_winner = "Alabama"
        test_pred.predicted_margin = 7.0
        test_pred.win_probability = 65.0
        test_pred.confidence_level = "Medium"
        test_pred.game_completed = False
        
        db.session.add(test_pred)
        db.session.commit()
        
        return "Test prediction created! <a href='/admin/ml'>Try ML Dashboard</a>"
        
    except Exception as e:
        return f"Error creating test prediction: {e}"

# Add these routes to your app.py for deleting predictions

@app.route('/admin/ml/delete_week/<week>')
@login_required
def delete_week_predictions(week):
    """Delete all predictions for a specific week"""
    try:
        # Count predictions before deletion
        prediction_count = CFBPredictionLog.query.filter(
            CFBPredictionLog.week == str(week)
        ).count()
        
        if prediction_count == 0:
            flash(f'No predictions found for Week {week}', 'info')
            return redirect(url_for('cfb_ml_dashboard'))
        
        # Delete all predictions for this week
        CFBPredictionLog.query.filter(
            CFBPredictionLog.week == str(week)
        ).delete()
        
        db.session.commit()
        
        flash(f'✅ Deleted {prediction_count} predictions for Week {week}', 'success')
        return redirect(url_for('cfb_ml_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting Week {week} predictions: {str(e)}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))


@app.route('/admin/ml/delete_automated')
@login_required
def delete_all_automated():
    """Delete ALL automated predictions (keep manual ones)"""
    try:
        # Count automated predictions
        automated_count = CFBPredictionLog.query.filter(
            CFBPredictionLog.prediction_type == 'automated'
        ).count()
        
        if automated_count == 0:
            flash('No automated predictions found to delete', 'info')
            return redirect(url_for('cfb_ml_dashboard'))
        
        # Delete all automated predictions
        CFBPredictionLog.query.filter(
            CFBPredictionLog.prediction_type == 'automated'
        ).delete()
        
        db.session.commit()
        
        flash(f'✅ Deleted {automated_count} automated predictions (manual predictions kept)', 'success')
        return redirect(url_for('cfb_ml_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting automated predictions: {str(e)}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))


@app.route('/admin/ml/delete_all')
@login_required
def delete_all_predictions():
    """Delete ALL predictions (manual and automated) - BE CAREFUL!"""
    try:
        # Count all predictions
        total_count = CFBPredictionLog.query.count()
        
        if total_count == 0:
            flash('No predictions found to delete', 'info')
            return redirect(url_for('cfb_ml_dashboard'))
        
        # Delete ALL predictions
        CFBPredictionLog.query.delete()
        
        db.session.commit()
        
        flash(f'⚠️ Deleted ALL {total_count} predictions (manual and automated)', 'warning')
        return redirect(url_for('cfb_ml_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting all predictions: {str(e)}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))


@app.route('/admin/ml/manage_predictions')
@login_required
def manage_predictions():
    """Interface to manage/delete predictions"""
    try:
        # Get prediction counts by week and type
        all_predictions = CFBPredictionLog.query.all()
        
        # Group by week
        weeks_data = {}
        for pred in all_predictions:
            if pred.week not in weeks_data:
                weeks_data[pred.week] = {'manual': 0, 'automated': 0, 'total': 0}
            weeks_data[pred.week][pred.prediction_type] += 1
            weeks_data[pred.week]['total'] += 1
        
        # Sort weeks in descending order (most recent first)
        sorted_weeks = sorted(weeks_data.keys(), key=lambda x: int(x) if x.isdigit() else 999, reverse=True)
        
        # Count totals
        total_manual = len([p for p in all_predictions if p.prediction_type == 'manual'])
        total_automated = len([p for p in all_predictions if p.prediction_type == 'automated'])
        total_predictions = len(all_predictions)
        
        # Organize data for template
        manage_data = {
            'weeks': {week: weeks_data[week] for week in sorted_weeks},
            'totals': {
                'manual': total_manual,
                'automated': total_automated,
                'all': total_predictions
            }
        }
        
        return render_template('manage_predictions.html', 
                             manage_data=manage_data)
        
    except Exception as e:
        flash(f'Error loading manage predictions: {str(e)}', 'error')
        return redirect(url_for('cfb_ml_dashboard'))



@app.route('/remove_game/<int:game_id>', methods=['POST'])
@login_required
def remove_game(game_id):
    """Remove a specific game and update team stats"""
    try:
        # Get the game to remove
        game = Game.query.get_or_404(game_id)
        
        # Store game info before deletion
        home_team = game.home_team
        away_team = game.away_team
        home_score = game.home_score
        away_score = game.away_score
        week = game.week
        is_neutral = game.is_neutral_site
        is_overtime = game.overtime
        
        # FIND AND RESET THE MATCHING SCHEDULED GAME
        scheduled_game = ScheduledGame.query.filter_by(
            week=week,
            completed=True
        ).filter(
            db.or_(
                db.and_(ScheduledGame.home_team == home_team, ScheduledGame.away_team == away_team),
                db.and_(ScheduledGame.home_team == away_team, ScheduledGame.away_team == home_team)
            )
        ).first()
        
        if scheduled_game:
            # Reset the scheduled game back to uncompleted
            scheduled_game.completed = False
            scheduled_game.final_home_score = None
            scheduled_game.final_away_score = None
            scheduled_game.overtime = False
            print(f"✅ Reset scheduled game back to uncompleted: {scheduled_game.home_team} vs {scheduled_game.away_team}")
        
        
        # NEW: Reset ML predictions back to pending
        if CFB_ML_ENABLED:
            reset_prediction_to_pending(home_team, away_team, week)


        # Reverse team stats for both teams
        reverse_team_stats_in_db(home_team, away_team, home_score, away_score, True, is_neutral, is_overtime)
        reverse_team_stats_in_db(away_team, home_team, away_score, home_score, False, is_neutral, is_overtime)
        
        # Remove the game from games table
        db.session.delete(game)
        db.session.commit()
        
        if scheduled_game:
            flash(f'✅ Removed game and reset to scheduled: {home_team} {home_score}-{away_score} {away_team} (Week {week})', 'success')
        else:
            flash(f'✅ Removed game: {home_team} {home_score}-{away_score} {away_team} (Week {week})', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error removing game: {e}', 'error')
    
    return redirect(request.referrer or url_for('admin'))


@app.route('/remove_scheduled_game/<int:scheduled_game_id>', methods=['POST'])
@login_required
def remove_scheduled_game(scheduled_game_id):
    """Remove a specific scheduled game"""
    try:
        # Get the scheduled game to remove
        scheduled_game = ScheduledGame.query.get_or_404(scheduled_game_id)
        
        # Store game info before deletion for the flash message
        home_team = scheduled_game.home_team
        away_team = scheduled_game.away_team
        week = scheduled_game.week
        game_date = scheduled_game.game_date
        
        # Remove the scheduled game
        db.session.delete(scheduled_game)
        db.session.commit()
        
        # Format the flash message
        date_text = f" on {game_date}" if game_date else ""
        flash(f'✅ Removed scheduled game: {home_team} vs {away_team} (Week {week}{date_text})', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error removing scheduled game: {e}', 'error')
    
    # Redirect back to the weekly results page for the same week
    return redirect(url_for('scoreboard', week=scheduled_game.week if 'scheduled_game' in locals() else request.form.get('week', '1')))


def reverse_team_stats_in_db(team, opponent, team_score, opp_score, is_home, is_neutral_site, is_overtime):
    """Reverse the stats changes when removing a game"""
    if team == 'FCS':
        return
    
    team_stats_record = TeamStats.query.filter_by(team_name=team).first()
    if not team_stats_record:
        return
    
    # Reverse win/loss
    if team_score > opp_score:
        team_stats_record.wins = max(0, team_stats_record.wins - 1)
        team_stats_record.margin_of_victory_total = max(0, team_stats_record.margin_of_victory_total - (team_score - opp_score))
        
        # Reverse home/road wins
        if not is_neutral_site:
            if is_home:
                team_stats_record.home_wins = max(0, team_stats_record.home_wins - 1)
            else:
                team_stats_record.road_wins = max(0, team_stats_record.road_wins - 1)
    else:
        team_stats_record.losses = max(0, team_stats_record.losses - 1)
    
    # Reverse points
    team_stats_record.points_for = max(0, team_stats_record.points_for - team_score)
    team_stats_record.points_against = max(0, team_stats_record.points_against - opp_score)
    
    # Remove game from history
    games_list = team_stats_record.games
    # Remove the specific game (match on opponent and scores)
    games_list = [g for g in games_list if not (
        g['opponent'] == opponent and 
        g['team_score'] == team_score and 
        g['opp_score'] == opp_score
    )]
    team_stats_record.games = games_list
    
    db.session.commit()

@app.route('/manage_games')
@login_required
def manage_games():
    """Admin page to manage all games"""
    all_games = Game.query.order_by(Game.date_added.desc()).limit(50).all()
    games_data = [game.to_dict() for game in all_games]
    return render_template('manage_games.html', games=games_data)


def is_fcs_opponent(opponent_name):
    """Check if opponent is FCS"""
    return opponent_name == 'FCS' or opponent_name.upper() == 'FCS'


def save_team_mappings():
    """Save team mappings - DATABASE VERSION (simplified)"""
    # Since team mappings are used during schedule import and are temporary,
    # we can just keep them in memory for the session
    # If you want permanent storage, you'd need a TeamMapping database table
    pass

def load_team_mappings():
    """Load team mappings - DATABASE VERSION"""
    # Team mappings are now handled per-session during schedule import
    return {}

def get_team_suggestions(unknown_team):
    """Get suggestions for unknown team names with variations check"""
    suggestions = []
    unknown_lower = unknown_team.lower().strip()
    
    # Remove common punctuation that might interfere
    unknown_clean = unknown_lower.replace('"', '').replace('(', '').replace(')', '').replace('.', '')
    
    # First, check if the unknown team is a variation of any official team
    variations = {
        # Your full variations dictionary goes here - copy from the previous artifact
        'Alabama': ['Alabama', 'Bama', 'Crimson Tide'],
        'Arkansas': ['Arkansas', 'Ark', 'Razorbacks'],
        'Auburn': ['Auburn', 'Tigers'],
        'Florida': ['Florida', 'UF', 'Gators'],
        'Georgia': ['Georgia', 'UGA', 'Bulldogs'],
        'Kentucky': ['Kentucky', 'UK', 'Wildcats'],
        'LSU': ['LSU', 'Louisiana State', 'Tigers'],
        'Mississippi State': ['Mississippi State', 'MSU', 'Miss State', 'Bulldogs'],
        'Missouri': ['Missouri', 'Mizzou', 'Tigers'],
        'Oklahoma': ['Oklahoma', 'OU', 'Sooners'],
        'Ole Miss': ['Ole Miss', 'Mississippi', 'Rebels'],
        'South Carolina': ['South Carolina', 'Gamecocks'],
        'Tennessee': ['Tennessee', 'Tenn', 'UT', 'Volunteers', 'Vols'],
        'Texas': ['Texas', 'UT', 'Longhorns'],
        'Texas A&M': ['Texas A&M', 'TAMU', 'A&M', 'Aggies', 'Texas AM'],
        'Vanderbilt': ['Vanderbilt', 'Vandy', 'Commodores'],
        'Illinois': ['Illinois', 'Illini', 'Fighting Illini'],
        'Indiana': ['Indiana', 'IU', 'Hoosiers'],
        'Iowa': ['Iowa', 'Hawkeyes'],
        'Maryland': ['Maryland', 'UMD', 'Terrapins', 'Terps'],
        'Michigan': ['Michigan', 'UM', 'Wolverines'],
        'Michigan State': ['Michigan State', 'MSU', 'Mich State', 'Spartans'],
        'Minnesota': ['Minnesota', 'Gophers', 'Golden Gophers'],
        'Nebraska': ['Nebraska', 'Huskers', 'Cornhuskers'],
        'Northwestern': ['Northwestern', 'NU', 'Wildcats'],
        'Ohio State': ['Ohio State', 'OSU', 'tOSU', 'Buckeyes'],
        'Oregon': ['Oregon', 'Ducks'],
        'Penn State': ['Penn State', 'PSU', 'Nittany Lions'],
        'Purdue': ['Purdue', 'Boilermakers'],
        'Rutgers': ['Rutgers', 'RU', 'Scarlet Knights'],
        'UCLA': ['UCLA', 'Bruins'],
        'USC': ['USC', 'Southern Cal', 'Southern California', 'Trojans'],
        'Washington': ['Washington', 'UW', 'Huskies'],
        'Wisconsin': ['Wisconsin', 'Badgers'],
        'Boston College': ['Boston College', 'BC', 'Eagles'],
        'California': ['California', 'Cal', 'Berkeley', 'Golden Bears'],
        'Clemson': ['Clemson', 'Tigers'],
        'Duke': ['Duke', 'Blue Devils'],
        'Florida State': ['Florida State', 'FSU', 'Seminoles'],
        'Georgia Tech': ['Georgia Tech', 'GT', 'Yellow Jackets'],
        'Louisville': ['Louisville', 'Cards', 'Cardinals'],
        'Miami': ['Miami', 'UM', 'Miami (FL)', 'Miami Florida', 'Miami FL', 'Hurricanes', 'The U'],
        'NC State': ['NC State', 'North Carolina State', 'NCSU', 'Wolfpack'],
        'North Carolina': ['North Carolina', 'UNC', 'Tar Heels', 'Carolina'],
        'Pittsburgh': ['Pittsburgh', 'Pitt', 'Panthers'],
        'SMU': ['SMU', 'Southern Methodist', 'Mustangs'],
        'Stanford': ['Stanford', 'Cardinal'],
        'Syracuse': ['Syracuse', 'Cuse', 'Orange'],
        'Virginia': ['Virginia', 'UVA', 'Cavaliers'],
        'Virginia Tech': ['Virginia Tech', 'VT', 'Hokies'],
        'Wake Forest': ['Wake Forest', 'Wake', 'Demon Deacons'],
        'Arizona': ['Arizona', 'Wildcats'],
        'Arizona State': ['Arizona State', 'ASU', 'Sun Devils'],
        'Baylor': ['Baylor', 'Bears'],
        'BYU': ['BYU', 'Brigham Young', 'Cougars'],
        'Cincinnati': ['Cincinnati', 'UC', 'Bearcats'],
        'Colorado': ['Colorado', 'CU', 'Buffaloes', 'Buffs'],
        'Houston': ['Houston', 'UH', 'Cougars'],
        'Iowa State': ['Iowa State', 'ISU', 'Cyclones'],
        'Kansas': ['Kansas', 'KU', 'Jayhawks'],
        'Kansas State': ['Kansas State', 'KSU', 'K-State', 'Wildcats'],
        'Oklahoma State': ['Oklahoma State', 'OSU', 'Cowboys'],
        'TCU': ['TCU', 'Texas Christian', 'Horned Frogs'],
        'Texas Tech': ['Texas Tech', 'TTU', 'Red Raiders'],
        'UCF': ['UCF', 'Central Florida', 'Knights'],
        'Utah': ['Utah', 'Utes'],
        'West Virginia': ['West Virginia', 'WVU', 'Mountaineers'],
        'Oregon State': ['Oregon State', 'OSU', 'Beavers'],
        'Washington State': ['Washington State', 'WSU', 'Cougars'],
        'South Florida': ['South Florida', 'USF', 'Bulls'],
        'UL Monroe': ['UL Monroe', 'ULM', 'Louisiana Monroe', 'Warhawks'],
        'Miami (OH)': ['Miami (OH)', 'Miami Ohio', 'Miami "Ohio"', 'Miami (Ohio)', 'RedHawks'],
        'Western Kentucky': ['Western Kentucky', 'WKU', 'Hilltoppers'],
        'Florida Intl': ['Florida Intl', 'FIU', 'Florida International', 'Panthers'],
        'UCF': ['UCF', 'Central Florida', 'Knights'],
        'TCU': ['TCU', 'Texas Christian', 'Horned Frogs'],
        'LSU': ['LSU', 'Louisiana State', 'Tigers'],
        'BYU': ['BYU', 'Brigham Young', 'Cougars'],
        'SMU': ['SMU', 'Southern Methodist', 'Mustangs'],
        'Texas A&M': ['Texas A&M', 'TAMU', 'A&M', 'Aggies', 'Texas AM'],
    }
    
    # Check variations dictionary - PRIORITY CHECK
    for official_name, variant_list in variations.items():
        for variant in variant_list:
            if unknown_clean == variant.lower():
                suggestions.insert(0, official_name)  # Put exact matches first
                break
            elif unknown_clean in variant.lower() or variant.lower() in unknown_clean:
                suggestions.append(official_name)
    
    # Then look for partial matches in known teams (original logic)
    for team in TEAMS:
        team_lower = team.lower()
        
        # Skip if we already found this team through variations
        if team in suggestions:
            continue
            
        # Contains match (either direction)
        if unknown_clean in team_lower or team_lower in unknown_clean:
            suggestions.append(team)
            continue
            
        # Word-by-word matching for multi-word teams
        unknown_words = unknown_clean.split()
        team_words = team_lower.split()
        
        # Check if any significant words match
        if len(unknown_words) > 0 and len(team_words) > 0:
            word_matches = 0
            for u_word in unknown_words:
                if len(u_word) > 2:  # Only check meaningful words
                    for t_word in team_words:
                        if u_word in t_word or t_word in u_word:
                            word_matches += 1
                            break
            
            # If we matched a good portion of words, suggest it
            if word_matches >= min(len(unknown_words), len(team_words)) * 0.7:
                suggestions.append(team)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_suggestions = []
    for suggestion in suggestions:
        if suggestion not in seen:
            seen.add(suggestion)
            unique_suggestions.append(suggestion)
    
    # Limit to top 5 suggestions
    return unique_suggestions[:5]



def normalize_team_name(team_name):
    """Normalize team names for matching"""
    # Handle common variations
    variations = {
            # SEC
            'Alabama': ['Alabama', 'Bama', 'Crimson Tide'],
            'Arkansas': ['Arkansas', 'Ark', 'Razorbacks'],
            'Auburn': ['Auburn', 'Tigers'],
            'Florida': ['Florida', 'UF', 'Gators'],
            'Georgia': ['Georgia', 'UGA', 'Bulldogs'],
            'Kentucky': ['Kentucky', 'UK', 'Wildcats'],
            'LSU': ['LSU', 'Louisiana State', 'Tigers'],
            'Mississippi State': ['Mississippi State', 'MSU', 'Miss State', 'Bulldogs'],
            'Missouri': ['Missouri', 'Mizzou', 'Tigers'],
            'Oklahoma': ['Oklahoma', 'OU', 'Sooners'],
            'Ole Miss': ['Ole Miss', 'Mississippi', 'Rebels'],
            'South Carolina': ['South Carolina', 'Gamecocks'],
            'Tennessee': ['Tennessee', 'Tenn', 'UT', 'Volunteers', 'Vols'],
            'Texas': ['Texas', 'UT', 'Longhorns'],
            'Texas A&M': ['Texas A&M', 'TAMU', 'A&M', 'Aggies', 'Texas AM'],
            'Vanderbilt': ['Vanderbilt', 'Vandy', 'Commodores'],

            # Big Ten
            'Illinois': ['Illinois', 'Illini', 'Fighting Illini'],
            'Indiana': ['Indiana', 'IU', 'Hoosiers'],
            'Iowa': ['Iowa', 'Hawkeyes'],
            'Maryland': ['Maryland', 'UMD', 'Terrapins', 'Terps'],
            'Michigan': ['Michigan', 'UM', 'Wolverines'],
            'Michigan State': ['Michigan State', 'MSU', 'Mich State', 'Spartans'],
            'Minnesota': ['Minnesota', 'Gophers', 'Golden Gophers'],
            'Nebraska': ['Nebraska', 'Huskers', 'Cornhuskers'],
            'Northwestern': ['Northwestern', 'NU', 'Wildcats'],
            'Ohio State': ['Ohio State', 'OSU', 'tOSU', 'Buckeyes'],
            'Oregon': ['Oregon', 'Ducks'],
            'Penn State': ['Penn State', 'PSU', 'Nittany Lions'],
            'Purdue': ['Purdue', 'Boilermakers'],
            'Rutgers': ['Rutgers', 'RU', 'Scarlet Knights'],
            'UCLA': ['UCLA', 'Bruins'],
            'USC': ['USC', 'Southern Cal', 'Southern California', 'Trojans'],
            'Washington': ['Washington', 'UW', 'Huskies'],
            'Wisconsin': ['Wisconsin', 'Badgers'],

            # ACC
            'Boston College': ['Boston College', 'BC', 'Eagles'],
            'California': ['California', 'Cal', 'Berkeley', 'Golden Bears'],
            'Clemson': ['Clemson', 'Tigers'],
            'Duke': ['Duke', 'Blue Devils'],
            'Florida State': ['Florida State', 'FSU', 'Seminoles'],
            'Georgia Tech': ['Georgia Tech', 'GT', 'Yellow Jackets'],
            'Louisville': ['Louisville', 'Cards', 'Cardinals'],
            'Miami': ['Miami', 'UM', 'Miami (FL)', 'Miami Florida', 'Miami FL', 'Hurricanes', 'The U'],
            'NC State': ['NC State', 'North Carolina State', 'NCSU', 'Wolfpack'],
            'North Carolina': ['North Carolina', 'UNC', 'Tar Heels', 'Carolina'],
            'Pittsburgh': ['Pittsburgh', 'Pitt', 'Panthers'],
            'SMU': ['SMU', 'Southern Methodist', 'Mustangs'],
            'Stanford': ['Stanford', 'Cardinal'],
            'Syracuse': ['Syracuse', 'Cuse', 'Orange'],
            'Virginia': ['Virginia', 'UVA', 'Cavaliers'],
            'Virginia Tech': ['Virginia Tech', 'VT', 'Hokies'],
            'Wake Forest': ['Wake Forest', 'Wake', 'Demon Deacons'],

            # Big 12
            'Arizona': ['Arizona', 'Wildcats'],
            'Arizona State': ['Arizona State', 'ASU', 'Sun Devils'],
            'Baylor': ['Baylor', 'Bears'],
            'BYU': ['BYU', 'Brigham Young', 'Cougars'],
            'Cincinnati': ['Cincinnati', 'UC', 'Bearcats'],
            'Colorado': ['Colorado', 'CU', 'Buffaloes', 'Buffs'],
            'Houston': ['Houston', 'UH', 'Cougars'],
            'Iowa State': ['Iowa State', 'ISU', 'Cyclones'],
            'Kansas': ['Kansas', 'KU', 'Jayhawks'],
            'Kansas State': ['Kansas State', 'KSU', 'K-State', 'Wildcats'],
            'Oklahoma State': ['Oklahoma State', 'OSU', 'Cowboys'],
            'TCU': ['TCU', 'Texas Christian', 'Horned Frogs'],
            'Texas Tech': ['Texas Tech', 'TTU', 'Red Raiders'],
            'UCF': ['UCF', 'Central Florida', 'Knights'],
            'Utah': ['Utah', 'Utes'],
            'West Virginia': ['West Virginia', 'WVU', 'Mountaineers'],

            # Pac-12 (remaining)
            'Oregon State': ['Oregon State', 'OSU', 'Beavers'],
            'Washington State': ['Washington State', 'WSU', 'Cougars'],

            # American Athletic Conference
            'Army': ['Army', 'Black Knights'],
            'Charlotte': ['Charlotte', '49ers'],
            'East Carolina': ['East Carolina', 'ECU', 'Pirates'],
            'Florida Atlantic': ['Florida Atlantic', 'FAU', 'Owls'],
            'Memphis': ['Memphis', 'Tigers'],
            'Navy': ['Navy', 'Midshipmen'],
            'North Texas': ['North Texas', 'UNT', 'Mean Green'],
            'Rice': ['Rice', 'Owls'],
            'South Florida': ['South Florida', 'USF', 'Bulls'],
            'Temple': ['Temple', 'Owls'],
            'Tulane': ['Tulane', 'Green Wave'],
            'Tulsa': ['Tulsa', 'Golden Hurricane'],
            'UAB': ['UAB', 'Alabama Birmingham', 'Blazers'],
            'UTSA': ['UTSA', 'Texas San Antonio', 'Roadrunners'],

            # Conference USA
            'Delaware': ['Delaware', 'Blue Hens'],
            'Florida Intl': ['Florida Intl', 'FIU', 'Florida International', 'Panthers'],
            'Jacksonville State': ['Jacksonville State', 'JSU', 'Gamecocks'],
            'Kennesaw State': ['Kennesaw State', 'Owls'],
            'LA Tech': ['LA Tech', 'Louisiana Tech', 'Bulldogs'],
            'Liberty': ['Liberty', 'Flames'],
            'Middle Tennessee': ['Middle Tennessee', 'MTSU', 'Blue Raiders'],
            'Missouri State': ['Missouri State', 'Bears'],
            'New Mexico St': ['New Mexico St', 'New Mexico State', 'NMSU', 'Aggies'],
            'Sam Houston': ['Sam Houston', 'Sam Houston State', 'SHSU', 'Bearkats'],
            'UTEP': ['UTEP', 'Texas El Paso', 'Miners'],
            'Western Kentucky': ['Western Kentucky', 'WKU', 'Hilltoppers'],

            # MAC
            'Akron': ['Akron', 'Zips'],
            'Ball State': ['Ball State', 'Cardinals'],
            'Bowling Green': ['Bowling Green', 'BGSU', 'Falcons'],
            'Buffalo': ['Buffalo', 'Bulls'],
            'Central Michigan': ['Central Michigan', 'CMU', 'Chippewas'],
            'Eastern Michigan': ['Eastern Michigan', 'EMU', 'Eagles'],
            'Kent State': ['Kent State', 'Golden Flashes'],
            'UMass': ['UMass', 'Massachusetts', 'Minutemen'],
            'Miami (OH)': ['Miami (OH)', 'Miami Ohio', 'Miami "Ohio"', 'Miami (Ohio)', 'RedHawks'],
            'Northern Illinois': ['Northern Illinois', 'NIU', 'Huskies'],
            'Ohio': ['Ohio', 'Bobcats'],
            'Toledo': ['Toledo', 'Rockets'],
            'Western Michigan': ['Western Michigan', 'WMU', 'Broncos'],

            # Mountain West
            'Air Force': ['Air Force', 'Falcons'],
            'Boise State': ['Boise State', 'Broncos'],
            'Colorado State': ['Colorado State', 'CSU', 'Rams'],
            'Fresno State': ['Fresno State', 'Bulldogs'],
            'Hawaii': ['Hawaii', 'Rainbow Warriors'],
            'Nevada': ['Nevada', 'Wolf Pack'],
            'New Mexico': ['New Mexico', 'UNM', 'Lobos'],
            'San Diego State': ['San Diego State', 'SDSU', 'Aztecs'],
            'San Jose State': ['San Jose State', 'SJSU', 'Spartans'],
            'UNLV': ['UNLV', 'Rebels'],
            'Utah State': ['Utah State', 'USU', 'Aggies'],
            'Wyoming': ['Wyoming', 'Cowboys'],

            # Sun Belt
            'Appalachian St': ['Appalachian St', 'Appalachian State', 'App State', 'Mountaineers'],
            'Arkansas State': ['Arkansas State', 'A-State', 'Red Wolves'],
            'Coastal Carolina': ['Coastal Carolina', 'Chanticleers'],
            'Georgia Southern': ['Georgia Southern', 'Eagles'],
            'Georgia State': ['Georgia State', 'Panthers'],
            'James Madison': ['James Madison', 'JMU', 'Dukes'],
            'UL Monroe': ['UL Monroe', 'ULM', 'Louisiana Monroe', 'Warhawks'],
            'Louisiana': ['Louisiana', 'UL', 'Ragin Cajuns', 'Louisiana Lafayette'],
            'Marshall': ['Marshall', 'Thundering Herd'],
            'Old Dominion': ['Old Dominion', 'ODU', 'Monarchs'],
            'South Alabama': ['South Alabama', 'USA', 'Jaguars'],
            'Southern Miss': ['Southern Miss', 'Southern Mississippi', 'USM', 'Golden Eagles'],
            'Texas State': ['Texas State', 'Bobcats'],
            'Troy': ['Troy', 'Trojans'],

            # Independents
            'Connecticut': ['Connecticut', 'UConn', 'Huskies'],
            'Notre Dame': ['Notre Dame', 'ND', 'Fighting Irish'],
        }
    
    for standard_name, variants in variations.items():
        if team_name in variants:
            return standard_name
    
    return team_name

def find_matching_scheduled_game(home_team, away_team, week):
    """Find a scheduled game that matches the completed game"""
    home_normalized = normalize_team_name(home_team)
    away_normalized = normalize_team_name(away_team)
    
    all_scheduled = get_scheduled_games_list()  # 
    for i, scheduled in enumerate(all_scheduled):  # 
        if scheduled['week'] != week or scheduled['completed']:
            continue
            
        sched_home = normalize_team_name(scheduled['home_team'])
        sched_away = normalize_team_name(scheduled['away_team'])
        
        # Check both orientations (home/away might be swapped)
        if ((sched_home == home_normalized and sched_away == away_normalized) or
            (sched_home == away_normalized and sched_away == home_normalized)):
            return i
    
    return None

def get_scheduled_games_list():
    """Get scheduled games from database"""
    try:
        scheduled = ScheduledGame.query.order_by(ScheduledGame.game_date, ScheduledGame.game_time).all()
        return [game.to_dict() for game in scheduled]
    except Exception as e:
        print(f"Error getting scheduled games: {e}")
        return []   


@app.route('/analyze_fcs_games')
@login_required
def analyze_fcs_games():
    """Analyze all FCS games and their impact"""
    fcs_games = []
    
    all_games = get_games_data()  # 
    for game in all_games:  # 
        home_team = game['home_team']
        away_team = game['away_team']
        
        if is_fcs_opponent(home_team) or is_fcs_opponent(away_team):
            # Determine which team beat FCS
            if is_fcs_opponent(away_team):  # Home team beat FCS
                winner = home_team
                winner_score = game['home_score']
                loser_score = game['away_score']
            else:  # Away team beat FCS
                winner = away_team
                winner_score = game['away_score'] 
                loser_score = game['home_score']
            
            # Calculate victory value for this FCS win
            mock_game = {
                'result': 'W',
                'opponent': 'FCS',
                'team_score': winner_score,
                'opp_score': loser_score,
                'home_away': 'Home' if winner == home_team else 'Away'
            }
            victory_value = calculate_victory_value_with_rivalry(mock_game, winner)
            
            fcs_games.append({
                'week': game['week'],
                'winner': winner,
                'score': f"{winner_score}-{loser_score}",
                'margin': winner_score - loser_score,
                'victory_value': victory_value
            })
    
    return render_template_string("""
    <html>
    <head><title>FCS Games Analysis</title></head>
    <body style="font-family: Arial; margin: 40px;">
        <h1>FCS Games Analysis</h1>
        <p>Showing minimal credit given for beating FCS opponents:</p>
        
        <table style="border-collapse: collapse; width: 100%;">
            <tr style="background: #f0f0f0;">
                <th style="border: 1px solid #ddd; padding: 8px;">Week</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Winner</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Score</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Margin</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Victory Value</th>
            </tr>
            {% for game in fcs_games %}
            <tr>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.week }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.winner }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.score }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.margin }}</td>
                <td style="border: 1px solid #ddd; padding: 8px; color: red;">{{ game.victory_value }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <div style="background: #fff3cd; padding: 15px; margin: 20px 0; border-radius: 5px;">
            <h3>FCS Game Penalties Applied:</h3>
            <ul>
                <li>Opponent Quality: 0.5/10 (extremely low)</li>
                <li>No location bonus (road wins vs FCS don't get extra credit)</li>
                <li>Minimal margin bonus (max 0.2 regardless of score)</li>
                <li>No conference bonus</li>
                <li>No rivalry bonus</li>
                <li>Hard cap at 1.0 total victory points</li>
            </ul>
        </div>
        
        <p><a href="/admin">Back to Admin</a></p>
    </body>
    </html>
    """, fcs_games=fcs_games)


# Replace your bowl_projections route with this clean version


@app.route('/bowl_projections')
def bowl_projections():
    """Bowl projections with proper conference tie-ins"""
    cache_key = 'bowl_projections_data'
    
    # Check cache first (5 minute cache)
    if cache_key in performance_cache:
        cached_data, timestamp = performance_cache[cache_key]
        if time.time() - timestamp < 300:  
            return render_template('bowl_projections.html', **cached_data)
    
    try:
        # Get all teams with proper ranking
        all_teams_stats = get_all_team_stats_bulk()
        
        # Find teams with 4+ wins (early season adjustment)
        bowl_eligible = []
        teams_with_games = []
        
        for team in all_teams_stats:
            total_games = team['total_wins'] + team['total_losses']
            if total_games > 0:
                teams_with_games.append(team)
                if team['total_wins'] >= 4:  # Using 4+ for early season
                    bowl_eligible.append(team)
        
        print(f"BOWL DEBUG: Found {len(bowl_eligible)} teams with 4+ wins")
        
        # Generate CFP bracket (top 12 teams)
        cfp_teams = all_teams_stats[:12] if len(all_teams_stats) >= 12 else all_teams_stats
        for i, team in enumerate(cfp_teams):
            team['seed'] = i + 1
        
        cfp_bracket = {
            'first_round_byes': cfp_teams[:4],
            'all_teams': cfp_teams,
            'automatic_qualifiers': cfp_teams[:5],
            'first_round_games': create_simple_first_round_games(cfp_teams),
            'conference_champions': {}
        }
        
        # Remove CFP teams from bowl pool
        cfp_team_names = {team['team'] for team in cfp_teams}
        non_cfp_bowl_eligible = [team for team in bowl_eligible if team['team'] not in cfp_team_names]
        
        print(f"BOWL DEBUG: After removing CFP teams, {len(non_cfp_bowl_eligible)} teams available for bowls")
        
        # Group teams by conference for tie-in assignments
        teams_by_conference = {}
        for team in non_cfp_bowl_eligible:
            conf = team['conference']
            if conf not in teams_by_conference:
                teams_by_conference[conf] = []
            teams_by_conference[conf].append(team)
        
        # Sort teams within each conference by ranking
        for conf in teams_by_conference:
            teams_by_conference[conf].sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        print(f"BOWL DEBUG: Teams by conference:")
        for conf, teams in teams_by_conference.items():
            print(f"  {conf}: {len(teams)} teams")
        
        # Create bowls with proper tie-ins using your BOWL_GAMES data
        bowls_by_tier = create_bowls_with_tieins(teams_by_conference, non_cfp_bowl_eligible)
        
        template_data = {
            'cfp_bracket': cfp_bracket,
            'bowls_by_tier': bowls_by_tier,
            'total_bowl_teams': len(bowl_eligible)
        }
        
        # Cache the result
        performance_cache[cache_key] = (template_data, time.time())
        
        return render_template('bowl_projections.html', **template_data)
        
    except Exception as e:
        print(f"BOWL ERROR: {e}")
        
        # Return with empty but valid structure
        return render_template('bowl_projections.html',
                             cfp_bracket={'first_round_byes': [], 'all_teams': [], 'automatic_qualifiers': [], 'first_round_games': []},
                             bowls_by_tier={'NY6': [], 'Major': [], 'Conference': [], 'G5': [], 'Championship': []},
                             total_bowl_teams=0)

def create_bowls_with_tieins(teams_by_conference, all_available_teams):
    """Create bowls using proper conference tie-ins from BOWL_GAMES"""
    
    # Track which teams have been assigned
    assigned_teams = set()
    
    # Organize bowls by tier
    bowls_by_tier = {'NY6': [], 'Major': [], 'Conference': [], 'G5': [], 'Championship': []}
    
    # Get bowls sorted by selection order and tier
    sorted_bowls = []
    for bowl_id, bowl_info in BOWL_GAMES.items():
        if bowl_info.get('tier') != 'CFP':  # Skip CFP bowls
            sorted_bowls.append((bowl_id, bowl_info))
    
    # Sort by tier priority and selection order
    tier_priority = {'NY6': 1, 'Major': 2, 'Conference': 3, 'G5': 4}
    sorted_bowls.sort(key=lambda x: (
        tier_priority.get(x[1].get('tier', 'G5'), 5),
        x[1].get('selection_order', 999)
    ))
    
    print(f"BOWL DEBUG: Processing {len(sorted_bowls)} bowls")
    
    for bowl_id, bowl_info in sorted_bowls:
        bowl = {
            'name': bowl_info['name'],
            'location': bowl_info['location'],
            'payout': bowl_info['payout'],
            'tie_ins': bowl_info.get('primary_tie_ins', []),
            'teams': []
        }
        
        teams_needed = bowl_info.get('teams', 2)
        tier = bowl_info.get('tier', 'G5')
        
        print(f"BOWL DEBUG: Filling {bowl['name']} (needs {teams_needed} teams)")
        
        # Try to fill based on tie-ins
        for tie_in in bowl_info.get('primary_tie_ins', []):
            if teams_needed <= 0:
                break
            
            print(f"  Looking for {tie_in} team...")
            
            # Find best available team from this conference
            if tie_in in teams_by_conference:
                available_teams = [t for t in teams_by_conference[tie_in] 
                                 if t['team'] not in assigned_teams]
                if available_teams:
                    selected_team = available_teams[0]  # Best team from conference
                    bowl['teams'].append({
                        'team': selected_team['team'],
                        'wins': selected_team['total_wins'],
                        'losses': selected_team['total_losses'],
                        'conference': selected_team['conference']
                    })
                    assigned_teams.add(selected_team['team'])
                    teams_needed -= 1
                    print(f"    Assigned {selected_team['team']} ({selected_team['conference']})")
                else:
                    print(f"    No available teams from {tie_in}")
            else:
                print(f"    No teams from {tie_in} conference")
        
        # Fill remaining spots with best available at-large teams
        while teams_needed > 0:
            best_available = None
            best_rating = -999
            
            for team in all_available_teams:
                if team['team'] not in assigned_teams and team['adjusted_total'] > best_rating:
                    best_available = team
                    best_rating = team['adjusted_total']
            
            if best_available:
                bowl['teams'].append({
                    'team': best_available['team'],
                    'wins': best_available['total_wins'],
                    'losses': best_available['total_losses'],
                    'conference': best_available['conference']
                })
                assigned_teams.add(best_available['team'])
                teams_needed -= 1
                print(f"    Assigned {best_available['team']} (at-large)")
            else:
                print(f"    No more teams available")
                break
        
        # Add bowl to appropriate tier if it has teams
        if bowl['teams']:
            bowls_by_tier[tier].append(bowl)
            print(f"  Added {bowl['name']} to {tier} with {len(bowl['teams'])} teams")
        
        # Stop if we've assigned most teams
        if len(assigned_teams) >= min(60, len(all_available_teams)):
            break
    
    print(f"BOWL DEBUG: Final bowl counts:")
    for tier, bowls in bowls_by_tier.items():
        print(f"  {tier}: {len(bowls)} bowls")
    
    return bowls_by_tier

def create_simple_first_round_games(cfp_teams):
    """Create simple first round matchups"""
    if len(cfp_teams) < 12:
        return []
    
    return [
        {'higher_seed': cfp_teams[4], 'lower_seed': cfp_teams[11], 'game_num': 1},
        {'higher_seed': cfp_teams[5], 'lower_seed': cfp_teams[10], 'game_num': 2},
        {'higher_seed': cfp_teams[6], 'lower_seed': cfp_teams[9], 'game_num': 3},
        {'higher_seed': cfp_teams[7], 'lower_seed': cfp_teams[8], 'game_num': 4},
    ]


@app.route('/historical')
def historical_rankings():
    # Historical rankings feature disabled since we removed the global variable
    flash('Historical rankings feature is currently disabled. Use archived seasons instead.', 'info')
    return redirect(url_for('archived_seasons'))

@app.route('/reload_data')
@login_required
def reload_data():
    """Force reload all data in production"""
    try:
        load_data()  # This calls all your load functions
        return f"Reloaded! Scheduled games: {len(scheduled_games)}, Games: {len(games_data)}"
    except Exception as e:
        return f"Error reloading: {e}"


@app.route('/reset_data', methods=['POST'])
@login_required
def reset_data():
    """Reset all data - DATABASE VERSION"""
    try:
        # Clear all games from database
        Game.query.delete()
        
        # Clear all team stats from database
        TeamStats.query.delete()
        
        # NEW: Clear all scheduled games from database
        ScheduledGame.query.delete()
        
        # Commit the deletions
        db.session.commit()
        
        flash('All data has been reset!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting data: {e}', 'error')
    
    return redirect(url_for('admin'))


def save_weekly_snapshot(week_number):
    """Save current rankings as a weekly snapshot - DATABASE VERSION"""
    # Weekly snapshots are now handled through the season archive system
    try:
        flash(f'Weekly snapshots have been replaced with the season archive system. Use "Archive Current Season" instead.', 'info')
        return True
    except Exception as e:
        print(f"Error creating weekly snapshot: {e}")
        return False

def save_historical_data():
    """Save historical rankings - DATABASE VERSION (simplified)"""
    # Historical data is now handled through the season archive system
    pass

def load_historical_data():
    """Load historical rankings - DATABASE VERSION"""
    # Historical data is now handled through the season archive system
    return []


# Season Archive System

@app.route('/archive_season', methods=['POST'])
@login_required  
def archive_season():
    """Archive the current season - FINAL VERSION"""
    try:
        season_name = request.form.get('season_name', '').strip()
        if not season_name:
            flash('Please enter a season name!', 'error')
            return redirect(url_for('admin'))
        
        # Check database instead of global games_data
        total_games = Game.query.count()
        if total_games == 0:
            flash('No games to archive! Add some games first.', 'error')
            return redirect(url_for('admin'))
        
        # Archive the season 
        if archive_current_season_db(season_name):
            flash(f'✅ Season "{season_name}" archived successfully! ({total_games} games processed)', 'success')
        else:
            flash('❌ Error archiving season. Please try again.', 'error')
            
    except Exception as e:
        flash(f'Error archiving season: {e}', 'error')
    
    # Always return a response
    return redirect(url_for('admin'))

def archive_current_season_db(season_name):
    """Archive the current season's data to database - FINAL VERSION"""
    try:
        # Get current comprehensive stats for final rankings from database
        final_rankings = []
        for conf_name, teams in CONFERENCES.items():
            for team in teams:
                team_record = TeamStats.query.filter_by(team_name=team).first()
                if team_record and (team_record.wins + team_record.losses) > 0:
                    stats = calculate_comprehensive_stats(team)
                    stats['team'] = team
                    stats['conference'] = conf_name
                    final_rankings.append(stats)
        
        # Sort by Adjusted Total (highest first) 
        final_rankings.sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        # Add rank numbers
        for rank, team_data in enumerate(final_rankings, 1):
            team_data['final_rank'] = rank
        
        # Get all games and team stats from database
        games_data_db = get_games_data()
        
        # Get all team stats from database
        team_stats_dict = {}
        all_team_stats = TeamStats.query.all()
        for team_record in all_team_stats:
            team_stats_dict[team_record.team_name] = team_record.to_dict()
        
        # Get scheduled games from database
        scheduled_games_db = get_scheduled_games_list()
        
        # Create complete season archive data
        complete_archive_data = {
            'games_data': games_data_db,
            'team_stats': team_stats_dict,
            'scheduled_games': scheduled_games_db,
            'final_rankings': final_rankings[:25]  # Top 25
        }
        
        # Create season summary
        champion = final_rankings[0]['team'] if final_rankings else 'No Champion'
        total_weeks = len(set(game['week'] for game in games_data_db)) if games_data_db else 0
        
        # Save to database
        from models import ArchivedSeason
        archived_season = ArchivedSeason(
            season_name=season_name,
            total_games=len(games_data_db),
            total_teams=len(final_rankings),
            champion=champion,
            total_weeks=total_weeks,
            archive_data_json=json.dumps(complete_archive_data)
        )
        
        db.session.add(archived_season)
        db.session.commit()
        
        print(f"✅ Season '{season_name}' archived to database with:")
        print(f"   - {len(games_data_db)} games")
        print(f"   - {len(final_rankings)} teams")
        print(f"   - Champion: {champion}")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error archiving season: {e}")
        return False

def load_archived_seasons():
    """Load list of all archived seasons from database"""
    try:
        from models import ArchivedSeason
        archived_seasons = ArchivedSeason.query.all()
        
        seasons_list = [{
            'filename': str(season.id),
            'season_name': season.season_name,
            'archived_date': season.archived_date.strftime('%Y-%m-%d %H:%M:%S'),
            'total_games': season.total_games,
            'total_teams': season.total_teams,
            'champion': season.champion,
            'total_weeks': season.total_weeks
        } for season in archived_seasons]
        
        # Sort by season name in descending order (assuming names are years like "2025", "2024")
        # This will put 2025 before 2024
        seasons_list.sort(key=lambda x: x['season_name'], reverse=True)
        
        return seasons_list
        
    except Exception as e:
        print(f"Error loading archived seasons: {e}")
        return []

def load_archived_season_details(season_id):
    """Load complete details of a specific archived season"""
    try:
        from models import ArchivedSeason
        season = ArchivedSeason.query.get(int(season_id))
        
        if not season:
            return None
            
        # Parse the archive data
        archive_data = json.loads(season.archive_data_json) if season.archive_data_json else {}
        
        # Format data for existing template
        season_data = {
            'season_name': season.season_name,
            'archived_date': season.archived_date.strftime('%Y-%m-%d %H:%M:%S'),
            'total_games': season.total_games,
            'total_teams_with_games': season.total_teams,
            'final_rankings': archive_data.get('final_rankings', []),
            'season_summary': {
                'total_weeks': season.total_weeks,
                'conferences_represented': len(set(team['conference'] for team in archive_data.get('final_rankings', [])[:25])),
                'champion': archive_data.get('final_rankings', [{}])[0] if archive_data.get('final_rankings') else None
            }
        }
        
        return season_data
            
    except Exception as e:
        print(f"Error loading archived season details: {e}")
        return None

def safe_reset_season():
    """Reset current season data - DATABASE ONLY VERSION"""
    try:
        # Clear all database tables
        Game.query.delete()
        TeamStats.query.delete()
        ScheduledGame.query.delete()
        
        # If you have other tables to clear, add them here:
        # ArchivedSeason.query.delete()  # Only if you want to delete archives too
        
        db.session.commit()
        
        # Clear global variables (if still used anywhere)
        global team_mappings, historical_rankings
        team_mappings = {}
        historical_rankings = []
        
        print("🗑️ Current season data reset successfully from database")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error resetting season data: {e}")
        return False



@app.route('/health')
def health_check():
    """Health check endpoint for load balancers"""
    return {'status': 'healthy'}, 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session.permanent = True
            next_page = request.args.get('next')
            return redirect(next_page or url_for('rankings'))
        else:
            flash('Invalid credentials!', 'error')
    
    return render_template('login.html', next=request.args.get('next'))

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('rankings')) 

@app.route('/archived_seasons')
def archived_seasons():
    """View list of all archived seasons - USES YOUR EXISTING TEMPLATE"""
    archived_seasons_list = load_archived_seasons()
    return render_template('archived_seasons.html', archived_seasons=archived_seasons_list)



@app.route('/archived_season/<filename>')
def view_archived_season(filename):
    """View details of a specific archived season - USES YOUR EXISTING TEMPLATE"""
    season_data = load_archived_season_details(filename)
    
    if not season_data:
        flash('Archived season not found!', 'error')
        return redirect(url_for('archived_seasons'))
    
    return render_template('archived_season_detail.html', season_data=season_data)



@app.route('/delete_archived_season', methods=['POST'])
@login_required
def delete_archived_season():
    """Delete a specific archived season"""
    try:
        season_id = request.form.get('filename', '').strip()  # Template sends 'filename' but it's actually ID
        confirm_text = request.form.get('delete_confirm', '').strip()
        
        if confirm_text != 'DELETE':
            flash('Delete confirmation failed. Please type DELETE exactly.', 'error')
            return redirect(url_for('archived_seasons'))
        
        # Find and delete the archived season
        from models import ArchivedSeason
        season = ArchivedSeason.query.get(int(season_id))
        
        if not season:
            flash('Archived season not found!', 'error')
            return redirect(url_for('archived_seasons'))
        
        season_name = season.season_name
        db.session.delete(season)
        db.session.commit()
        
        flash(f'✅ Archived season "{season_name}" deleted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting archived season: {e}', 'error')
    
    return redirect(url_for('archived_seasons'))





@app.route('/safe_reset_data', methods=['POST'])
@login_required
def safe_reset_data():
    """Safely reset data with confirmation - DATABASE ONLY VERSION"""
    try:
        confirm_text = request.form.get('reset_confirm', '').strip()
        if confirm_text != 'RESET':
            flash('Reset confirmation failed. Please type RESET exactly.', 'error')
            return redirect(url_for('admin'))
        
        # Count current data
        game_count = Game.query.count()
        team_count = TeamStats.query.count()
        scheduled_count = ScheduledGame.query.count()
        
        if game_count > 0 or scheduled_count > 0:
            flash(f'⚠️ You have {game_count} games, {team_count} teams, and {scheduled_count} scheduled games. Are you sure you want to delete everything?', 'warning')
        
        # Clear all data from database
        Game.query.delete()
        TeamStats.query.delete()
        ScheduledGame.query.delete()
        
        # Commit the deletions
        db.session.commit()
        
        flash(f'🗑️ Successfully deleted {game_count} games, {team_count} teams, and {scheduled_count} scheduled games from database!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting data: {e}', 'error')
    
    return redirect(url_for('admin'))


@app.route('/import_csv', methods=['GET', 'POST'])
@login_required
def import_csv():
    """Import final rankings from CSV file"""
    if request.method == 'GET':
        return render_template('import_csv.html')
    
    try:
        season_name = request.form.get('season_name', '').strip()
        if not season_name:
            flash('Please enter a season name!', 'error')
            return redirect(url_for('import_csv'))
        
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            flash('Please select a CSV file!', 'error')
            return redirect(url_for('import_csv'))
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('Please select a CSV file!', 'error')
            return redirect(url_for('import_csv'))
        
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file!', 'error')
            return redirect(url_for('import_csv'))
        
        # Read and parse CSV
        import csv
        import io
        
        # Read file content
        file_content = file.read().decode('utf-8')
        csv_data = list(csv.DictReader(io.StringIO(file_content)))
        
        if not csv_data:
            flash('CSV file is empty!', 'error')
            return redirect(url_for('import_csv'))
        
        # Validate required columns
        required_cols = ['Rank', 'Team', 'Conference', 'Wins', 'Losses', 'Adjusted_Total']
        missing_cols = [col for col in required_cols if col not in csv_data[0].keys()]
        if missing_cols:
            flash(f'Missing required columns: {", ".join(missing_cols)}', 'error')
            return redirect(url_for('import_csv'))
        
        # INITIALIZE final_rankings here to avoid NameError
        final_rankings = []
        
        # Process the data
        for row in csv_data:
            try:
                team_data = {
                    'final_rank': int(row['Rank']),
                    'team': row['Team'].strip(),
                    'conference': row['Conference'].strip(),
                    'total_wins': int(row['Wins']),
                    'total_losses': int(row['Losses']),
                    'adjusted_total': float(row['Adjusted_Total']),
                    'p4_wins': int(row.get('P4_Wins', 0)) if row.get('P4_Wins', '').strip() else 0,
                    'g5_wins': int(row.get('G5_Wins', 0)) if row.get('G5_Wins', '').strip() else 0,
                    'strength_of_schedule': 0.500,  # Default value
                    'points_fielded': 0,  # Not available from CSV
                    'points_allowed': 0,  # Not available from CSV
                    'margin_of_victory': 0,  # Not available from CSV
                    'point_differential': 0,  # Not available from CSV
                    'home_wins': 0,  # Not available from CSV
                    'road_wins': 0,  # Not available from CSV
                    'opp_w': 0,  # Not available from CSV
                    'opp_l': 0,  # Not available from CSV
                    'opp_wl_differential': 0,  # Not available from CSV
                    'totals': float(row['Adjusted_Total'])  # Use adjusted total as totals
                }
                final_rankings.append(team_data)
            except (ValueError, KeyError) as e:
                flash(f'Error processing row {row.get("Rank", "?")}: {e}', 'error')
                return redirect(url_for('import_csv'))
        
        # Sort by rank to ensure proper order
        final_rankings.sort(key=lambda x: x['final_rank'])
        
        # Create complete archive data
        complete_archive_data = {
            'games_data': [],  # No individual games from CSV
            'team_stats': {},  # No detailed stats from CSV
            'scheduled_games': [],  # No scheduled games from CSV
            'final_rankings': final_rankings
        }
        
        # Save to database using ArchivedSeason model
        champion = final_rankings[0]['team'] if final_rankings else 'No Champion'
        
        from models import ArchivedSeason
        archived_season = ArchivedSeason(
            season_name=season_name,
            total_games=0,  # Unknown from CSV import
            total_teams=len(final_rankings),
            champion=champion,
            total_weeks=0,  # Unknown from CSV import
            archive_data_json=json.dumps(complete_archive_data)
        )
        
        db.session.add(archived_season)
        db.session.commit()
        
        flash(f'✅ Successfully imported {len(final_rankings)} teams for "{season_name}"!', 'success')
        return redirect(url_for('archived_seasons'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error importing CSV: {e}', 'error')
        return redirect(url_for('import_csv'))


if __name__ == '__main__':
    
    
    # Load existing data
    load_data()
    
    print("College Football Ranking App")
    print("=" * 40)
    print("Templates created successfully!")
    print("Features:")
    print("- Add games with automatic P4/G5 classification")
    print("- Neutral site games (no home/road win credit)")
    print("- Weekly results page to review games by week")
    print("- Comprehensive statistics and ranking calculation")
    print("- Sortable table columns (click headers to sort)")
    print("- All FBS conferences included + FCS option")
    print("- Team detail pages with statistics")
    print("- Conference-organized dropdowns")
    print("- Data persistence (automatically saved)")
    print("- Reset data option in navigation")
    print("- Responsive Bootstrap UI")
    print(f"\nTotal teams: {len(TEAMS)} across {len(CONFERENCES)} conferences")
    print("Conferences included:")
    for conf_name, teams in CONFERENCES.items():
        classification = ""
        if conf_name in P4_CONFERENCES:
            classification = " (P4)"
        elif conf_name in G5_CONFERENCES:
            classification = " (G5)"
        elif conf_name == "Independent":
            classification = " (Notre Dame=P4, Connecticut=G5, FCS=None)"
        print(f"  - {conf_name}: {len(teams)} teams{classification}")
    print("\nP4 Conferences: ACC, Big Ten, Big XII, Pac 12, SEC, Notre Dame")
    print("G5 Conferences: American, Conference USA, MAC, Mountain West, Sun Belt, Connecticut")
    print("None Classification: FCS (for non-P4/G5 games)")
    print("Ready with your custom ranking formula!")
    print("\nHow game types work:")
    print("- Each team's game type reflects their OPPONENT's classification")
    print("- Example: Boston College (P4) vs Kent State (G5)")
    print("  → Boston College gets 'G5' game type (playing G5 opponent)")
    print("  → Kent State gets 'P4' game type (playing P4 opponent)")
    print("- Neutral site games: Neither team gets home/road win credit")
    print("  → Useful for bowl games, conference championships, etc.")
    print("\nData will be automatically saved to games_data.json and team_stats.json")
    print("Starting Flask development server...")


    if CFB_ML_ENABLED:
        try:
            with app.app_context():
                cfb_ml_tracking.setup_cfb_ml_tracking()
                print("✅ CFB ML tracking initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing CFB ML tracking: {e}")
            CFB_ML_ENABLED = False
    
    print("College Football Ranking App")
    # ... rest of your existing startup code ...
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False)
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False)
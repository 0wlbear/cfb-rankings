from flask import Flask, render_template, request, redirect, url_for, flash, session, render_template_string
import json
from datetime import datetime
from collections import defaultdict
from functools import wraps
import os


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.permanent_session_lifetime = 86400  # Session lasts 24 hours

# Data directory for persistence
DATA_DIR = os.environ.get('DATA_DIR', './data')
os.makedirs(DATA_DIR, exist_ok=True)

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
    'UAB': '2429',
    'UTSA': '2902',
    
    # Conference USA
    'Delaware': '48',
    'Florida Intl': '2229',
    'Jacksonville State': '55',
    'Kennesaw State': '2390',
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

def get_team_logo_url(team_name):
    """Get ESPN logo URL for a team"""
    team_id = TEAM_LOGOS.get(team_name)
    if team_id:
        return f"https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png"
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
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')

def is_admin():
    """Check if user is logged in as admin"""
    return session.get('admin_logged_in', False)

@app.context_processor
def inject_user():
    return dict(is_admin=is_admin)

@app.context_processor
def inject_logo_function():
    return dict(get_team_logo_url=get_team_logo_url)

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
    """Save game data and team stats to JSON files"""
    try:
        # Save games data
        games_file = os.path.join(DATA_DIR, 'games_data.json')
        with open(games_file, 'w') as f:
            json.dump(games_data, f, indent=2)
        
        # Convert team_stats defaultdict to regular dict for JSON serialization
        team_stats_dict = {}
        for team, stats in team_stats.items():
            team_stats_dict[team] = dict(stats)
        
        stats_file = os.path.join(DATA_DIR, 'team_stats.json')
        with open(stats_file, 'w') as f:
            json.dump(team_stats_dict, f, indent=2)
        
        print("Data saved successfully!")
    except Exception as e:
        print(f"Error saving data: {e}")

def load_data():
    """Load game data and team stats from JSON files"""
    global games_data, team_stats
    try:
        # Load games data
        try:
            games_file = os.path.join(DATA_DIR, 'games_data.json')
            with open(games_file, 'r') as f:
                games_data = json.load(f)
            print(f"Loaded {len(games_data)} games from saved data")
        except FileNotFoundError:
            print("No saved games data found, starting fresh")
            games_data = []
        
        # Load team stats
        try:
            stats_file = os.path.join(DATA_DIR, 'team_stats.json')
            with open(stats_file, 'r') as f:
                saved_stats = json.load(f)
            
            # Convert back to defaultdict
            team_stats = defaultdict(lambda: {
                'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0,
                'p4_wins': 0, 'p4_losses': 0, 'g5_wins': 0, 'g5_losses': 0,
                'home_wins': 0, 'road_wins': 0, 'margin_of_victory_total': 0,
                'games': []
            })
            
            for team, stats in saved_stats.items():
                team_stats[team] = stats
            
            print(f"Loaded stats for {len(saved_stats)} teams")
        except FileNotFoundError:
            print("No saved team stats found, starting fresh")

        # Load historical data
        load_historical_data()    
            
    except Exception as e:
        print(f"Error loading data: {e}")
        print("Starting with fresh data")


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
    """Generate 12-team CFP bracket based on current rankings"""
    # Get all teams ranked by adjusted total
    all_teams = []
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            all_teams.append(stats)
    
    # Sort by adjusted total (highest first)
    all_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    # Get conference champions (excluding Pac 12 and Independent)
    champions = get_conference_champions()
    
    # Step 1: Get the top 5 ranked conference champions (automatic qualifiers)
    automatic_qualifiers = []
    for team in all_teams:
        if team['conference'] in champions and champions[team['conference']]['team'] == team['team']:
            automatic_qualifiers.append(team)
            if len(automatic_qualifiers) == 5:
                break
    
    # Step 2: Get the top 12 teams overall (this will include some/all auto-qualifiers)
    top_12_teams = all_teams[:12].copy()
    
    # Step 3: Ensure all 5 auto-qualifiers are in the playoff
    # If any auto-qualifier is not in top 12, replace the lowest-ranked non-auto-qualifier
    auto_qualifier_names = {team['team'] for team in automatic_qualifiers}
    
    # Find auto-qualifiers not in top 12
    missing_auto_qualifiers = [team for team in automatic_qualifiers if team['team'] not in [t['team'] for t in top_12_teams]]
    
    # Replace lowest-ranked non-auto-qualifiers with missing auto-qualifiers
    for missing_team in missing_auto_qualifiers:
        # Find the lowest-ranked team in top_12 that's not an auto-qualifier
        for i in range(11, -1, -1):  # Start from bottom of top 12
            if top_12_teams[i]['team'] not in auto_qualifier_names:
                top_12_teams[i] = missing_team
                break
    
    # Step 4: Sort the final 12 teams and assign seeds 1-12
    playoff_teams = top_12_teams
    playoff_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    for i, team in enumerate(playoff_teams):
        team['seed'] = i + 1
    
    # Step 5: First Round Byes go to TOP 4 TEAMS (seeds 1-4)
    first_round_byes = playoff_teams[:4]
    
    # At-Large Display: Seeds 5-12
    at_large_display = playoff_teams[4:]
    
    # Generate bracket structure
    bracket = {
        'first_round_byes': first_round_byes,  # TOP 4 TEAMS OVERALL (regardless of champion status)
        'first_round_games': [
            {'higher_seed': playoff_teams[4], 'lower_seed': playoff_teams[11], 'game_num': 1},  # 5 vs 12
            {'higher_seed': playoff_teams[5], 'lower_seed': playoff_teams[10], 'game_num': 2},  # 6 vs 11
            {'higher_seed': playoff_teams[6], 'lower_seed': playoff_teams[9], 'game_num': 3},   # 7 vs 10
            {'higher_seed': playoff_teams[7], 'lower_seed': playoff_teams[8], 'game_num': 4},   # 8 vs 9
        ],
        'all_teams': playoff_teams,
        'automatic_qualifiers': automatic_qualifiers,  # Top 5 ranked conference champions
        'at_large_display': at_large_display,          # Seeds 5-12
        'conference_champions': champions
    }
    
    return bracket

def calculate_comprehensive_stats(team_name):
    """Calculate all comprehensive statistics for a team"""
    stats = team_stats[team_name]
    
    # Basic stats
    total_games = stats['wins'] + stats['losses']
    if total_games == 0:
        return {
            'points_fielded': 0, 'points_allowed': 0, 'margin_of_victory': 0,
            'point_differential': 0, 'home_wins': 0, 'road_wins': 0,
            'p4_wins': 0, 'g5_wins': 0, 'opp_w': 0, 'opp_l': 0,
            'strength_of_schedule': 0, 'opp_wl_differential': 0,
            'totals': 0, 'total_wins': 0, 'total_losses': 0, 'adjusted_total': 0
        }
    
    # Calculate opponent wins/losses and SoS
    opponent_total_wins = 0
    opponent_total_losses = 0
    opponent_total_games = 0
    
    for game in stats['games']:
        opponent = game['opponent']
        if opponent in team_stats:
            opp_stats = team_stats[opponent]
            opp_wins = opp_stats['wins']
            opp_losses = opp_stats['losses']
            opponent_total_wins += opp_wins
            opponent_total_losses += opp_losses
            opponent_total_games += (opp_wins + opp_losses)
    
    # Strength of Schedule (Average Opponent Win Percentage)
    strength_of_schedule = opponent_total_wins / opponent_total_games if opponent_total_games > 0 else 0
    
    # Point Differential
    point_differential = stats['points_for'] - stats['points_against']
    
    # Opponent W/L Differential
    opp_wl_differential = opponent_total_wins - opponent_total_losses
    
    # Totals calculation: =(sum(((MoV*0.1)*0.05),(Total Losses*-1.5),((Point Differential*0.1)*0.05),(Home Win*0.1), (Road Win*0.2), (P4 Win), (G5 Win*0.75),Opponent W/L Differential))
    totals = (
        ((stats['margin_of_victory_total'] * 0.1) * 0.05) +
        (stats['losses'] * -1.5) +
        ((point_differential * 0.1) * 0.05) +
        (stats['home_wins'] * 0.1) +
        (stats['road_wins'] * 0.2) +
        (stats['p4_wins'] * 1) +
        (stats['g5_wins'] * 0.75) +
        opp_wl_differential
    )
    
    # Adjusted Total: =((Totals+(SoS*0.4))
    adjusted_total = totals + (strength_of_schedule * 0.4)
    
    return {
        'points_fielded': stats['points_for'],
        'points_allowed': stats['points_against'],
        'margin_of_victory': stats['margin_of_victory_total'],
        'point_differential': point_differential,
        'home_wins': stats['home_wins'],
        'road_wins': stats['road_wins'],
        'p4_wins': stats['p4_wins'],
        'g5_wins': stats['g5_wins'],
        'opp_w': opponent_total_wins,
        'opp_l': opponent_total_losses,
        'strength_of_schedule': round(strength_of_schedule, 3),
        'opp_wl_differential': opp_wl_differential,
        'totals': round(totals, 2),
        'total_wins': stats['wins'],
        'total_losses': stats['losses'],
        'adjusted_total': round(adjusted_total, 2)
    }

def update_team_stats(team, opponent, team_score, opp_score, team_game_type, is_home, is_neutral_site=False):
    """Update team statistics after a game"""
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
            
        # Track P4/G5 wins
        if team_game_type == 'P4':
            team_stats[team]['p4_wins'] += 1
        elif team_game_type == 'G5':
            team_stats[team]['g5_wins'] += 1
    else:
        team_stats[team]['losses'] += 1
        if team_game_type == 'P4':
            team_stats[team]['p4_losses'] += 1
        elif team_game_type == 'G5':
            team_stats[team]['g5_losses'] += 1
    
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
    
    # Add game to history
    team_stats[team]['games'].append({
        'opponent': opponent,
        'team_score': team_score,
        'opp_score': opp_score,
        'game_type': team_game_type,
        'result': 'W' if team_score > opp_score else 'L',
        'home_away': location
    })

def analyze_common_opponents(team1_name, team2_name):
    """Analyze how both teams performed against common opponents"""
    team1_games = team_stats[team1_name]['games']
    team2_games = team_stats[team2_name]['games']
    
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
    games = team_stats[team_name]['games']
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
    team1_games = team_stats[team1_name]['games']
    
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

def predict_matchup(team1_name, team2_name, location='neutral'):
    """Comprehensive matchup prediction"""
    team1_stats = calculate_comprehensive_stats(team1_name)
    team2_stats = calculate_comprehensive_stats(team2_name)
    
    # Base prediction from adjusted totals
    base_diff = team1_stats['adjusted_total'] - team2_stats['adjusted_total']
    predicted_margin = base_diff * 2.5  # Scale factor to convert to points
    
    # Factor adjustments
    adjustments = {}
    total_adjustment = 0
    
    # 1. Common opponents
    common_analysis = analyze_common_opponents(team1_name, team2_name)
    if common_analysis['has_common']:
        common_adj = common_analysis['advantage'] * 0.3  # Weight common opponents
        adjustments['Common Opponents'] = round(common_adj, 1)
        total_adjustment += common_adj
    
    # 2. Recent form
    team1_form = calculate_recent_form(team1_name)
    team2_form = calculate_recent_form(team2_name)
    form_diff = team1_form['avg_margin'] - team2_form['avg_margin']
    form_adj = form_diff * 0.2  # Weight recent form
    adjustments['Recent Form'] = round(form_adj, 1)
    total_adjustment += form_adj
    
    # 3. Conference context (P4 vs G5 adjustment)
    team1_conf = get_team_conference(team1_name)
    team2_conf = get_team_conference(team2_name)
    
    conf_adj = 0
    if team1_conf in P4_CONFERENCES and team2_conf in G5_CONFERENCES:
        conf_adj = 3  # P4 team gets 3-point boost vs G5
        adjustments['Conference Level'] = 3.0
    elif team2_conf in P4_CONFERENCES and team1_conf in G5_CONFERENCES:
        conf_adj = -3  # G5 team penalized 3 points vs P4
        adjustments['Conference Level'] = -3.0
    
    total_adjustment += conf_adj
    
    # 4. Home field advantage
    if location == 'team1_home':
        hfa_adj = 3.0
        adjustments['Home Field'] = 3.0
        total_adjustment += hfa_adj
    elif location == 'team2_home':
        hfa_adj = -3.0
        adjustments['Home Field'] = -3.0
        total_adjustment += hfa_adj
    
    # Final prediction
    final_margin = predicted_margin + total_adjustment
    
    # Calculate win probability (rough approximation)
    win_prob = 50 + (final_margin * 2.5)  # Each point = ~2.5% win prob
    win_prob = max(5, min(95, win_prob))  # Cap between 5-95%
    
    return {
        'base_margin': round(predicted_margin, 1),
        'adjustments': adjustments,
        'final_margin': round(final_margin, 1),
        'win_probability': round(win_prob, 1),
        'winner': team1_name if final_margin > 0 else team2_name,
        'confidence': 'High' if abs(final_margin) > 10 else 'Medium' if abs(final_margin) > 4 else 'Low'
    }

@app.route('/compare')
def team_compare():
    """Team comparison page"""
    return render_template('team_compare.html', conferences=CONFERENCES)

@app.route('/compare_teams', methods=['POST'])
def compare_teams():
    """Process team comparison"""
    team1 = request.form['team1']
    team2 = request.form['team2']
    location = request.form.get('location', 'neutral')
    
    if team1 == team2:
        flash('Please select two different teams!', 'error')
        return redirect(url_for('team_compare'))
    
    # Get comprehensive stats
    team1_stats = calculate_comprehensive_stats(team1)
    team2_stats = calculate_comprehensive_stats(team2)
    
    # Run all analyses
    prediction = predict_matchup(team1, team2, location)
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
        'prediction': prediction,
        'common_opponents': common_opponents,
        'team1_form': team1_form,
        'team2_form': team2_form,
        'style_matchup': style_matchup,
        'h2h_history': h2h_history,
        'location': location
    }
    
    return render_template('comparison_results.html', **comparison_data)




@app.route('/create_snapshot', methods=['POST'])
@login_required
def create_snapshot():
    try:
        week_name = request.form.get('week_name', f"Week_{len(historical_rankings) + 1}")
        save_weekly_snapshot(week_name)
        flash(f'Snapshot "{week_name}" created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating snapshot: {e}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/admin')
@login_required
def admin():
    # Create comprehensive stats table for all teams (full data)
    comprehensive_stats = []
    
    # Add all teams from all conferences
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            comprehensive_stats.append(stats)
    
    # Sort by Adjusted Total (highest first)
    comprehensive_stats.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    return render_template('admin.html', comprehensive_stats=comprehensive_stats, recent_games=games_data[-10:])

@app.route('/team/<team_name>')
def team_detail(team_name):
    if team_name not in team_stats:
        flash('Team not found!', 'error')
        return redirect(url_for('public_rankings'))
    
    stats = team_stats[team_name]
    comprehensive_stats = calculate_comprehensive_stats(team_name)
    
    return render_template('team_detail.html', 
                         team_name=team_name, 
                         stats=stats, 
                         adjusted_total=comprehensive_stats['adjusted_total'])


@app.route('/cfp_bracket')
def cfp_bracket():
    """Display current CFP bracket projection"""
    bracket = generate_cfp_bracket()
    return render_template('cfp_bracket.html', bracket=bracket)   


@app.route('/public')
@app.route('/')
def public_rankings():
    # Create comprehensive stats table for all teams (same as index)
    comprehensive_stats = []
    
    # Add all teams from all conferences
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            comprehensive_stats.append(stats)
    
    # Sort by Adjusted Total (highest first)
    comprehensive_stats.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    return render_template('public.html', comprehensive_stats=comprehensive_stats)   

@app.route('/')
def index():
    # Create comprehensive stats table for all teams
    comprehensive_stats = []
    
    # Add all teams from all conferences
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            comprehensive_stats.append(stats)
    
    # Sort by Adjusted Total (highest first)
    comprehensive_stats.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    return render_template('index.html', comprehensive_stats=comprehensive_stats, recent_games=games_data[-10:])

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
            home_game_type = request.form['home_game_type']
            away_game_type = request.form['away_game_type']
            is_neutral_site = 'neutral_site' in request.form
            
            # Validate that teams are different
            if home_team == away_team:
                flash('Teams must be different!', 'error')
                return redirect(url_for('add_game', selected_week=week))
            
            # Add game to data
            game = {
                'week': week,
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'home_game_type': home_game_type,
                'away_game_type': away_game_type,
                'is_neutral_site': is_neutral_site,
                'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            games_data.append(game)
            
            # Update team statistics
            update_team_stats(home_team, away_team, home_score, away_score, home_game_type, True, is_neutral_site)
            update_team_stats(away_team, home_team, away_score, home_score, away_game_type, False, is_neutral_site)
            
            # Save data after adding game
            save_data()

            # Remember the selected week for next time
            session['last_selected_week'] = week
            
            location_text = " (Neutral Site)" if is_neutral_site else ""
            flash(f'Game added: {home_team} {home_score} - {away_score} {away_team}{location_text}', 'success')
            return redirect(url_for('add_game'))
            
        except ValueError:
            flash('Please enter valid scores (numbers only)', 'error')
            return redirect(url_for('add_game'))
    
    # Create team classification data for JavaScript
    team_classifications = {}
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            team_classifications[team] = get_auto_game_type(team)
    
    # Get the selected week from URL parameter (if any)
    selected_week = request.args.get('selected_week') or session.get('last_selected_week', '')
    return render_template('add_game.html', conferences=CONFERENCES, weeks=WEEKS, game_types=GAME_TYPES, team_classifications=team_classifications, recent_games=games_data[-10:], selected_week=selected_week)

@app.route('/historical')
@login_required
def historical_rankings():
    if len(historical_rankings) < 2:
        flash('Need at least 2 weekly snapshots to show movement', 'info')
        return redirect(url_for('admin'))
    
    # Get the two most recent snapshots
    current_week = historical_rankings[-1]
    previous_week = historical_rankings[-2]
    
    # Calculate movement for each team
    movement_data = []
    
    # Create lookup for previous week rankings
    prev_rankings = {team['team']: team['rank'] for team in previous_week['rankings']}
    
    for team in current_week['rankings']:
        team_name = team['team']
        current_rank = team['rank']
        previous_rank = prev_rankings.get(team_name, None)
        
        if previous_rank:
            movement = previous_rank - current_rank  # Positive = moved up
            movement_data.append({
                'team': team_name,
                'conference': team['conference'],
                'current_rank': current_rank,
                'previous_rank': previous_rank,
                'movement': movement,
                'wins': team['wins'],
                'losses': team['losses'],
                'adjusted_total': team['adjusted_total']
            })
        else:
            # New team in rankings
            movement_data.append({
                'team': team_name,
                'conference': team['conference'],
                'current_rank': current_rank,
                'previous_rank': None,
                'movement': None,
                'wins': team['wins'],
                'losses': team['losses'],
                'adjusted_total': team['adjusted_total']
            })
    
    # Sort by current rank
    movement_data.sort(key=lambda x: x['current_rank'])
    
    return render_template('historical.html', 
                         movement_data=movement_data,
                         current_week=current_week,
                         previous_week=previous_week)

@app.route('/weekly_results')
@app.route('/weekly_results/<week>')
def weekly_results(week=None):
    # Get all unique weeks from games data
    weeks_with_games = sorted(set(game['week'] for game in games_data), key=lambda x: (
        # Sort by numeric value if it's a number, otherwise by string
        int(x) if x.isdigit() else (100 if x == 'Bowls' else 101 if x == 'CFP' else 999)
    ))
    
    # If no week specified, default to the most recent week with games
    if not week and weeks_with_games:
        week = weeks_with_games[-1]
    elif not week:
        week = '1'  # Default to week 1 if no games exist
    
    # Get games for the selected week
    week_games = [game for game in games_data if game['week'] == week]
    
    # Sort games by date added (most recent first)
    week_games.sort(key=lambda x: x['date_added'], reverse=True)
    
    return render_template('weekly_results.html', 
                         selected_week=week, 
                         weeks_with_games=weeks_with_games,
                         week_games=week_games,
                         all_weeks=WEEKS)

@app.route('/reset_data', methods=['POST'])
@login_required
def reset_data():
    """Reset all data - useful for testing or starting over"""
    global games_data, team_stats, historical_rankings
    games_data = []
    team_stats = defaultdict(lambda: {
        'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0,
        'p4_wins': 0, 'p4_losses': 0, 'g5_wins': 0, 'g5_losses': 0,
        'home_wins': 0, 'road_wins': 0, 'margin_of_victory_total': 0,
        'games': []
    })
    historical_rankings = []
    
    # Delete saved files
    try:
        games_file = os.path.join(DATA_DIR, 'games_data.json')
        stats_file = os.path.join(DATA_DIR, 'team_stats.json')
        historical_file = os.path.join(DATA_DIR, 'historical_rankings.json')
        
        if os.path.exists(games_file):
            os.remove(games_file)
        if os.path.exists(stats_file):
            os.remove(stats_file)
        if os.path.exists(historical_file):
            os.remove(historical_file)
        flash('All data has been reset!', 'success')
    except Exception as e:
        flash(f'Error resetting data: {e}', 'error')
    
    return redirect(url_for('admin'))

    # Historical rankings storage
historical_rankings = []

def save_weekly_snapshot(week_number):
    """Save current rankings as a weekly snapshot"""
    # Create comprehensive stats table
    comprehensive_stats = []
    
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            comprehensive_stats.append(stats)
    
    # Sort by Adjusted Total (highest first)
    comprehensive_stats.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    # Create snapshot with rankings
    snapshot = {
        'week': week_number,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'rankings': []
    }
    
    for rank, team_data in enumerate(comprehensive_stats, 1):
        snapshot['rankings'].append({
            'rank': rank,
            'team': team_data['team'],
            'conference': team_data['conference'],
            'wins': team_data['total_wins'],
            'losses': team_data['total_losses'],
            'adjusted_total': team_data['adjusted_total']
        })
    
    # Add to historical data
    historical_rankings.append(snapshot)
    
    # Save to file
    save_historical_data()
    print(f"📸 Weekly snapshot saved for Week {week_number}")

def save_historical_data():
    """Save historical rankings to JSON file"""
    try:
        historical_file = os.path.join(DATA_DIR, 'historical_rankings.json')
        with open(historical_file, 'w') as f:
            json.dump(historical_rankings, f, indent=2)
    except Exception as e:
        print(f"Error saving historical data: {e}")

def load_historical_data():
    """Load historical rankings from JSON file"""
    global historical_rankings
    try:
        historical_file = os.path.join(DATA_DIR, 'historical_rankings.json')
        with open(historical_file, 'r') as f:
            historical_rankings = json.load(f)
        print(f"Loaded {len(historical_rankings)} historical snapshots")
    except FileNotFoundError:
        print("No historical data found, starting fresh")
        historical_rankings = []
    except Exception as e:
        print(f"Error loading historical data: {e}")
        historical_rankings = []


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
            return redirect(next_page or url_for('public_rankings'))
        else:
            flash('Invalid credentials!', 'error')
    
    return render_template('login.html', next=request.args.get('next'))

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('public_rankings'))    



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
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False)
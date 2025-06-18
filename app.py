from flask import Flask, render_template, request, redirect, url_for, flash, session
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

# Admin password (you can change this)
ADMIN_PASSWORD = "cfb2025admin"

def is_admin():
    """Check if user is logged in as admin"""
    return session.get('admin_logged_in', False)

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
            
    except Exception as e:
        print(f"Error loading data: {e}")
        print("Starting with fresh data")

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
    selected_week = request.args.get('selected_week', '')
    return render_template('add_game.html', conferences=CONFERENCES, weeks=WEEKS, game_types=GAME_TYPES, team_classifications=team_classifications, recent_games=games_data[-10:], selected_week=selected_week)

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
def reset_data():
    """Reset all data - useful for testing or starting over"""
    global games_data, team_stats
    games_data = []
    team_stats = defaultdict(lambda: {
        'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0,
        'p4_wins': 0, 'p4_losses': 0, 'g5_wins': 0, 'g5_losses': 0,
        'home_wins': 0, 'road_wins': 0, 'margin_of_victory_total': 0,
        'games': []
    })
    
    # Delete saved files
    import os
    try:
        games_file = os.path.join(DATA_DIR, 'games_data.json')
        stats_file = os.path.join(DATA_DIR, 'team_stats.json')

        if os.path.exists(games_file):
            os.remove(games_file)
        if os.path.exists(stats_file):
            os.remove(stats_file)
        flash('All data has been reset!', 'success')
    except Exception as e:
        flash(f'Error resetting data: {e}', 'error')
    
    return redirect(url_for('index'))

@app.route('/team/<team_name>')
def team_detail(team_name):
    if team_name not in team_stats:
        flash('Team not found!', 'error')
        return redirect(url_for('index'))
    
    stats = team_stats[team_name]
    comprehensive_stats = calculate_comprehensive_stats(team_name)
    
    return render_template('team_detail.html', 
                         team_name=team_name, 
                         stats=stats, 
                         adjusted_total=comprehensive_stats['adjusted_total'])
@app.route('/health')
def health_check():
    """Health check endpoint for load balancers"""
    return {'status': 'healthy'}, 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session.permanent = True
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid password!', 'error')
    
    return render_template('login.html', next=request.args.get('next'))

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('public_rankings'))    

def create_templates():
    """Create all HTML template files"""
    import os
    os.makedirs('templates', exist_ok=True)
    
    # Base template
    base_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}College Football Rankings{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .navbar-brand { font-weight: bold; }
        .rating-high { color: #28a745; font-weight: bold; }
        .rating-medium { color: #ffc107; font-weight: bold; }
        .rating-low { color: #dc3545; font-weight: bold; }
        .sortable-header { cursor: pointer; user-select: none; }
        .sortable-header:hover { background-color: #f8f9fa; }
        .sort-indicator { margin-left: 5px; opacity: 0.5; }
        
        /* Searchable team input styling */
        input[list] {
            background-image: url("data:image/svg+xml;charset=UTF-8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='%23666' d='M8 10l4-4H4l4 4z'/></svg>");
            background-repeat: no-repeat;
            background-position: right 8px center;
            background-size: 12px;
            padding-right: 30px;
        }
        
        input[list]:focus {
            background-image: url("data:image/svg+xml;charset=UTF-8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='%23007bff' d='M8 6l-4 4h8l-4-4z'/></svg>");
        }
        
        /* Invalid team input styling */
        .is-invalid {
            border-color: #dc3545;
            background-color: #f8d7da;
        }
        
        .is-invalid:focus {
            border-color: #dc3545;
            box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25);
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">2025 CFB Rankings</a>
            <div class="navbar-nav">
                <a class="nav-link" href="{{ url_for('index') }}">Rankings</a>
                <a class="nav-link" href="{{ url_for('add_game') }}">Add Game</a>
                <a class="nav-link" href="{{ url_for('weekly_results') }}">Weekly Results</a>
            </div>
            <div class="navbar-nav ms-auto">
                <button class="btn btn-outline-light btn-sm" onclick="confirmReset()">Reset Data</button>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </div>
    
    <!-- Hidden form for reset data -->
    <form id="resetForm" method="POST" action="{{ url_for('reset_data') }}" style="display: none;">
    </form>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Table sorting functionality
        function sortTable(columnIndex, isNumeric = false) {
            const table = document.getElementById('statsTable');
            const tbody = table.getElementsByTagName('tbody')[0];
            const rows = Array.from(tbody.getElementsByTagName('tr'));
            
            // Get current header and determine sort direction BEFORE clearing classes
            const currentHeader = table.getElementsByTagName('th')[columnIndex];
            const currentlyAscending = currentHeader.classList.contains('sort-asc');
            const currentlyDescending = currentHeader.classList.contains('sort-desc');
            
            // Determine new sort direction
            let isAscending;
            if (!currentlyAscending && !currentlyDescending) {
                // First click - default to descending for most columns, ascending for text
                isAscending = !isNumeric;
            } else if (currentlyAscending) {
                // Currently ascending, switch to descending
                isAscending = false;
            } else {
                // Currently descending, switch to ascending
                isAscending = true;
            }
            
            // Clear all sort indicators
            const headers = table.getElementsByTagName('th');
            for (let header of headers) {
                header.classList.remove('sort-asc', 'sort-desc');
                const indicator = header.querySelector('.sort-indicator');
                if (indicator) indicator.textContent = '';
            }
            
            // Set new sort indicator
            const indicator = currentHeader.querySelector('.sort-indicator');
            if (indicator) {
                indicator.textContent = isAscending ? '↑' : '↓';
                currentHeader.classList.add(isAscending ? 'sort-asc' : 'sort-desc');
            }
            
            // Sort rows
            rows.sort((a, b) => {
                let aVal = a.getElementsByTagName('td')[columnIndex].textContent.trim();
                let bVal = b.getElementsByTagName('td')[columnIndex].textContent.trim();
                
                if (isNumeric) {
                    aVal = parseFloat(aVal) || 0;
                    bVal = parseFloat(bVal) || 0;
                    return isAscending ? aVal - bVal : bVal - aVal;
                } else {
                    return isAscending ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                }
            });
            
            // Re-append sorted rows and update rank numbers
            rows.forEach((row, index) => {
                row.getElementsByTagName('td')[0].textContent = index + 1;
                tbody.appendChild(row);
            });
        }
        
        // Reset data confirmation
        function confirmReset() {
            if (confirm('Are you sure you want to reset all data? This will delete all games and statistics. This action cannot be undone.')) {
                document.getElementById('resetForm').submit();
            }
        }
    </script>
</body>
</html>"""

    # Index template
    index_html = """{% extends "base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-10">
        <h2>Comprehensive Team Statistics</h2>
        <p class="text-muted">Click column headers to sort</p>
        <div class="table-responsive">
            <table class="table table-striped table-sm" id="statsTable">
                <thead>
                    <tr>
                        <th class="sortable-header" onclick="sortTable(0, true)">Rank<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(1)">Team<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(2)">Conf<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(3, true)">PF<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(4, true)">PA<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(5, true)">MoV<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(6, true)">PD<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(7, true)">HW<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(8, true)">RW<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(9, true)">P4W<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(10, true)">G5W<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(11, true)">Opp W<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(12, true)">Opp L<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(13, true)">SoS<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(14, true)">Opp W/L Diff<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(15, true)">Totals<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(16, true)">Total W<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(17, true)">Total L<span class="sort-indicator"></span></th>
                        <th class="sortable-header" onclick="sortTable(18, true)">Adj Total<span class="sort-indicator">↓</span></th>
                    </tr>
                </thead>
                <tbody>
                    {% for team in comprehensive_stats %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td style="white-space: nowrap; min-width: 120px;">
                            <a href="{{ url_for('team_detail', team_name=team.team) }}">
                                {{ team.team }}
                            </a>
                        </td>
                        <td>
                            {% set badge_class = {
                                'ACC': 'primary',
                                'Big Ten': 'success',
                                'Big XII': 'warning text-dark',
                                'Pac 12': 'info',
                                'SEC': 'danger',
                                'Independent': 'secondary',
                                'American': 'dark',
                                'Conference USA': 'light text-dark',
                                'MAC': 'primary',
                                'Mountain West': 'success',
                                'Sun Belt': 'warning text-dark'
                            }.get(team.conference, 'secondary') %}
                            <span class="badge bg-{{ badge_class }}">
                                {{ team.conference }}
                            </span>
                        </td>
                        <td>{{ team.points_fielded }}</td>
                        <td>{{ team.points_allowed }}</td>
                        <td>{{ team.margin_of_victory }}</td>
                        <td>{{ team.point_differential }}</td>
                        <td>{{ team.home_wins }}</td>
                        <td>{{ team.road_wins }}</td>
                        <td>{{ team.p4_wins }}</td>
                        <td>{{ team.g5_wins }}</td>
                        <td>{{ team.opp_w }}</td>
                        <td>{{ team.opp_l }}</td>
                        <td>{{ team.strength_of_schedule }}</td>
                        <td>{{ team.opp_wl_differential }}</td>
                        <td><strong>{{ team.totals }}</strong></td>
                        <td>{{ team.total_wins }}</td>
                        <td>{{ team.total_losses }}</td>
                        <td class="text-primary"><strong>{{ team.adjusted_total }}</strong></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="col-md-2">
        <!-- Top 25 Rankings -->
        <div class="mb-4">
            <h5 class="text-center">
                <span class="badge bg-primary">Top 25</span>
            </h5>
            <div class="card">
                <div class="card-body p-1">
                    {% for team in comprehensive_stats[:25] %}
                        <div class="d-flex justify-content-between align-items-center py-1 px-2 {% if loop.index <= 4 %}bg-success bg-opacity-25{% elif loop.index <= 12 %}bg-warning bg-opacity-25{% endif %} {% if not loop.last %}border-bottom{% endif %}">
                            <div class="flex-grow-1">
                                <small class="fw-bold">{{ loop.index }}.</small>
                                <a href="{{ url_for('team_detail', team_name=team.team) }}" class="text-decoration-none ms-1">
                                    <small class="fw-bold">{{ team.team }}</small>
                                </a>
                                <br>
                                <small class="text-muted ms-3">{{ team.total_wins }}-{{ team.total_losses }}</small>
                            </div>
                            <div>
                                <small class="text-primary fw-bold">{{ team.adjusted_total }}</small>
                            </div>
                        </div>
                    {% endfor %}
                </div>
                <div class="card-footer p-1 text-center">
                    <small class="text-muted">
                        <span class="badge bg-success me-1" style="font-size: 0.6em;">CFP</span>
                        <span class="badge bg-warning text-dark" style="font-size: 0.6em;">At-Large</span>
                    </small>
                </div>
            </div>
        </div>
        
        <!-- Recent Games -->
        <h6>Recent Games</h6>
        {% if recent_games %}
            <div class="list-group">
                {% for game in recent_games[:5] %}
                <div class="list-group-item p-2">
                    <small class="text-muted">Week {{ game.week }}{% if game.get('is_neutral_site') %} - N{% endif %}</small><br>
                    <small class="fw-bold">{{ game.home_team }} {{ game.home_score }}-{{ game.away_score }} {{ game.away_team }}</small>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <p class="text-muted small">No games yet.</p>
        {% endif %}
    </div>
</div>
{% endblock %}"""

    # Add game template
    add_game_html = """{% extends "base.html" %}

{% block title %}Add Game - College Football Rankings{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <h2>Add New Game</h2>
        <p class="text-muted">Game types are automatically set based on opponent classification. Type team names to search or click dropdown arrow to browse.</p>
        
        <form method="POST">
            <!-- Recent Games Display -->
            {% if recent_games %}
            <div class="alert alert-info mb-4">
                <h6><i class="fas fa-info-circle"></i> Recent Games Added:</h6>
                <div class="small">
                    {% for game in recent_games[:3] %}
                        <div>{{ game.home_team }} {{ game.home_score }} - {{ game.away_score }} {{ game.away_team }} (Week {{ game.week }}){% if game.get('is_neutral_site') %} - Neutral{% endif %}</div>
                    {% endfor %}
                    {% if recent_games|length > 3 %}
                        <div class="text-muted">... and {{ recent_games|length - 3 }} more</div>
                    {% endif %}
                </div>
            </div>
            {% endif %}
            <div class="row mb-3">
                <div class="col-md-6">
                    <label for="week" class="form-label">Week</label>
                    <select class="form-select" id="week" name="week" required>
                        <option value="">Select Week</option>
                        {% for week in weeks %}
                            <option value="{{ week }}" {% if week == selected_week %}selected{% endif %}>{{ week }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-6 d-flex align-items-end">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="neutral_site" name="neutral_site" onchange="updateNeutralSiteLabels()">
                        <label class="form-check-label" for="neutral_site">
                            <strong>Neutral Site Game</strong><br>
                            <small class="text-muted">Neither team gets home/road win credit</small>
                        </label>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header bg-success text-white">
                            <h5 class="mb-0" id="home_team_header">Home Team</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label for="home_team" class="form-label">Team</label>
                              <input type="text" class="form-control" id="home_team" name="home_team" 
       list="team_list" placeholder="Type to search or click to browse..." 
       onchange="updateGameTypes()" required>
<datalist id="team_list">
    {% for conf_name, teams in conferences.items() %}
        <!-- Optgroup simulation with disabled options -->
        <option disabled>--- {{ conf_name }} ---</option>
        {% for team in teams %}
            <option value="{{ team }}">{{ team }} ({{ conf_name }})</option>
        {% endfor %}
    {% endfor %}
</datalist>
                            </div>
                            
                            <div class="mb-3">
                                <label for="home_score" class="form-label">Score</label>
                                <input type="number" class="form-control" id="home_score" name="home_score" min="0" required>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Game Type for Home Team</label>
                                <div id="home_game_type_display" class="mb-2">
                                    <span class="badge bg-secondary">Select both teams first</span>
                                </div>
                                <div>
                                    {% for game_type in game_types %}
                                    <div class="form-check">
                                        <input class="form-check-input" type="radio" name="home_game_type" id="home_{{ game_type }}" value="{{ game_type }}" required>
                                        <label class="form-check-label" for="home_{{ game_type }}">
                                            {{ game_type }}
                                        </label>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0" id="away_team_header">Away Team</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label for="away_team" class="form-label">Team</label>
                                <input type="text" class="form-control" id="away_team" name="away_team" 
                                       list="team_list" placeholder="Type to search or click to browse..." 
                                       onchange="updateGameTypes()" required>
                            </div>
                            
                            <div class="mb-3">
                                <label for="away_score" class="form-label">Score</label>
                                <input type="number" class="form-control" id="away_score" name="away_score" min="0" required>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Game Type for Away Team</label>
                                <div id="away_game_type_display" class="mb-2">
                                    <span class="badge bg-secondary">Select both teams first</span>
                                </div>
                                <div>
                                    {% for game_type in game_types %}
                                    <div class="form-check">
                                        <input class="form-check-input" type="radio" name="away_game_type" id="away_{{ game_type }}" value="{{ game_type }}" required>
                                        <label class="form-check-label" for="away_{{ game_type }}">
                                            {{ game_type }}
                                        </label>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="mt-4 text-center">
                <button type="submit" class="btn btn-primary btn-lg">Add Game</button>
                <a href="{{ url_for('index') }}" class="btn btn-secondary btn-lg">View Rankings</a>
                <a href="{{ url_for('weekly_results') }}" class="btn btn-outline-secondary btn-lg">Weekly Results</a>
            </div>
        </form>
    </div>
</div>

<script>
// Team classifications data
const teamClassifications = {{ team_classifications | tojson }};

// Create array of valid team names for validation
const validTeams = Object.keys(teamClassifications);

function validateTeamInput(inputElement) {
    const teamName = inputElement.value.trim();
    if (teamName && !validTeams.includes(teamName)) {
        inputElement.setCustomValidity('Please select a valid team from the list');
        inputElement.classList.add('is-invalid');
    } else {
        inputElement.setCustomValidity('');
        inputElement.classList.remove('is-invalid');
    }
}

function updateGameTypes() {
    const homeTeamInput = document.getElementById('home_team');
    const awayTeamInput = document.getElementById('away_team');
    const homeTeam = homeTeamInput.value.trim();
    const awayTeam = awayTeamInput.value.trim();
    
    // Validate team inputs
    validateTeamInput(homeTeamInput);
    validateTeamInput(awayTeamInput);
    
    const homeDisplay = document.getElementById('home_game_type_display');
    const awayDisplay = document.getElementById('away_game_type_display');
    
    // Clear previous selections
    const homeRadios = document.querySelectorAll('input[name="home_game_type"]');
    const awayRadios = document.querySelectorAll('input[name="away_game_type"]');
    homeRadios.forEach(radio => radio.checked = false);
    awayRadios.forEach(radio => radio.checked = false);
    
    if (homeTeam && awayTeam && teamClassifications[homeTeam] && teamClassifications[awayTeam]) {
        // Home team's game type = what level the away team is
        const homeGameType = teamClassifications[awayTeam];
        // Away team's game type = what level the home team is  
        const awayGameType = teamClassifications[homeTeam];
        
        // Update displays
        updateGameTypeDisplay('home', homeGameType, awayTeam);
        updateGameTypeDisplay('away', awayGameType, homeTeam);
        
        // Auto-select radio buttons
        const homeRadio = document.getElementById('home_' + homeGameType);
        const awayRadio = document.getElementById('away_' + awayGameType);
        
        if (homeRadio) homeRadio.checked = true;
        if (awayRadio) awayRadio.checked = true;
        
    } else {
        homeDisplay.innerHTML = '<span class="badge bg-secondary">Select both teams first</span>';
        awayDisplay.innerHTML = '<span class="badge bg-secondary">Select both teams first</span>';
    }
}

function updateGameTypeDisplay(side, gameType, opponent) {
    const displayElement = document.getElementById(side + '_game_type_display');
    
    let badgeClass = 'bg-secondary';
    let explanation = '';
    
    if (gameType === 'P4') {
        badgeClass = 'bg-primary';
        explanation = `Playing P4 team (${opponent})`;
    } else if (gameType === 'G5') {
        badgeClass = 'bg-success';
        explanation = `Playing G5 team (${opponent})`;
    } else if (gameType === 'None') {
        badgeClass = 'bg-warning text-dark';
        explanation = `Playing other team (${opponent})`;
    }
    
    displayElement.innerHTML = `<span class="badge ${badgeClass}">${gameType} Game</span><br><small class="text-muted">${explanation}</small>`;
}

function updateNeutralSiteLabels() {
    const neutralSite = document.getElementById('neutral_site').checked;
    const homeHeader = document.getElementById('home_team_header');
    const awayHeader = document.getElementById('away_team_header');
    
    if (neutralSite) {
        homeHeader.innerHTML = 'Team 1 <small class="text-light">(Neutral Site)</small>';
        awayHeader.innerHTML = 'Team 2 <small class="text-light">(Neutral Site)</small>';
    } else {
        homeHeader.innerHTML = 'Home Team';
        awayHeader.innerHTML = 'Away Team';
    }
}

// Clear form after successful game addition (if there's a success message)
document.addEventListener('DOMContentLoaded', function() {
    const successAlert = document.querySelector('.alert-success');
    if (successAlert) {
        // Preserve the selected week
        const currentWeek = document.getElementById('week').value;
        
        // Clear form fields EXCEPT week
        document.getElementById('home_team').value = '';
        document.getElementById('away_team').value = '';
        document.getElementById('home_score').value = '';
        document.getElementById('away_score').value = '';
        document.getElementById('neutral_site').checked = false;
        
        // Restore week selection
        document.getElementById('week').value = currentWeek;
        
        // Clear game type displays
        document.getElementById('home_game_type_display').innerHTML = '<span class="badge bg-secondary">Select both teams first</span>';
        document.getElementById('away_game_type_display').innerHTML = '<span class="badge bg-secondary">Select both teams first</span>';
        
        // Clear radio buttons
        const homeRadios = document.querySelectorAll('input[name="home_game_type"]');
        const awayRadios = document.querySelectorAll('input[name="away_game_type"]');
        homeRadios.forEach(radio => radio.checked = false);
        awayRadios.forEach(radio => radio.checked = false);
        
        // Reset headers
        updateNeutralSiteLabels();
        
        // Focus on home team input for next entry
        document.getElementById('home_team').focus();
    }
    
    // Add event listeners for team input validation
    document.getElementById('home_team').addEventListener('input', function() {
        updateGameTypes();
    });
    
    document.getElementById('away_team').addEventListener('input', function() {
        updateGameTypes();
    });
});
</script>
{% endblock %}"""

    # Team detail template
    team_detail_html = """{% extends "base.html" %}

{% block title %}{{ team_name }} - College Football Rankings{% endblock %}

{% block content %}
<div class="row">
    <div class="col-md-8">
        <h2>{{ team_name }}</h2>
        
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">Adj Total</h5>
                        <h3 class="text-primary">{{ adjusted_total }}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">Overall Record</h5>
                        <h4>{{ stats.wins }}-{{ stats.losses }}</h4>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">P4 Record</h5>
                        <h4>{{ stats.p4_wins }}-{{ stats.p4_losses }}</h4>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">G5 Record</h5>
                        <h4>{{ stats.g5_wins }}-{{ stats.g5_losses }}</h4>
                    </div>
                </div>
            </div>
        </div>
        
        <h3>Game History</h3>
        {% if stats.games %}
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Result</th>
                            <th>Opponent</th>
                            <th>Score</th>
                            <th>Type</th>
                            <th>Location</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for game in stats.games %}
                        <tr>
                            <td>
                                <span class="badge bg-{{ 'success' if game.result == 'W' else 'danger' }}">
                                    {{ game.result }}
                                </span>
                            </td>
                            <td>{{ game.opponent }}</td>
                            <td>{{ game.team_score }}-{{ game.opp_score }}</td>
                            <td>{{ game.game_type }}</td>
                            <td>{{ game.home_away }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
            <p class="text-muted">No games recorded yet.</p>
        {% endif %}
    </div>
    
    <div class="col-md-4">
        <div class="card">
            <div class="card-header">
                <h5>Statistics</h5>
            </div>
            <div class="card-body">
                <p><strong>Total Points For:</strong> {{ stats.points_for }}</p>
                <p><strong>Total Points Against:</strong> {{ stats.points_against }}</p>
                <p><strong>Point Differential:</strong> {{ stats.points_for - stats.points_against }}</p>
                {% if stats.wins + stats.losses > 0 %}
                    <p><strong>Avg Points Per Game:</strong> {{ "%.1f"|format(stats.points_for / (stats.wins + stats.losses)) }}</p>
                    <p><strong>Avg Points Allowed:</strong> {{ "%.1f"|format(stats.points_against / (stats.wins + stats.losses)) }}</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<div class="mt-3">
    <a href="{{ url_for('index') }}" class="btn btn-primary">Back to Rankings</a>
</div>
{% endblock %}"""

    # Weekly results template
    weekly_results_html = """{% extends "base.html" %}

{% block title %}Weekly Results - College Football Rankings{% endblock %}

{% block content %}
<div class="row">
    <div class="col-md-12">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Weekly Results</h2>
            <div>
                <label for="week_selector" class="form-label me-2">Select Week:</label>
                <select class="form-select d-inline-block w-auto" id="week_selector" onchange="changeWeek()">
                    {% for week_option in all_weeks %}
                        <option value="{{ week_option }}" {% if week_option == selected_week %}selected{% endif %}>
                            Week {{ week_option }}
                        </option>
                    {% endfor %}
                </select>
            </div>
        </div>
        
        {% if weeks_with_games %}
            <div class="mb-3">
                <div class="btn-group" role="group" aria-label="Week navigation">
                    {% for week_with_games in weeks_with_games %}
                        <a href="{{ url_for('weekly_results', week=week_with_games) }}" 
                           class="btn btn-{{ 'primary' if week_with_games == selected_week else 'outline-primary' }} btn-sm">
                            {{ week_with_games }}
                        </a>
                    {% endfor %}
                </div>
            </div>
        {% endif %}
        
        <div class="card">
            <div class="card-header">
                <h4 class="mb-0">
                    Week {{ selected_week }} Results
                    {% if week_games %}
                        <span class="badge bg-secondary ms-2">{{ week_games|length }} game{{ 's' if week_games|length != 1 else '' }}</span>
                    {% endif %}
                </h4>
            </div>
            <div class="card-body">
                {% if week_games %}
                    <div class="row">
                        {% for game in week_games %}
                            <div class="col-md-6 col-lg-4 mb-3">
                                <div class="card h-100">
                                    <div class="card-body">
                                        <div class="text-center mb-2">
                                            {% if game.get('is_neutral_site') %}
                                                <small class="badge bg-info text-dark mb-2">Neutral Site</small>
                                            {% endif %}
                                        </div>
                                        
                                        <div class="text-center">
                                            <!-- Teams and Scores -->
                                            <div class="d-flex justify-content-between align-items-center mb-2">
                                                <div class="text-{{ 'success' if game.home_score > game.away_score else 'muted' }}">
                                                    <strong>{{ game.home_team }}</strong>
                                                    {% if not game.get('is_neutral_site') %}
                                                        <small class="text-muted">(H)</small>
                                                    {% endif %}
                                                </div>
                                                <div class="mx-2">
                                                    <span class="badge bg-{{ 'success' if game.home_score > game.away_score else 'secondary' }} fs-6">
                                                        {{ game.home_score }}
                                                    </span>
                                                </div>
                                            </div>
                                            
                                            <div class="d-flex justify-content-between align-items-center mb-3">
                                                <div class="text-{{ 'success' if game.away_score > game.home_score else 'muted' }}">
                                                    <strong>{{ game.away_team }}</strong>
                                                    {% if not game.get('is_neutral_site') %}
                                                        <small class="text-muted">(A)</small>
                                                    {% endif %}
                                                </div>
                                                <div class="mx-2">
                                                    <span class="badge bg-{{ 'success' if game.away_score > game.home_score else 'secondary' }} fs-6">
                                                        {{ game.away_score }}
                                                    </span>
                                                </div>
                                            </div>
                                            
                                            <!-- Game Types -->
                                            <div class="small text-muted">
                                                <div>{{ game.home_team }}: {{ game.home_game_type }} Game</div>
                                                <div>{{ game.away_team }}: {{ game.away_game_type }} Game</div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="card-footer text-center">
                                        <small class="text-muted">
                                            Added: {{ game.date_added.split(' ')[0] if ' ' in game.date_added else game.date_added }}
                                        </small>
                                    </div>
                                </div>
                            </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <div class="text-center text-muted py-5">
                        <h5>No games recorded for Week {{ selected_week }}</h5>
                        <p>Games will appear here once you add them for this week.</p>
                        <a href="{{ url_for('add_game') }}" class="btn btn-primary">Add Game</a>
                    </div>
                {% endif %}
            </div>
        </div>
        
        {% if week_games %}
            <div class="mt-4">
                <h5>Week {{ selected_week }} Summary</h5>
                <div class="row">
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h6 class="card-title">Total Games</h6>
                                <h4 class="text-primary">{{ week_games|length }}</h4>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h6 class="card-title">P4 Games</h6>
                                <h4 class="text-primary">{{ week_games|selectattr('home_game_type', 'equalto', 'P4')|list|length + week_games|selectattr('away_game_type', 'equalto', 'P4')|list|length }}</h4>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h6 class="card-title">G5 Games</h6>
                                <h4 class="text-primary">{{ week_games|selectattr('home_game_type', 'equalto', 'G5')|list|length + week_games|selectattr('away_game_type', 'equalto', 'G5')|list|length }}</h4>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h6 class="card-title">Neutral Site</h6>
                                <h4 class="text-primary">{{ week_games|selectattr('is_neutral_site', 'equalto', true)|list|length }}</h4>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        {% endif %}
    </div>
</div>

<script>
function changeWeek() {
    const selectedWeek = document.getElementById('week_selector').value;
    window.location.href = "{{ url_for('weekly_results') }}/" + selectedWeek;
}
</script>
{% endblock %}"""

    # Write all template files
    with open('templates/base.html', 'w') as f:
        f.write(base_html)
    
    with open('templates/index.html', 'w') as f:
        f.write(index_html)
    
    with open('templates/add_game.html', 'w') as f:
        f.write(add_game_html)
    
    with open('templates/team_detail.html', 'w') as f:
        f.write(team_detail_html)
    
    with open('templates/weekly_results.html', 'w') as f:
        f.write(weekly_results_html)

    # Login template
    login_html = """{% extends "base.html" %}

{% block title %}Admin Login - College Football Rankings{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h4 class="mb-0">Admin Login</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="password" class="form-label">Password</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                    </div>
                    <button type="submit" class="btn btn-primary">Login</button>
                    <a href="{{ url_for('index') }}" class="btn btn-secondary">Back to Rankings</a>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}"""

    with open('templates/login.html', 'w') as f:
        f.write(login_html)

if __name__ == '__main__':
    # Create templates directory and files
    create_templates()
    
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
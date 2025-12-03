"""
Bowl Pick'em Utility Functions
Helper functions for the Bowl Pick'em feature
"""
import secrets
from datetime import datetime
from flask import session

# Import from root-level modules
from models import db, ScheduledGame, PickEmUser, BowlPick


# Configuration
PICKEM_WEEKS = ['Bowl Games', 'CFP', 'Bowls', 'CFP Playoffs']
SESSION_COOKIE_NAME = 'pickem_user_code'
CURRENT_SEASON = 2025  # Update this each year


def generate_user_code():
    """Generate a unique user code in format BOWL-XXXXXX"""
    while True:
        code = f"BOWL-{secrets.token_hex(3).upper()}"
        # Check if code already exists for current season
        existing = PickEmUser.query.filter_by(
            user_code=code, 
            season_year=CURRENT_SEASON
        ).first()
        if not existing:
            return code


def get_current_user():
    """Get the current logged-in PickEm user from session cookie"""
    user_code = session.get(SESSION_COOKIE_NAME)
    if not user_code:
        return None
    
    # Find user by code for current season
    user = PickEmUser.query.filter_by(
        user_code=user_code,
        season_year=CURRENT_SEASON
    ).first()
    
    return user


def set_current_user(user_code):
    """Set the current user in session (cookie-based login)"""
    session[SESSION_COOKIE_NAME] = user_code
    session.permanent = True  # Makes session last 31 days


def clear_current_user():
    """Clear the current user from session (logout)"""
    session.pop(SESSION_COOKIE_NAME, None)


def is_game_locked(scheduled_game):
    """
    Check if a game is locked (game time has passed)
    Returns True if locked, False if still pickable
    """
    if not scheduled_game:
        return False
    
    if not scheduled_game.game_date or not scheduled_game.game_time:
        return False
    
    try:
        # Parse game time (format: "3:30 PM")
        game_datetime = datetime.combine(
            scheduled_game.game_date,
            datetime.strptime(scheduled_game.game_time, '%I:%M %p').time()
        )
        
        # Game is locked if time has passed
        return game_datetime <= datetime.now()
    except (ValueError, TypeError):
        # If we can't parse the time, consider it unlocked
        return False


def get_pickem_games():
    """
    Get all games eligible for pick'em (Bowl Games, CFP, etc.)
    Returns list of ScheduledGame objects
    """
    games = ScheduledGame.query.filter(
        ScheduledGame.week.in_(PICKEM_WEEKS)
    ).order_by(
        ScheduledGame.game_date.asc(),
        ScheduledGame.game_time.asc()
    ).all()
    
    return games


def get_unlocked_games():
    """Get all pick'em games that are still unlocked (can be picked)"""
    all_games = get_pickem_games()
    return [game for game in all_games if not is_game_locked(game)]


def get_locked_games():
    """Get all pick'em games that are locked (already started)"""
    all_games = get_pickem_games()
    return [game for game in all_games if is_game_locked(game)]


def get_or_create_pick(user, game):
    """
    Get existing pick or create a new one for a user/game combination
    Returns BowlPick object
    """
    pick = BowlPick.query.filter_by(
        user_id=user.id,
        game_id=game.id,
        season_year=CURRENT_SEASON
    ).first()
    
    if not pick:
        pick = BowlPick(
            user_id=user.id,
            game_id=game.id,
            season_year=CURRENT_SEASON
        )
        db.session.add(pick)
    
    return pick


def calculate_user_score(user_id):
    """
    Calculate and update scores for all of a user's picks
    Returns dict with scoring info
    """
    user = PickEmUser.query.get(user_id)
    if not user:
        return None
    
    picks = BowlPick.query.filter_by(
        user_id=user_id,
        season_year=CURRENT_SEASON
    ).all()
    
    total_correct = 0
    total_locked = 0
    total_picks = 0
    
    for pick in picks:
        # Only count picks that have been made
        if pick.picked_team:
            total_picks += 1
            
            # Only score locked games
            if pick.is_locked():
                total_locked += 1
                
                # Calculate if correct
                if pick.calculate_result():
                    db.session.add(pick)
                    if pick.is_correct:
                        total_correct += 1
    
    # Commit any scoring updates
    db.session.commit()
    
    return {
        'user': user,
        'total_picks': total_picks,
        'total_locked': total_locked,
        'total_correct': total_correct,
        'percentage': round((total_correct / total_locked * 100), 1) if total_locked > 0 else 0
    }


def calculate_all_scores():
    """
    Calculate scores for ALL users in current season
    Useful for admin scoring updates
    Returns list of score dictionaries
    """
    users = PickEmUser.query.filter_by(season_year=CURRENT_SEASON).all()
    results = []
    
    for user in users:
        score_info = calculate_user_score(user.id)
        if score_info:
            results.append(score_info)
    
    return results


def get_leaderboard():
    """
    Get leaderboard data sorted by score
    Returns list of users with their scores
    """
    users = PickEmUser.query.filter_by(season_year=CURRENT_SEASON).all()
    
    leaderboard_data = []
    for user in users:
        score_info = {
            'user': user,
            'name': user.name,
            'user_code': user.user_code,
            'total_picks': user.get_total_picks(),
            'locked_picks': user.get_locked_picks(),
            'correct_picks': user.get_score(),
            'percentage': user.get_percentage_correct()
        }
        leaderboard_data.append(score_info)
    
    # Sort by correct picks (descending), then by percentage
    leaderboard_data.sort(key=lambda x: (x['correct_picks'], x['percentage']), reverse=True)
    
    # Add rank
    for idx, entry in enumerate(leaderboard_data, start=1):
        entry['rank'] = idx
    
    return leaderboard_data


def get_game_pick_summary(game_id):
    """
    Get summary of all picks for a specific game
    Only shows picks if game is locked
    Returns dict with pick counts
    """
    game = ScheduledGame.query.get(game_id)
    if not game or not is_game_locked(game):
        return None
    
    picks = BowlPick.query.filter_by(
        game_id=game_id,
        season_year=CURRENT_SEASON
    ).filter(
        BowlPick.picked_team.isnot(None)
    ).all()
    
    home_picks = sum(1 for p in picks if p.picked_team == game.home_team)
    away_picks = sum(1 for p in picks if p.picked_team == game.away_team)
    
    return {
        'game': game,
        'home_team': game.home_team,
        'away_team': game.away_team,
        'home_picks': home_picks,
        'away_picks': away_picks,
        'total_picks': len(picks),
        'is_locked': True
    }


def archive_season(season_year):
    """
    Archive a completed season's pick'em data
    Returns True if successful, False otherwise
    """
    from models import PickEmArchive
    
    # Check if already archived
    existing = PickEmArchive.query.filter_by(season_year=season_year).first()
    if existing:
        return False  # Already archived
    
    # Get all data for the season
    users = PickEmUser.query.filter_by(season_year=season_year).all()
    picks = BowlPick.query.filter_by(season_year=season_year).all()
    
    # Find winner (user with most correct picks)
    winner = None
    winner_score = 0
    for user in users:
        score = user.get_score()
        if score > winner_score:
            winner = user
            winner_score = score
    
    # Create archive data
    archive_data = {
        'users': [
            {
                'name': u.name,
                'user_code': u.user_code,
                'email': u.email,
                'total_picks': u.get_total_picks(),
                'correct_picks': u.get_score(),
                'percentage': u.get_percentage_correct()
            }
            for u in users
        ],
        'picks': [
            {
                'user_code': p.user.user_code if p.user else 'Unknown',
                'game_id': p.game_id,
                'picked_team': p.picked_team,
                'is_correct': p.is_correct,
                'points': p.points
            }
            for p in picks
        ]
    }
    
    # Create archive record
    archive = PickEmArchive(
        season_year=season_year,
        total_users=len(users),
        total_picks=len(picks),
        total_games=len(get_pickem_games()),
        winner_name=winner.name if winner else None,
        winner_code=winner.user_code if winner else None,
        winner_score=winner_score
    )
    archive.set_archive_data(archive_data)
    
    db.session.add(archive)
    db.session.commit()
    
    return True
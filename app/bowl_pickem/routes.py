"""
Bowl Pick'em Routes
All routes for the Bowl Pick'em feature
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime

# Import from root-level modules
from models import db, ScheduledGame, PickEmUser, BowlPick

# Import utilities from this module
from .utils import (
    generate_user_code,
    get_current_user,
    set_current_user,
    clear_current_user,
    is_game_locked,
    get_pickem_games,
    get_unlocked_games,
    get_locked_games,
    get_or_create_pick,
    calculate_user_score,
    calculate_all_scores,
    get_leaderboard,
    get_game_pick_summary,
    CURRENT_SEASON
)

# Create Blueprint
bp = Blueprint('bowl_pickem', __name__, url_prefix='/bowl_pickem')


@bp.route('/')
def home():
    """
    Home page - shows registration form or user dashboard
    """
    user = get_current_user()
    
    if user:
        # User is logged in - show dashboard
        total_games = len(get_pickem_games())
        unlocked_games = len(get_unlocked_games())
        user_picks = user.get_total_picks()
        user_score = user.get_score()
        user_percentage = user.get_percentage_correct()
        locked_picks = user.get_locked_picks()
        
        return render_template(
            'bowl_pickem/home.html',
            user=user,
            logged_in=True,
            total_games=total_games,
            unlocked_games=unlocked_games,
            user_picks=user_picks,
            user_score=user_score,
            user_percentage=user_percentage,
            locked_picks=locked_picks
        )
    else:
        # Show registration form
        return render_template(
            'bowl_pickem/home.html',
            logged_in=False
        )


@bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user for Bowl Pick'em
    """
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    
    if not name:
        flash('Please enter your name!', 'error')
        return redirect(url_for('bowl_pickem.home'))
    
    # Generate unique code
    user_code = generate_user_code()
    
    # Create new user
    new_user = PickEmUser(
        name=name,
        email=email if email else None,
        user_code=user_code,
        season_year=CURRENT_SEASON
    )
    
    db.session.add(new_user)
    
    # Initialize picks for all available games
    games = get_pickem_games()
    for game in games:
        pick = BowlPick(
            user_id=new_user.id,
            game_id=game.id,
            season_year=CURRENT_SEASON
        )
        db.session.add(pick)
    
    db.session.commit()
    
    # Log user in
    set_current_user(user_code)
    
    flash(f'Welcome, {name}! Your code is: {user_code} - Save this code!', 'success')
    return redirect(url_for('bowl_pickem.home'))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login with existing user code
    """
    if request.method == 'GET':
        return render_template('bowl_pickem/login.html')
    
    user_code = request.form.get('user_code', '').strip().upper()
    
    if not user_code:
        flash('Please enter your user code!', 'error')
        return redirect(url_for('bowl_pickem.login'))
    
    # Find user
    user = PickEmUser.query.filter_by(
        user_code=user_code,
        season_year=CURRENT_SEASON
    ).first()
    
    if not user:
        flash('User code not found! Check your code and try again.', 'error')
        return redirect(url_for('bowl_pickem.login'))
    
    # Log user in
    set_current_user(user_code)
    flash(f'Welcome back, {user.name}!', 'success')
    return redirect(url_for('bowl_pickem.home'))


@bp.route('/logout')
def logout():
    """
    Logout current user
    """
    user = get_current_user()
    if user:
        flash(f'Goodbye, {user.name}! Your code is {user.user_code}', 'info')
    
    clear_current_user()
    return redirect(url_for('bowl_pickem.home'))


@bp.route('/make_picks', methods=['GET', 'POST'])
def make_picks():
    """
    Make or update picks for bowl games
    """
    user = get_current_user()
    
    if not user:
        flash('Please register or login first!', 'error')
        return redirect(url_for('bowl_pickem.home'))
    
    if request.method == 'GET':
        # Get all games grouped by locked status
        all_games = get_pickem_games()
        
        # Get user's existing picks
        user_picks = {
            pick.game_id: pick 
            for pick in BowlPick.query.filter_by(
                user_id=user.id,
                season_year=CURRENT_SEASON
            ).all()
        }
        
        # Group games
        unlocked_games = []
        locked_games = []
        
        for game in all_games:
            game_data = {
                'game': game,
                'pick': user_picks.get(game.id),
                'is_locked': is_game_locked(game)
            }
            
            if game_data['is_locked']:
                locked_games.append(game_data)
            else:
                unlocked_games.append(game_data)
        
        return render_template(
            'bowl_pickem/picks.html',
            user=user,
            unlocked_games=unlocked_games,
            locked_games=locked_games
        )
    
    # POST - Save picks
    games = get_pickem_games()
    picks_saved = 0
    picks_locked = 0
    
    for game in games:
        # Check if game is locked
        if is_game_locked(game):
            picks_locked += 1
            continue
        
        # Get the pick from form
        form_key = f'pick_{game.id}'
        picked_team = request.form.get(form_key)
        
        if picked_team and picked_team in [game.home_team, game.away_team]:
            # Get or create pick
            pick = get_or_create_pick(user, game)
            pick.picked_team = picked_team
            pick.updated_at = datetime.utcnow()
            db.session.add(pick)
            picks_saved += 1
    
    db.session.commit()
    
    flash(f'✅ Saved {picks_saved} picks! ({picks_locked} games already locked)', 'success')
    return redirect(url_for('bowl_pickem.make_picks'))


@bp.route('/leaderboard')
def leaderboard():
    """
    Show leaderboard with all users and scores
    """
    leaderboard_data = get_leaderboard()
    
    # Get current user if logged in
    user = get_current_user()
    
    return render_template(
        'bowl_pickem/leaderboard.html',
        leaderboard=leaderboard_data,
        current_user=user
    )


@bp.route('/game_picks/<int:game_id>')
def game_picks(game_id):
    """
    Show all picks for a specific game (only if locked)
    """
    game = ScheduledGame.query.get_or_404(game_id)
    
    if not is_game_locked(game):
        flash('Picks are hidden until the game starts!', 'warning')
        return redirect(url_for('bowl_pickem.leaderboard'))
    
    # Get all picks for this game
    picks = BowlPick.query.filter_by(
        game_id=game_id,
        season_year=CURRENT_SEASON
    ).filter(
        BowlPick.picked_team.isnot(None)
    ).all()
    
    # Group by team
    home_pickers = [p.user for p in picks if p.picked_team == game.home_team]
    away_pickers = [p.user for p in picks if p.picked_team == game.away_team]
    
    return render_template(
        'bowl_pickem/game_picks.html',
        game=game,
        home_pickers=home_pickers,
        away_pickers=away_pickers,
        total_picks=len(picks)
    )


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@bp.route('/admin/auto_score', methods=['POST'])
def auto_score():
    """
    Admin route to automatically calculate scores for all completed games
    This should be run after games complete
    """
    # TODO: Add your login_required decorator here
    # For now, we'll add a simple check
    
    try:
        results = calculate_all_scores()
        
        total_users = len(results)
        flash(f'✅ Scores calculated for {total_users} users!', 'success')
        
    except Exception as e:
        flash(f'Error calculating scores: {e}', 'error')
    
    return redirect(url_for('bowl_pickem.leaderboard'))


@bp.route('/admin/archive_season', methods=['POST'])
def admin_archive_season():
    """
    Admin route to archive the current season
    This should be run AFTER the season ends and BEFORE starting a new season
    """
    # TODO: Add your login_required decorator here
    
    from .utils import archive_season
    
    try:
        success = archive_season(CURRENT_SEASON)
        
        if success:
            flash(f'✅ Season {CURRENT_SEASON} archived successfully!', 'success')
        else:
            flash(f'Season {CURRENT_SEASON} is already archived!', 'warning')
            
    except Exception as e:
        flash(f'Error archiving season: {e}', 'error')
    
    return redirect(url_for('bowl_pickem.home'))


@bp.route('/admin/reset_season', methods=['POST'])
def admin_reset_season():
    """
    Admin route to reset the current season (DELETE ALL DATA)
    WARNING: This deletes all users and picks for current season
    Use archive_season first if you want to keep historical data
    """
    # TODO: Add your login_required decorator here
    
    confirm = request.form.get('confirm', '').strip()
    
    if confirm != 'RESET':
        flash('Reset cancelled. Type RESET to confirm.', 'warning')
        return redirect(url_for('bowl_pickem.home'))
    
    try:
        # Delete all picks for current season
        picks_deleted = BowlPick.query.filter_by(season_year=CURRENT_SEASON).delete()
        
        # Delete all users for current season
        users_deleted = PickEmUser.query.filter_by(season_year=CURRENT_SEASON).delete()
        
        db.session.commit()
        
        flash(f'🗑️ Reset complete! Deleted {users_deleted} users and {picks_deleted} picks.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting season: {e}', 'error')
    
    return redirect(url_for('bowl_pickem.home'))

@bp.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    """
    Admin route to delete a specific user and all their picks
    """
    # TODO: Add your login_required decorator here
    
    try:
        user = PickEmUser.query.get_or_404(user_id)
        user_name = user.name
        user_code = user.user_code
        
        # Delete user (picks will cascade automatically)
        db.session.delete(user)
        db.session.commit()
        
        flash(f'✅ Deleted user "{user_name}" ({user_code}) and all their picks', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {e}', 'error')
    
    return redirect(url_for('bowl_pickem.admin_manage_users'))


@bp.route('/admin/manage_users')
def admin_manage_users():
    """
    Admin route to view and manage all Bowl Pick'em users
    """
    # TODO: Add your login_required decorator here
    
    users = PickEmUser.query.filter_by(season_year=CURRENT_SEASON).order_by(PickEmUser.name).all()
    
    user_data = []
    for user in users:
        user_data.append({
            'id': user.id,
            'name': user.name,
            'user_code': user.user_code,
            'email': user.email,
            'total_picks': user.get_total_picks(),
            'correct_picks': user.get_score(),
            'created_at': user.created_at
        })
    
    return render_template('bowl_pickem/manage_users.html', users=user_data)
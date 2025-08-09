# models.py - Database table definitions
# This file tells the database what tables to create and what columns they should have

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

# Create the database object
db = SQLAlchemy()

class Game(db.Model):
    """
    This replaces your games_data.json file
    Each row in this table = one game from your JSON file
    """
    __tablename__ = 'cfb_games'
    
    # Columns (think of these as the keys in your JSON objects)
    id = db.Column(db.Integer, primary_key=True)  # Unique ID for each game
    week = db.Column(db.String(10), nullable=False, index=True)  # "1", "2", "Bowls", etc.
    home_team = db.Column(db.String(100), nullable=False, index=True)  # "Alabama", etc.
    away_team = db.Column(db.String(100), nullable=False, index=True)  # "Georgia", etc.
    home_score = db.Column(db.Integer, nullable=False)  # 28
    away_score = db.Column(db.Integer, nullable=False)  # 21
    is_neutral_site = db.Column(db.Boolean, default=False)  # True/False
    overtime = db.Column(db.Boolean, default=False)  # True/False
    date_added = db.Column(db.DateTime, default=datetime.utcnow)  # When game was added
    game_date = db.Column(db.Date, nullable=True)  # When game was actually played
    
    # ADD THESE LINES FOR PERFORMANCE (right before def to_dict):
    __table_args__ = (
        db.Index('idx_games_week_teams', 'week', 'home_team', 'away_team'),
        db.Index('idx_games_teams_lookup', 'home_team', 'away_team'),
        db.Index('idx_games_date_added', 'date_added'),
        db.Index('idx_games_week_date', 'week', 'game_date'),
    )


    def to_dict(self):
        """Convert database row back to the format your app expects"""
        return {
            'id': self.id,
            'week': self.week,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'home_score': self.home_score,
            'away_score': self.away_score,
            'is_neutral_site': self.is_neutral_site,
            'overtime': self.overtime,
            'date_added': self.date_added.strftime('%Y-%m-%d %H:%M:%S') if self.date_added else None,
            'game_date': self.game_date.strftime('%Y-%m-%d') if self.game_date else None
        }

class TeamStats(db.Model):
    """
    This replaces your team_stats.json file
    Each row = one team's statistics
    """
    __tablename__ = 'cfb_team_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(100), nullable=False, unique=True, index=True)  # "Alabama"
    wins = db.Column(db.Integer, default=0)  # 10
    losses = db.Column(db.Integer, default=0)  # 2
    points_for = db.Column(db.Integer, default=0)  # 420
    points_against = db.Column(db.Integer, default=0)  # 180
    home_wins = db.Column(db.Integer, default=0)  # 6
    road_wins = db.Column(db.Integer, default=0)  # 4
    margin_of_victory_total = db.Column(db.Integer, default=0)  # 240
    games_json = db.Column(db.Text, default='[]')  # Store individual games as JSON text
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ADD THESE LINES FOR PERFORMANCE (right before @property):
    __table_args__ = (
        db.Index('idx_team_stats_record', 'wins', 'losses'),
        db.Index('idx_team_stats_games_played', 'wins', 'losses', 'team_name'),
        db.Index('idx_team_stats_updated', 'last_updated'),
        db.Index('idx_team_stats_points', 'points_for', 'points_against'),
    )



    @property
    def games(self):
        """Get the games list (converts JSON text back to Python list)"""
        return json.loads(self.games_json) if self.games_json else []
    
    @games.setter
    def games(self, value):
        """Set the games list (converts Python list to JSON text)"""
        self.games_json = json.dumps(value)
    
    def to_dict(self):
        """Convert to the format your current app expects"""
        return {
            'wins': self.wins,
            'losses': self.losses,
            'points_for': self.points_for,
            'points_against': self.points_against,
            'home_wins': self.home_wins,
            'road_wins': self.road_wins,
            'margin_of_victory_total': self.margin_of_victory_total,
            'games': self.games  # This automatically uses the @property above
        }

# Add these fields to your existing ScheduledGame model in models.py

class ScheduledGame(db.Model):
    __tablename__ = 'cfb_scheduled_games'
    
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.String(10), nullable=False)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    neutral = db.Column(db.Boolean, default=False)
    completed = db.Column(db.Boolean, default=False)
    game_date = db.Column(db.Date, nullable=True)
    game_time = db.Column(db.String(20), nullable=True)
    tv_network = db.Column(db.String(50), nullable=True)
    location_note = db.Column(db.String(200), nullable=True)
    original_home = db.Column(db.String(100), nullable=True)
    original_away = db.Column(db.String(100), nullable=True)
    bowl_game_name = db.Column(db.String(255), nullable=True)
    
    # NEW: Add these fields for final scores
    final_home_score = db.Column(db.Integer, nullable=True)
    final_away_score = db.Column(db.Integer, nullable=True)
    overtime = db.Column(db.Boolean, default=False)

    # ADD THESE LINES FOR PERFORMANCE (right before def to_dict):
    __table_args__ = (
        db.Index('idx_scheduled_week_completed', 'week', 'completed'),
        db.Index('idx_scheduled_teams', 'home_team', 'away_team'),
        db.Index('idx_scheduled_date_time', 'game_date', 'game_time'),
        db.Index('idx_scheduled_completed_lookup', 'completed', 'week'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'week': self.week,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'neutral': self.neutral,
            'completed': self.completed,
            'game_date': self.game_date.strftime('%Y-%m-%d') if self.game_date else None,
            'game_time': self.game_time,
            'tv_network': self.tv_network,
            'location_note': self.location_note,
            'original_home': self.original_home,
            'original_away': self.original_away,
            'final_home_score': self.final_home_score,
            'final_away_score': self.final_away_score,
            'overtime': self.overtime,
            'bowl_game_name': self.bowl_game_name
        }
        

class ArchivedSeason(db.Model):
    __tablename__ = 'cfb_archived_seasons'
    
    id = db.Column(db.Integer, primary_key=True)
    season_name = db.Column(db.String(100), nullable=False)
    archived_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_games = db.Column(db.Integer, default=0)
    total_teams = db.Column(db.Integer, default=0)
    champion = db.Column(db.String(100), nullable=True)
    total_weeks = db.Column(db.Integer, default=0)
    
    # Store the complete archive data as JSON text
    archive_data_json = db.Column(db.Text)

    # ADD THESE LINES FOR PERFORMANCE (right before def to_dict):
    __table_args__ = (
        db.Index('idx_archived_season_name', 'season_name'),
        db.Index('idx_archived_date_desc', 'archived_date'),
        db.Index('idx_archived_champion', 'champion'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'season_name': self.season_name,
            'archived_date': self.archived_date.strftime('%Y-%m-%d %H:%M:%S'),
            'total_games': self.total_games,
            'total_teams': self.total_teams,
            'champion': self.champion,
            'total_weeks': self.total_weeks,
            'archive_data': json.loads(self.archive_data_json) if self.archive_data_json else {}
        }

class WeeklySnapshot(db.Model):
    __tablename__ = 'cfb_weekly_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    week_name = db.Column(db.String(100), nullable=False)  # "Week 5", "Week 10", etc.
    snapshot_date = db.Column(db.DateTime, default=datetime.utcnow)
    rankings_json = db.Column(db.Text)  # Store the rankings data
    
    # Add indexes for performance
    __table_args__ = (
        db.Index('idx_weekly_snapshots_week', 'week_name'),
        db.Index('idx_weekly_snapshots_date', 'snapshot_date'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'week_name': self.week_name,
            'snapshot_date': self.snapshot_date.isoformat(),
            'rankings': json.loads(self.rankings_json) if self.rankings_json else []
        }
    
    @property
    def rankings(self):
        return json.loads(self.rankings_json) if self.rankings_json else []
    
    @rankings.setter 
    def rankings(self, value):
        self.rankings_json = json.dumps(value)


class CFBPredictionLog(db.Model):
    """Track every CFB prediction made vs actual results"""
    __tablename__ = 'cfb_prediction_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Game identification
    season_year = db.Column(db.Integer, nullable=False, default=2025)
    week = db.Column(db.String(10), nullable=False)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    
    # Pre-game predictions
    predicted_winner = db.Column(db.String(100), nullable=False)
    predicted_margin = db.Column(db.Float, nullable=False)  # Positive = home team favored
    predicted_total = db.Column(db.Float, nullable=True)    # Over/under points
    win_probability = db.Column(db.Float, nullable=False)   # 0-100
    confidence_level = db.Column(db.String(20), nullable=True)  # High/Medium/Low

    prediction_type = db.Column(db.String(50), default='manual', nullable=False)  # 'manual' or 'automated'

        # Algorithm settings when prediction was made (MISSING - ADD THIS)
    temporal_weights_json = db.Column(db.Text, nullable=True)  # Store current temporal weights
    algorithm_version = db.Column(db.String(50), default='v1.0')  # Track algorithm changes
    
    # Structured factor breakdown (MISSING - ADD THESE)
    base_strength_diff = db.Column(db.Float, nullable=True)    # Raw rating difference  
    schedule_strength_factor = db.Column(db.Float, nullable=True)
    momentum_factor = db.Column(db.Float, nullable=True)
    location_factor = db.Column(db.Float, nullable=True)
    consistency_factor = db.Column(db.Float, nullable=True)
    common_opponent_factor = db.Column(db.Float, nullable=True)
    
    # Prediction factors (JSON storage for flexibility)
    prediction_factors_json = db.Column(db.Text, nullable=True)
    
    # Actual results (filled after game)
    actual_winner = db.Column(db.String(100), nullable=True)
    actual_margin = db.Column(db.Float, nullable=True)
    actual_total = db.Column(db.Float, nullable=True)
    game_completed = db.Column(db.Boolean, default=False)
    
    # Accuracy metrics (calculated after game)
    margin_error = db.Column(db.Float, nullable=True)       # |predicted - actual|
    total_error = db.Column(db.Float, nullable=True)
    winner_correct = db.Column(db.Boolean, nullable=True)
    
    # Timestamps
    prediction_date = db.Column(db.DateTime, default=datetime.utcnow)
    result_date = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'season_year': self.season_year,
            'week': self.week,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'predicted_winner': self.predicted_winner,
            'predicted_margin': self.predicted_margin,
            'predicted_total': self.predicted_total,
            'win_probability': self.win_probability,
            'confidence_level': self.confidence_level,
            'actual_winner': self.actual_winner,
            'actual_margin': self.actual_margin,
            'actual_total': self.actual_total,
            'margin_error': self.margin_error,
            'total_error': self.total_error,
            'winner_correct': self.winner_correct,
            'game_completed': self.game_completed,
            'prediction_factors': json.loads(self.prediction_factors_json) if self.prediction_factors_json else {},
            'prediction_date': self.prediction_date.isoformat() if self.prediction_date else None,
            'result_date': self.result_date.isoformat() if self.result_date else None
        }

class CFBTemporalAnalysis(db.Model):
    """Track how CFB prediction accuracy varies by week/timing"""
    __tablename__ = 'cfb_temporal_analysis'
    
    id = db.Column(db.Integer, primary_key=True)
    season_year = db.Column(db.Integer, nullable=False, default=2025)
    week = db.Column(db.String(10), nullable=False)
    
    # Prediction accuracy for this week
    total_predictions = db.Column(db.Integer, default=0)
    correct_winners = db.Column(db.Integer, default=0)
    avg_margin_error = db.Column(db.Float, default=0.0)
    avg_total_error = db.Column(db.Float, default=0.0)
    
    # Temporal weight performance
    current_temporal_weight = db.Column(db.Float, nullable=False)
    suggested_weight = db.Column(db.Float, nullable=True)
    weight_confidence = db.Column(db.Float, nullable=True)  # How confident in suggestion
    
    # Analysis date
    analysis_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate week analysis
    __table_args__ = (
        db.UniqueConstraint('season_year', 'week', name='unique_cfb_season_week_analysis'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'season_year': self.season_year,
            'week': self.week,
            'total_predictions': self.total_predictions,
            'correct_winners': self.correct_winners,
            'winner_accuracy': round(self.correct_winners / max(1, self.total_predictions) * 100, 1),
            'avg_margin_error': round(self.avg_margin_error, 2),
            'avg_total_error': round(self.avg_total_error, 2),
            'current_temporal_weight': self.current_temporal_weight,
            'suggested_weight': self.suggested_weight,
            'weight_confidence': self.weight_confidence,
            'analysis_date': self.analysis_date.isoformat() if self.analysis_date else None
        }

# In your models.py file, find the CFBAlgorithmPerformance class and add this field:

# In your models.py file, update the CFBAlgorithmPerformance class:

class CFBAlgorithmPerformance(db.Model):
    """Track which CFB algorithm factors are most/least predictive"""
    __tablename__ = 'cfb_algorithm_performance'
    
    id = db.Column(db.Integer, primary_key=True)
    season_year = db.Column(db.Integer, nullable=False, default=2025)
    
    # Factor being analyzed
    factor_name = db.Column(db.String(100), nullable=True)  # Changed to nullable=True
    factor_category = db.Column(db.String(50), nullable=True)  # Changed to nullable=True
    
    # Performance metrics
    prediction_count = db.Column(db.Integer, default=0)
    correlation_with_accuracy = db.Column(db.Float, nullable=True)
    avg_impact_on_prediction = db.Column(db.Float, nullable=True)
    
    # ADD ALL THESE MISSING ACCURACY TRACKING FIELDS:
    winner_accuracy = db.Column(db.Float, nullable=True)
    average_accuracy = db.Column(db.Float, nullable=True)
    average_margin_error = db.Column(db.Float, nullable=True)
    average_total_error = db.Column(db.Float, nullable=True)
    predictions_verified = db.Column(db.Integer, default=0)
    average_confidence = db.Column(db.Float, nullable=True)
    factor_importance = db.Column(db.Text, nullable=True)
    optimization_suggestions = db.Column(db.Text, nullable=True)
    
    # ADD THESE ADDITIONAL FIELDS THAT MIGHT BE NEEDED:
    factor_importance = db.Column(db.Text, nullable=True)  # JSON storage for factor rankings
    optimization_suggestions = db.Column(db.Text, nullable=True)  # JSON storage for suggestions
    
    # Current vs suggested values
    current_weight = db.Column(db.Float, nullable=True)
    suggested_weight = db.Column(db.Float, nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)
    
    # Analysis metadata
    analysis_date = db.Column(db.DateTime, default=datetime.utcnow)
    sample_size = db.Column(db.Integer, default=0)
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('season_year', 'factor_name', name='unique_cfb_season_factor'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'season_year': self.season_year,
            'factor_name': self.factor_name,
            'factor_category': self.factor_category,
            'prediction_count': self.prediction_count,
            'correlation_with_accuracy': round(self.correlation_with_accuracy, 3) if self.correlation_with_accuracy else None,
            'avg_impact_on_prediction': round(self.avg_impact_on_prediction, 3) if self.avg_impact_on_prediction else None,
            
            # ADD ALL THESE LINES TO THE to_dict() METHOD:
            'winner_accuracy': round(self.winner_accuracy, 1) if self.winner_accuracy else None,
            'average_accuracy': round(self.average_accuracy, 1) if self.average_accuracy else None,
            'average_margin_error': round(self.average_margin_error, 2) if self.average_margin_error else None,
            'average_total_error': round(self.average_total_error, 2) if self.average_total_error else None,
            'predictions_verified': self.predictions_verified,
            'average_confidence': round(self.average_confidence, 2) if self.average_confidence else None,
            'factor_importance': json.loads(self.factor_importance) if self.factor_importance else {},
            'optimization_suggestions': json.loads(self.optimization_suggestions) if self.optimization_suggestions else [],
            
            'current_weight': self.current_weight,
            'suggested_weight': self.suggested_weight,
            'confidence_score': round(self.confidence_score, 3) if self.confidence_score else None,
            'analysis_date': self.analysis_date.isoformat() if self.analysis_date else None,
            'sample_size': self.sample_size
        }


class ExternalPoll(db.Model):
    __tablename__ = 'external_polls'
    
    id = db.Column(db.Integer, primary_key=True)
    poll_name = db.Column(db.String(50), nullable=False)  # 'AP', 'Coaches', etc.
    week = db.Column(db.String(10), nullable=False)
    poll_date = db.Column(db.Date, nullable=False)
    rankings_json = db.Column(db.Text)  # Store the rankings as JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_rankings(self):
        """Helper method to get rankings as Python list"""
        return json.loads(self.rankings_json) if self.rankings_json else []
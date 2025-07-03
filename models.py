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
    __tablename__ = 'games'
    
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
    __tablename__ = 'team_stats'
    
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
    __tablename__ = 'scheduled_games'
    
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
    __tablename__ = 'archived_seasons'
    
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


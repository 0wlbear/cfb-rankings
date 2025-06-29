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
    
    # NEW: Add these fields for final scores
    final_home_score = db.Column(db.Integer, nullable=True)
    final_away_score = db.Column(db.Integer, nullable=True)
    overtime = db.Column(db.Boolean, default=False)
    
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
            'overtime': self.overtime
        }
        
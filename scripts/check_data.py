# check_data.py - Verify data is in database
from flask import Flask
from models import db, Game, TeamStats

def check_database():
    app = Flask(__name__)
    
    # Replace YOUR_PASSWORD with your actual password
    app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://cfb_admin:CFBRankings2025!@cfb-rankings-db.c0x628i8m5pg.us-east-1.rds.amazonaws.com:5432/cfb_rankings"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        # Check games
        games = Game.query.all()
        print(f"🎮 Games in database: {len(games)}")
        for game in games:
            print(f"  - Week {game.week}: {game.home_team} {game.home_score} - {game.away_score} {game.away_team}")
        
        # Check team stats
        teams = TeamStats.query.all()
        print(f"📊 Teams with stats: {len(teams)}")
        for team in teams:
            print(f"  - {team.team_name}: {team.wins}-{team.losses}")

if __name__ == '__main__':
    check_database()
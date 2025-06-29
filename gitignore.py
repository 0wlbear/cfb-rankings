# Add this to .gitignore (or create the file if it doesn't exist)

# Data persistence - don't track data files
/data/
*.json

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
cfb_rankings/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# But ALLOW these data files:
!data/games_data.json
!data/team_stats.json
!data/scheduled_games.json
!data/historical_rankings.json
!data/team_mappings.json
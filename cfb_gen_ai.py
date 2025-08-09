# cfb_gen_ai.py
"""
College Football Gen AI Module
Handles all AWS Bedrock integration and AI content generation
"""

import boto3
import json
import os
import hashlib
import time


# Simple in-memory cache for AI responses
ai_response_cache = {}
CACHE_TIMEOUT = 24 * 60 * 60  # 24 hours

def get_cache_key(*args, **kwargs):
    """Generate cache key from function arguments"""
    # Convert all arguments to string and hash
    cache_data = str(args) + str(sorted(kwargs.items()))
    return hashlib.md5(cache_data.encode()).hexdigest()

def cached_ai_call(cache_key, ai_function, *args, **kwargs):
    """Cache AI responses to avoid duplicate API calls"""
    
    # Check cache first
    if cache_key in ai_response_cache:
        cached_response, timestamp = ai_response_cache[cache_key]
        if time.time() - timestamp < CACHE_TIMEOUT:
            print(f"🚀 Using cached AI response for {cache_key[:8]}...")
            return cached_response
    
    # Not cached - make API call
    print(f"🤖 Making new AI API call for {cache_key[:8]}...")
    start_time = time.time()
    response = ai_function(*args, **kwargs)
    end_time = time.time()
    print(f"⏱️ AI call took {end_time - start_time:.2f} seconds")
    
    # Store in cache
    ai_response_cache[cache_key] = (response, time.time())
    
    return response

print(f"🔍 AI Cache status: {len(ai_response_cache)} cached responses")

# At the top of cfb_gen_ai.py, add model selection
FAST_MODEL_ID = "arn:aws:bedrock:us-east-1:249154182031:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
SLOW_MODEL_ID = "arn:aws:bedrock:us-east-1:249154182031:inference-profile/us.anthropic.claude-opus-4-1-20250805-v1:0"

def get_model_for_task(task_complexity="simple"):
    """Choose model based on task complexity"""
    if task_complexity == "complex":
        return SLOW_MODEL_ID  # Use Opus for complex analysis
    else:
        return FAST_MODEL_ID  # Use Sonnet for quick tasks

# Module availability flag
GEN_AI_AVAILABLE = False

try:
    # Initialize Bedrock client
    bedrock_client = boto3.client(
        service_name='bedrock-runtime',
        region_name=os.environ.get('AWS_REGION', 'us-east-1')
    )
    GEN_AI_AVAILABLE = True
    print("✅ AWS Bedrock Gen AI module loaded successfully")
except Exception as e:
    print(f"⚠️ Gen AI not available: {e}")
    bedrock_client = None

def test_gen_ai_connection():
    """Test the Gen AI connection"""
    if not GEN_AI_AVAILABLE:
        return {"status": "unavailable", "error": "Gen AI not configured"}
    
    try:
        # Simple test prompt
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": "Say 'Hello from CFB Gen AI!' in exactly those words."}],
            "max_tokens": 50
        }
        
        response = bedrock_client.invoke_model(
            modelId=get_model_for_task("simple"),
            body=json.dumps(body)
        )
        
        result = json.loads(response['body'].read())
        return {
            "status": "success", 
            "response": result['content'][0]['text'],
            "model": "arn:aws:bedrock:us-east-1:249154182031:inference-profile/us.anthropic.claude-opus-4-1-20250805-v1:0"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def explain_game_impact(game_data, victory_value, winner_team):
    """Generate AI explanation - USING FAST MODEL"""
    if not GEN_AI_AVAILABLE:
        return "AI analysis temporarily unavailable"
    
    cache_key = get_cache_key(
        game_data['home_team'], 
        game_data['away_team'], 
        game_data['home_score'], 
        game_data['away_score'],
        victory_value,
        winner_team
    )
    
    def _make_api_call():
        try:
            is_neutral = game_data.get('is_neutral_site', False) or game_data.get('neutral', False)
            
            if is_neutral:
                game_location = f"{game_data['away_team']} vs {game_data['home_team']} (Neutral Site)"
            else:
                game_location = f"{game_data['away_team']} @ {game_data['home_team']}"
            
            # ULTRA-SHORT PROMPT for speed
            prompt = f"""Game: {game_location}
Score: {game_data['away_score']}-{game_data['home_score']}
Winner: {winner_team}
Ranking Points: {victory_value}

Explain in 2 sentences why this win earned {victory_value} points."""
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,  # REDUCED further
                "temperature": 0.1  # Very focused
            }
            
            response = bedrock_client.invoke_model(
                modelId=get_model_for_task("simple"),  # FAST MODEL
                body=json.dumps(body)
            )
            
            result = json.loads(response['body'].read())
            return result['content'][0]['text']
            
        except Exception as e:
            return f"Analysis error: {str(e)}"
    
    return cached_ai_call(cache_key, _make_api_call)

def generate_weekly_preview(week, scheduled_games, team_rankings=None):
    """Generate AI preview for upcoming games in a week"""
    if not GEN_AI_AVAILABLE:
        return "Weekly preview temporarily unavailable"
    
    try:
        # Build context about the week's games
        games_summary = []
        top_matchups = []
        
        for game in scheduled_games[:15]:  # Limit to avoid token limits
            home_team = game.get('home_team', 'TBD')
            away_team = game.get('away_team', 'TBD')
            neutral = game.get('neutral', False)
            
            # Get rankings if available
            home_rank = team_rankings.get(home_team, 'NR') if team_rankings else 'NR'
            away_rank = team_rankings.get(away_team, 'NR') if team_rankings else 'NR'
            
            game_line = f"{away_team}"
            if away_rank != 'NR':
                game_line = f"#{away_rank} {away_team}"
            
            if neutral:
                game_line += f" vs "
            else:
                game_line += f" @ "
            
            if home_rank != 'NR':
                game_line += f"#{home_rank} {home_team}"
            else:
                game_line += home_team
            
            games_summary.append(game_line)
            
            # Identify top matchups (both teams ranked or high-profile)
            if (home_rank != 'NR' and away_rank != 'NR') or \
               any(team in ['Alabama', 'Ohio State', 'Georgia', 'Michigan', 'Texas', 'Notre Dame'] 
                   for team in [home_team, away_team]):
                top_matchups.append(game_line)

        games_text = '\n'.join(games_summary)
        
        prompt = f"""
Write a preview for Week {week} of college football. Here are the scheduled games:

{games_text}

Write a 4-6 sentence preview covering:
1. The biggest/most important games of the week
2. Key storylines or implications
3. What to watch for in terms of playoff/rankings impact

Keep it engaging and informative for college football fans. Focus on the most significant matchups.
"""

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400
        }
        
        response = bedrock_client.invoke_model(
            modelId=get_model_for_task("simple"),
            body=json.dumps(body)
        )
        
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
        
    except Exception as e:
        return f"Weekly preview error: {str(e)}"

def explain_team_ranking(team_name, team_ranking_data, team_stats, comparison_teams=None):
    """Generate AI explanation of why a team is ranked where they are"""
    if not GEN_AI_AVAILABLE:
        return "Ranking explanation temporarily unavailable"
    
    # Create cache key
    cache_key = get_cache_key(
        team_name, 
        str(team_ranking_data), 
        str(team_stats), 
        str(comparison_teams) if comparison_teams else ""
    )
    
    def _make_api_call():
        try:
            # Build context about the team
            rank = team_ranking_data.get('rank', 'NR')
            wins = team_stats.get('wins', team_stats.get('total_wins', 0))
            losses = team_stats.get('losses', team_stats.get('total_losses', 0))
            record = f"{wins}-{losses}"
            conference = team_ranking_data.get('conference', 'Unknown')
            adjusted_total = team_ranking_data.get('adjusted_total', 0)
            
            # Get key wins/losses if available
            notable_games = []
            if 'games' in team_stats:
                for game in team_stats['games']:
                    opponent = game.get('opponent', '')
                    result = game.get('result', '')
                    score = f"{game.get('team_score', 0)}-{game.get('opp_score', 0)}"
                    
                    # Include ranked opponents or notable teams
                    if any(notable in opponent for notable in ['Alabama', 'Georgia', 'Ohio State', 'Michigan', 'Texas', 'Notre Dame', 'Oklahoma', 'LSU', 'Florida']):
                        notable_games.append(f"{result} vs {opponent} ({score})")
            
            notable_text = "; ".join(notable_games[:3]) if notable_games else "No major wins/losses yet"
            
            comparison_text = ""
            if comparison_teams:
                comp_list = []
                for comp_team in comparison_teams[:3]:
                    comp_record = f"{comp_team.get('total_wins', 0)}-{comp_team.get('total_losses', 0)}"
                    comp_list.append(f"{comp_team.get('team', 'Unknown')} ({comp_record})")
                comparison_text = f"Compared to similar teams: {', '.join(comp_list)}"

            prompt = f"""
Explain why {team_name} is ranked #{rank} in college football:

Team: {team_name}
Record: {record}
Conference: {conference}
Ranking Score: {adjusted_total}
Notable Games: {notable_text}
{comparison_text}

Write 3-4 sentences explaining:
1. What makes this ranking justified
2. Key strengths or weaknesses
3. What they need to do to improve/maintain position

Be specific about their performance and resume.
"""

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300
            }
            
            response = bedrock_client.invoke_model(
                modelId=get_model_for_task("simple"),
                body=json.dumps(body)
            )
            
            result = json.loads(response['body'].read())
            return result['content'][0]['text']
            
        except Exception as e:
            return f"Ranking explanation error: {str(e)}"
    
    return cached_ai_call(cache_key, _make_api_call)

def enhance_matchup_prediction(team1_name, team2_name, prediction_data, team1_stats, team2_stats):
    """Generate AI analysis to enhance matchup predictions"""
    if not GEN_AI_AVAILABLE:
        return "Prediction analysis temporarily unavailable"
    
    try:
        winner = prediction_data.get('winner', 'Unknown')
        margin = prediction_data.get('final_margin', 0)
        win_prob = prediction_data.get('win_probability', 50)
        key_factors = prediction_data.get('key_factors', [])
        
        # Build team context
        team1_record = f"{team1_stats.get('total_wins', 0)}-{team1_stats.get('total_losses', 0)}"
        team2_record = f"{team2_stats.get('total_wins', 0)}-{team2_stats.get('total_losses', 0)}"
        
        factors_text = "; ".join(key_factors[:3]) if key_factors else "Standard analysis factors"

        prompt = f"""
Provide analysis for this college football matchup prediction:

Matchup: {team1_name} ({team1_record}) vs {team2_name} ({team2_record})
Predicted Winner: {winner}
Predicted Margin: {abs(margin)} points
Win Probability: {win_prob}%
Key Factors: {factors_text}

Write 3-4 sentences covering:
1. Why this prediction makes sense
2. What could change the outcome
3. Key players or matchups to watch

Focus on storylines and context that fans would find interesting.
"""

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300
        }
        
        response = bedrock_client.invoke_model(
            modelId=get_model_for_task("simple"),
            body=json.dumps(body)
        )
        
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
        
    except Exception as e:
        return f"Prediction analysis error: {str(e)}"

def get_gen_ai_status():
    """Get current status of Gen AI module"""
    return {
        'available': GEN_AI_AVAILABLE,
        'model': "arn:aws:bedrock:us-east-1:249154182031:inference-profile/us.anthropic.claude-opus-4-1-20250805-v1:0" if GEN_AI_AVAILABLE else None,
        'region': os.environ.get('AWS_REGION', 'us-east-1'),
        'functions': [
            'explain_game_impact',
            'generate_weekly_preview', 
            'explain_team_ranking',
            'enhance_matchup_prediction'
        ] if GEN_AI_AVAILABLE else []
    }

# Test when this file is run directly
if __name__ == "__main__":
    result = test_gen_ai_connection()
    print(f"Gen AI Test Result: {result}")

def process_natural_language_query(query, context_data=None):
    """Process natural language queries - WITH CACHING AND TRIMMING"""
    if not GEN_AI_AVAILABLE:
        return "AI query processing temporarily unavailable"
    
    # Create cache key from query and limited context
    cache_key = get_cache_key(query, str(context_data)[:500] if context_data else "")
    
    def _make_api_call():
        try:
            # TRIMMED CONTEXT - only top 10 teams and recent games
            context_parts = []
            
            if context_data:
                # Top 10 rankings only (not 25)
                if 'top_25' in context_data:
                    rankings_text = "Current Top 10:\n"
                    for i, team in enumerate(context_data['top_25'][:10], 1):  # LIMITED to 10
                        record = f"{team.get('total_wins', 0)}-{team.get('total_losses', 0)}"
                        rankings_text += f"#{i}. {team['team']} ({record})\n"
                    context_parts.append(rankings_text)
                
                # Only last 5 games (not 10)
                if 'recent_games' in context_data:
                    games_text = "Recent Games:\n"
                    for game in context_data['recent_games'][:5]:  # LIMITED to 5
                        games_text += f"- {game['away_team']} {game['away_score']}-{game['home_score']} {game['home_team']}\n"
                    context_parts.append(games_text)
                
                # Limited team stats
                if 'team_stats' in context_data:
                    for team_name, stats in list(context_data['team_stats'].items())[:2]:  # MAX 2 teams
                        team_text = f"\n{team_name}: {stats.get('wins', 0)}-{stats.get('losses', 0)}, #{stats.get('rank', 'NR')}\n"
                        context_parts.append(team_text)
            
            context_text = "\n".join(context_parts) if context_parts else "Limited data available."

            # SHORTER PROMPT
            prompt = f"""Answer this CFB question briefly using the data:

DATA:
{context_text}

QUESTION: {query}

Answer in 2-3 sentences:"""

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,  # REDUCED from 500
                "temperature": 0.7
            }
            
            response = bedrock_client.invoke_model(
                modelId=get_model_for_task("simple"),
                body=json.dumps(body)
            )
            
            result = json.loads(response['body'].read())
            return result['content'][0]['text']
            
        except Exception as e:
            return f"Error processing query: {str(e)}"
    
    return cached_ai_call(cache_key, _make_api_call)


def generate_weekly_report(context_data):
    """Generate weekly report - USING FAST MODEL"""
    if not GEN_AI_AVAILABLE:
        return "Weekly report generation unavailable"

    cache_key = get_cache_key(str(context_data)[:500])  # Even shorter cache key
    
    def _make_api_call():
        try:
            # MINIMAL CONTEXT for speed
            recent_games = context_data.get('recent_games', [])[:5]  # Only 5 games
            ranking_changes = context_data.get('ranking_changes', [])[:10]  # Only 10 changes

            # Ultra-compact context
            games_summary = []
            for g in recent_games:
                away = g.get('away_team', '')
                home = g.get('home_team', '')
                ascore = g.get('away_score', '')
                hscore = g.get('home_score', '')
                games_summary.append(f"{away} {ascore}-{hscore} {home}")

            changes_summary = []
            for c in ranking_changes[:5]:  # Only top 5 changes
                team = c.get('team', '')
                move = c.get('movement_text', '')
                if '▲' in move or '▼' in move:
                    changes_summary.append(f"{team} {move}")

            # ULTRA-SHORT PROMPT
            prompt = f"""Write a brief CFB weekly summary (2 paragraphs max):

Results: {'; '.join(games_summary)}
Rankings: {'; '.join(changes_summary)}

Remember: 12-team playoff means ranks #1-12 all make playoffs. Be factual, not dramatic."""

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 250,  # MUCH shorter
                "temperature": 0.1
            }

            response = bedrock_client.invoke_model(
                modelId=get_model_for_task("simple"),  # FAST MODEL
                body=json.dumps(body)
            )
            
            result = json.loads(response['body'].read())
            return result['content'][0]['text'].strip()
            
        except Exception as e:
            return f"Report error: {str(e)}"
    
    return cached_ai_call(cache_key, _make_api_call)

def get_ai_cache_stats():
    """Get cache statistics for monitoring"""
    total_entries = len(ai_response_cache)
    total_size = sum(len(str(v)) for v in ai_response_cache.values())
    
    return {
        'total_entries': total_entries,
        'total_size_bytes': total_size,
        'cache_hit_potential': f"{total_entries * 2}-{total_entries * 5} seconds saved"
    }

def clear_ai_cache():
    """Clear the AI response cache"""
    global ai_response_cache
    ai_response_cache.clear()
    return "AI cache cleared"




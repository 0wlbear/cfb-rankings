"""
CFB ML Tracking Module
Tracks prediction accuracy and optimizes temporal weights for college football rankings.
Designed for online learning during first season of data collection.
"""

import json
import time
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
import statistics

from flask import current_app
from models import db, CFBPredictionLog, CFBTemporalAnalysis, CFBAlgorithmPerformance
from sqlalchemy import func, and_, or_



# Global tracking variables
prediction_cache = {}
CONFIDENCE_THRESHOLD = 0.6  # Minimum confidence to track prediction
TEMPORAL_LEARNING_RATE = 0.1  # How quickly to adjust temporal weights

class CFBMLTracker:
    """Main class for CFB machine learning prediction tracking"""
    
    def __init__(self):
        self.current_week = None
        self.season_year = datetime.now().year
        
    def get_current_week(self):
        """Get current CFB week from your existing function"""
        try:
            from app import get_current_week_from_snapshots
            return get_current_week_from_snapshots()
        except:
            return '1'  # Fallback

def track_prediction(prediction_type='matchup'):
    """
    Decorator to automatically track CFB predictions
    
    Usage:
    @track_prediction('matchup')
    def predict_matchup_ultra_enhanced(team1, team2, location):
        # Your existing prediction logic
        return prediction_result
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Call the original prediction function
            result = func(*args, **kwargs)
            
            # Extract teams and prediction details
            if len(args) >= 2:
                team1_name = args[0]
                team2_name = args[1]
                location = args[2] if len(args) > 2 else kwargs.get('location', 'neutral')
                
                # Only track if prediction has sufficient confidence
                confidence = result.get('confidence_score', 0) if isinstance(result, dict) else 0.5
                
                if confidence >= CONFIDENCE_THRESHOLD:
                    try:
                        log_prediction(
                            team1_name=team1_name,
                            team2_name=team2_name,
                            location=location,
                            prediction_result=result,
                            prediction_type=prediction_type,
                            confidence=confidence
                        )
                    except Exception as e:
                        print(f"CFB ML Tracking Error: {e}")
            
            return result
        return wrapper
    return decorator

def log_prediction(team1_name, team2_name, location, prediction_result, prediction_type, confidence):
    """Log a CFB prediction to the database"""
    try:
        tracker = CFBMLTracker()
        current_week = tracker.get_current_week()
        
        # Extract key prediction components
        if isinstance(prediction_result, dict):
            predicted_winner = prediction_result.get('winner', team1_name)
            win_probability = prediction_result.get('win_probability', 50.0)
            predicted_margin = prediction_result.get('final_margin', 0.0)
            methodology = prediction_result.get('prediction_methodology', 'Ultra-Enhanced Analysis')
            
            # Get prediction factors
            factors = prediction_result.get('adjustments', {})
            factor_summary = {
                'base_margin': prediction_result.get('base_margin', 0.0),
                'total_adjustments': sum(factors.values()) if factors else 0.0,
                'key_factors': list(factors.keys())[:5],  # Top 5 factors
                'confidence_level': prediction_result.get('confidence', 'Medium')
            }
        else:
            # Fallback for non-dict results
            predicted_winner = team1_name
            win_probability = 50.0
            predicted_margin = 0.0
            methodology = 'Basic Analysis'
            factor_summary = {}
        
        # Create prediction log entry
        prediction_log = CFBPredictionLog(
            team1_name=team1_name,
            team2_name=team2_name,
            predicted_winner=predicted_winner,
            predicted_margin=predicted_margin,
            win_probability=win_probability,
            confidence_score=confidence,
            week=current_week,
            season_year=tracker.season_year,
            prediction_type=prediction_type,
            location=location,
            methodology=methodology,
            prediction_factors=json.dumps(factor_summary)
        )
        
        db.session.add(prediction_log)
        db.session.commit()
        
        print(f"✅ CFB Prediction logged: {team1_name} vs {team2_name} (Week {current_week})")
        
        # Update temporal analysis
        update_temporal_analysis(current_week, confidence)
        
        return prediction_log.id
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error logging CFB prediction: {e}")
        return None


# Add this function to wherever you keep your ML tracking functions
# (probably in the same file as your @track_prediction decorator)



def log_actual_result(team1_name, team2_name, actual_winner, actual_margin, week=None, is_overtime=False):
    """Log actual game result and update prediction accuracy"""
    try:
        tracker = CFBMLTracker()
        if not week:
            week = tracker.get_current_week()
        
        # Find matching prediction(s)
        predictions = CFBPredictionLog.query.filter(
            and_(
                CFBPredictionLog.week == week,
                CFBPredictionLog.actual_result.is_(None),  # Not yet resolved
                or_(
                    and_(
                        CFBPredictionLog.team1_name == team1_name,
                        CFBPredictionLog.team2_name == team2_name
                    ),
                    and_(
                        CFBPredictionLog.team1_name == team2_name,
                        CFBPredictionLog.team2_name == team1_name
                    )
                )
            )
        ).all()
        
        results_updated = 0
        
        for prediction in predictions:
            # Calculate accuracy metrics
            winner_correct = (prediction.predicted_winner == actual_winner)
            margin_error = abs(prediction.predicted_margin - actual_margin)
            
            # Accuracy score: 100% for correct winner, adjusted for margin accuracy
            if winner_correct:
                base_accuracy = 100.0
                # Reduce accuracy based on margin error (max penalty 50 points)
                margin_penalty = min(50.0, margin_error * 2.0)
                accuracy_score = max(50.0, base_accuracy - margin_penalty)
            else:
                # Wrong winner: score based on how close the margin was
                accuracy_score = max(0.0, 50.0 - margin_error * 1.5)
            
            # Update prediction with actual results
            prediction.actual_winner = actual_winner
            prediction.actual_margin = actual_margin
            prediction.accuracy_score = accuracy_score
            prediction.margin_error = margin_error
            prediction.winner_correct = winner_correct
            prediction.is_overtime = is_overtime
            prediction.actual_result = json.dumps({
                'winner': actual_winner,
                'margin': actual_margin,
                'overtime': is_overtime,
                'logged_at': datetime.utcnow().isoformat()
            })
            prediction.updated_at = datetime.utcnow()
            
            results_updated += 1
            
            print(f"✅ Updated CFB prediction: {accuracy_score:.1f}% accuracy, {margin_error:.1f} margin error")
        
        if results_updated > 0:
            db.session.commit()
            
            # Update algorithm performance metrics
            update_algorithm_performance(week)
            
            # Update temporal analysis with actual results
            update_temporal_analysis_with_results(week)
            
            print(f"📊 Updated {results_updated} CFB prediction(s) for {team1_name} vs {team2_name}")
        else:
            print(f"⚠️ No matching CFB predictions found for {team1_name} vs {team2_name} in week {week}")
        
        return results_updated
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error logging CFB actual result: {e}")
        return 0

def update_temporal_analysis(week, confidence):
    """Update temporal analysis with new prediction data"""
    try:
        # Get or create temporal analysis record
        temporal_record = CFBTemporalAnalysis.query.filter_by(
            week=week,
            season_year=datetime.now().year
        ).first()
        
        if not temporal_record:
            temporal_record = CFBTemporalAnalysis(
                week=week,
                season_year=datetime.now().year,
                predictions_made=0,
                average_confidence=0.0,
                suggested_weight=get_current_temporal_weight(week)
            )
            db.session.add(temporal_record)
        
        # Update with new prediction
        temporal_record.predictions_made += 1
        
        # Update average confidence (running average)
        if temporal_record.predictions_made == 1:
            temporal_record.average_confidence = confidence
        else:
            # Running average formula
            n = temporal_record.predictions_made
            temporal_record.average_confidence = ((n-1) * temporal_record.average_confidence + confidence) / n
        
        temporal_record.updated_at = datetime.utcnow()
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating CFB temporal analysis: {e}")

def update_temporal_analysis_with_results(week):
    """Update temporal analysis when actual results come in"""
    try:
        # Get predictions for this week with actual results
        week_predictions = CFBPredictionLog.query.filter(
            and_(
                CFBPredictionLog.week == week,
                CFBPredictionLog.season_year == datetime.now().year,
                CFBPredictionLog.winner_correct.isnot(None)
            )
        ).all()
        
        if not week_predictions:
            return
        
        # Calculate week performance metrics
        total_predictions = len(week_predictions)
        correct_winners = sum(1 for p in week_predictions if p.winner_correct)
        total_accuracy = sum(p.accuracy_score for p in week_predictions if p.accuracy_score)
        avg_margin_error = sum(p.margin_error for p in week_predictions if p.margin_error) / total_predictions
        
        winner_accuracy = (correct_winners / total_predictions) * 100.0
        avg_accuracy = total_accuracy / total_predictions if total_predictions > 0 else 0.0
        
        # Update temporal analysis record
        temporal_record = CFBTemporalAnalysis.query.filter_by(
            week=week,
            season_year=datetime.now().year
        ).first()
        
        if temporal_record:
            temporal_record.predictions_verified = total_predictions
            temporal_record.winner_accuracy = winner_accuracy
            temporal_record.average_accuracy = avg_accuracy
            temporal_record.average_margin_error = avg_margin_error
            
            # Calculate suggested temporal weight adjustment
            current_weight = get_current_temporal_weight(week)
            
            # If accuracy is significantly above/below average, suggest weight adjustment
            if avg_accuracy > 80.0:
                # High accuracy suggests this week's weight could be increased
                temporal_record.suggested_weight = min(1.3, current_weight + 0.05)
            elif avg_accuracy < 60.0:
                # Low accuracy suggests this week's weight should be decreased
                temporal_record.suggested_weight = max(0.6, current_weight - 0.05)
            else:
                # Average accuracy - keep current weight
                temporal_record.suggested_weight = current_weight
            
            temporal_record.updated_at = datetime.utcnow()
            db.session.commit()
            
            print(f"📈 CFB Temporal analysis updated for Week {week}: {avg_accuracy:.1f}% accuracy")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating CFB temporal analysis with results: {e}")

def update_algorithm_performance(week):
    """Update overall algorithm performance metrics"""
    try:
        print("=== DEBUG: Starting performance calculation ===")
        # Get all predictions with results
        all_predictions = CFBPredictionLog.query.filter(
            and_(
                CFBPredictionLog.season_year == datetime.now().year,
                CFBPredictionLog.winner_correct.isnot(None)
            )
        ).all()

        print(f"DEBUG: Found {len(all_predictions)} predictions with winner_correct set")
        
        if not all_predictions:
            print("DEBUG: No predictions found, returning early")
            return
        
        # Calculate overall metrics
        # Calculate overall metrics
        total_count = len(all_predictions)
        winner_correct_count = sum(1 for p in all_predictions if p.winner_correct)

        # Calculate average margin error (this field exists)
        predictions_with_margin_error = [p for p in all_predictions if p.margin_error is not None]
        avg_margin_error = sum(p.margin_error for p in predictions_with_margin_error) / len(predictions_with_margin_error) if predictions_with_margin_error else 0

        # Calculate overall accuracy based on winner_correct percentage
        avg_accuracy = (winner_correct_count / total_count) * 100.0

        # Skip confidence calculation since confidence_score doesn't exist
        avg_confidence = 0.5  # Default value
        
        winner_accuracy = (winner_correct_count / total_count) * 100.0
        
        # Analyze prediction factors
        factor_analysis = analyze_prediction_factors(all_predictions)
        
        # Get or create algorithm performance record
        performance_record = CFBAlgorithmPerformance.query.filter_by(
            season_year=datetime.now().year,
            # algorithm_version='ultra_enhanced_v1'
        ).first()
        
        if not performance_record:
            performance_record = CFBAlgorithmPerformance(
                season_year=datetime.now().year,
                # algorithm_version='ultra_enhanced_v1',
                prediction_count=0
            )
            db.session.add(performance_record)
        
        # Update performance metrics
        performance_record.prediction_count = total_count
        performance_record.winner_accuracy = winner_accuracy
        performance_record.average_accuracy = avg_accuracy
        performance_record.average_margin_error = avg_margin_error
        performance_record.average_confidence = avg_confidence
        performance_record.factor_importance = json.dumps(factor_analysis)
        
        # Generate optimization suggestions
        suggestions = generate_optimization_suggestions(
            winner_accuracy, avg_accuracy, avg_margin_error, factor_analysis
        )
        performance_record.optimization_suggestions = json.dumps(suggestions)
        performance_record.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        print(f"🎯 CFB Algorithm performance updated: {winner_accuracy:.1f}% winner accuracy, {avg_accuracy:.1f}% overall")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating CFB algorithm performance: {e}")

def analyze_prediction_factors(predictions):
    """Analyze which prediction factors are most important"""
    factor_impact = defaultdict(list)
    
    for prediction in predictions:
        if prediction.prediction_factors_json:
            try:
                factors = json.loads(prediction.prediction_factors_json)
                
                # Calculate accuracy score since the field doesn't exist
                if prediction.winner_correct is True:
                    calculated_accuracy = 100.0
                elif prediction.winner_correct is False:
                    calculated_accuracy = 0.0
                else:
                    continue  # Skip if no result
                
                # Analyze correlation between factors and accuracy
                for factor_name in factors.get('key_factors', []):
                    factor_impact[factor_name].append(calculated_accuracy)
                    
            except (json.JSONDecodeError, KeyError):
                continue
    
    # Calculate average accuracy for each factor
    factor_importance = {}
    for factor, accuracies in factor_impact.items():
        if len(accuracies) >= 3:  # Need at least 3 samples
            avg_accuracy = statistics.mean(accuracies)
            factor_importance[factor] = {
                'average_accuracy': avg_accuracy,
                'sample_count': len(accuracies),
                'accuracy_variance': statistics.variance(accuracies) if len(accuracies) > 1 else 0
            }
    
    # Sort by average accuracy (descending)
    sorted_factors = sorted(
        factor_importance.items(),
        key=lambda x: x[1]['average_accuracy'],
        reverse=True
    )
    
    return dict(sorted_factors[:10])  # Top 10 factors

def generate_optimization_suggestions(winner_accuracy, avg_accuracy, avg_margin_error, factor_analysis):
    """Generate actionable optimization suggestions"""
    suggestions = []
    
    # Accuracy-based suggestions
    if winner_accuracy < 60.0:
        suggestions.append({
            'type': 'critical',
            'category': 'Winner Prediction',
            'suggestion': 'Winner accuracy is below 60%. Consider increasing weight of strongest prediction factors.',
            'priority': 'high'
        })
    elif winner_accuracy > 75.0:
        suggestions.append({
            'type': 'positive',
            'category': 'Winner Prediction',
            'suggestion': f'Excellent winner accuracy ({winner_accuracy:.1f}%). Current approach is working well.',
            'priority': 'low'
        })
    
    # Margin error suggestions
    if avg_margin_error > 15.0:
        suggestions.append({
            'type': 'improvement',
            'category': 'Margin Prediction',
            'suggestion': f'Average margin error is {avg_margin_error:.1f} points. Consider fine-tuning point differential calculations.',
            'priority': 'medium'
        })
    elif avg_margin_error < 8.0:
        suggestions.append({
            'type': 'positive',
            'category': 'Margin Prediction',
            'suggestion': f'Low margin error ({avg_margin_error:.1f} points). Margin predictions are accurate.',
            'priority': 'low'
        })
    
    # Factor-based suggestions
    if factor_analysis:
        best_factor = max(factor_analysis.items(), key=lambda x: x[1]['average_accuracy'])
        worst_factor = min(factor_analysis.items(), key=lambda x: x[1]['average_accuracy'])
        
        suggestions.append({
            'type': 'insight',
            'category': 'Factor Analysis',
            'suggestion': f'Most reliable factor: "{best_factor[0]}" ({best_factor[1]["average_accuracy"]:.1f}% avg accuracy)',
            'priority': 'medium'
        })
        
        if worst_factor[1]['average_accuracy'] < 50.0:
            suggestions.append({
                'type': 'warning',
                'category': 'Factor Analysis',
                'suggestion': f'Least reliable factor: "{worst_factor[0]}" ({worst_factor[1]["average_accuracy"]:.1f}% avg accuracy). Consider reducing weight.',
                'priority': 'medium'
            })
    
    # Temporal suggestions
    suggestions.append({
        'type': 'temporal',
        'category': 'Temporal Weights',
        'suggestion': 'Review temporal analysis for week-specific accuracy patterns. Early season games may need different weighting.',
        'priority': 'medium'
    })
    
    return suggestions

def get_current_temporal_weight(week):
    """Get current temporal weight for a week from your existing system"""
    try:
        from app import get_temporal_weight_by_week
        return get_temporal_weight_by_week(week)
    except:
        # Fallback weights if import fails
        fallback_weights = {
            '1': 0.65, '2': 0.75, '3': 0.8, '4': 0.85, '5': 0.9,
            '6': 0.95, '7': 1.0, '8': 1.0, '9': 1.0, '10': 1.0,
            '11': 1.05, '12': 1.1, '13': 1.15, 'Bowls': 1.08, 'CFP': 1.25
        }
        return fallback_weights.get(str(week), 1.0)

# Data Export Functions

def export_prediction_data(format='json', weeks=None):
    """Export prediction data for analysis"""
    try:
        query = CFBPredictionLog.query.filter(
            CFBPredictionLog.season_year == datetime.now().year
        )
        
        if weeks:
            query = query.filter(CFBPredictionLog.week.in_(weeks))
        
        predictions = query.all()
        
        if format == 'json':
            return export_predictions_json(predictions)
        elif format == 'csv':
            return export_predictions_csv(predictions)
        else:
            return {'error': 'Unsupported format'}
            
    except Exception as e:
        return {'error': str(e)}

def export_predictions_json(predictions):
    """Export predictions as JSON"""
    data = []
    for pred in predictions:
        data.append({
            'id': pred.id,
            'week': pred.week,
            'team1': pred.team1_name,
            'team2': pred.team2_name,
            'predicted_winner': pred.predicted_winner,
            'predicted_margin': pred.predicted_margin,
            'win_probability': pred.win_probability,
            'confidence': pred.confidence_score,
            'actual_winner': pred.actual_winner,
            'actual_margin': pred.actual_margin,
            'accuracy_score': pred.accuracy_score,
            'winner_correct': pred.winner_correct,
            'margin_error': pred.margin_error,
            'methodology': pred.methodology,
            'location': pred.location,
            'prediction_date': pred.prediction_date.isoformat() if pred.prediction_date else None,
            'factors': json.loads(pred.prediction_factors) if pred.prediction_factors else {}
        })
    
    return {
        'total_predictions': len(data),
        'season_year': datetime.now().year,
        'export_date': datetime.utcnow().isoformat(),
        'predictions': data
    }

def export_predictions_csv(predictions):
    """Export predictions as CSV data"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Week', 'Team1', 'Team2', 'Predicted_Winner', 'Predicted_Margin',
        'Win_Probability', 'Confidence', 'Actual_Winner', 'Actual_Margin',
        'Accuracy_Score', 'Winner_Correct', 'Margin_Error', 'Methodology',
        'Location', 'Prediction_Date'
    ])
    
    # Write data
    for pred in predictions:
        writer.writerow([
            pred.id, pred.week, pred.team1_name, pred.team2_name,
            pred.predicted_winner, pred.predicted_margin, pred.win_probability,
            pred.confidence_score, pred.actual_winner, pred.actual_margin,
            pred.accuracy_score, pred.winner_correct, pred.margin_error,
            pred.methodology, pred.location,
            pred.prediction_date.isoformat() if pred.prediction_date else ''
        ])
    
    csv_data = output.getvalue()
    output.close()
    
    return csv_data

def get_ml_dashboard_data():
    """Get comprehensive data for ML dashboard"""
    try:
        current_year = datetime.now().year
        
        # Get overall performance metrics
        performance = CFBAlgorithmPerformance.query.filter_by(
            season_year=current_year
        ).first()
        
        # Get temporal analysis by week
        temporal_data = CFBTemporalAnalysis.query.filter_by(
            season_year=current_year
        ).order_by(CFBTemporalAnalysis.week).all()
        
        # Get recent predictions
        recent_predictions = CFBPredictionLog.query.filter(
            CFBPredictionLog.season_year == current_year
        ).order_by(CFBPredictionLog.prediction_date.desc()).limit(20).all()
        
        # Calculate weekly accuracy trends
        weekly_accuracy = []
        for week_data in temporal_data:
            if week_data.predictions_verified and week_data.predictions_verified > 0:
                weekly_accuracy.append({
                    'week': week_data.week,
                    'accuracy': week_data.average_accuracy,
                    'predictions': week_data.predictions_verified,
                    'confidence': week_data.average_confidence
                })
        
        return {
            'performance': performance,
            'temporal_data': temporal_data,
            'recent_predictions': recent_predictions,
            'weekly_accuracy': weekly_accuracy,
            'total_weeks': len(temporal_data),
            'total_predictions': performance.prediction_count if performance else 0
        }
        
    except Exception as e:
        print(f"❌ Error getting CFB ML dashboard data: {e}")
        return None

# Quick setup function
def setup_cfb_ml_tracking():
    """One-time setup for CFB ML tracking"""
    try:
        # Ensure all tables exist
        db.create_all()
        
        # Initialize current season performance record
        current_year = datetime.now().year
        performance = CFBAlgorithmPerformance.query.filter_by(
            season_year=current_year,
            # algorithm_version='ultra_enhanced_v1'
        ).first()
        
        if not performance:
            performance = CFBAlgorithmPerformance(
                season_year=current_year,
                # algorithm_version='ultra_enhanced_v1',
                prediction_count=0,
                winner_accuracy=0.0,
                average_accuracy=0.0,
                average_margin_error=0.0,
                average_confidence=0.0
            )
            db.session.add(performance)
            db.session.commit()
            print("✅ CFB ML tracking initialized for season", current_year)
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up CFB ML tracking: {e}")
        return False


def get_enhanced_ml_dashboard_data():
    """Get enhanced ML dashboard data with automated vs manual breakdowns and FCS exclusion stats"""
    try:
        from datetime import datetime, timedelta
        
        # Get all predictions
        all_predictions = CFBPredictionLog.query.all()
        
        # Calculate FCS exclusion statistics
        fcs_exclusions = calculate_fcs_exclusion_stats()
        
        if not all_predictions:
            return {
                'total_predictions': 0,
                'manual_predictions': 0,
                'automated_predictions': 0,
                'recent_predictions': [],
                'accuracy_by_type': {},
                'weekly_breakdown': {},
                'fcs_exclusions': fcs_exclusions
            }
        
        # Separate by prediction type
        manual_predictions = [p for p in all_predictions if p.prediction_type == 'manual']
        automated_predictions = [p for p in all_predictions if p.prediction_type == 'automated']
        completed_predictions = [p for p in all_predictions if p.game_completed]
        
        # Calculate accuracy by type
        accuracy_by_type = {}
        
        for pred_type, predictions in [('manual', manual_predictions), ('automated', automated_predictions)]:
            completed = [p for p in predictions if p.game_completed and p.winner_correct is not None]
            
            if completed:
                correct = len([p for p in completed if p.winner_correct])
                accuracy = round((correct / len(completed)) * 100, 1)
                avg_margin_error = round(sum([p.margin_error for p in completed if p.margin_error]) / len(completed), 1)
            else:
                correct = 0
                accuracy = 0
                avg_margin_error = 0
            
            accuracy_by_type[pred_type] = {
                'total': len(predictions),
                'completed': len(completed),
                'correct': correct,
                'accuracy': accuracy,
                'avg_margin_error': avg_margin_error
            }
        
        # Weekly breakdown with FCS exclusion info
        weekly_breakdown = {}
        weeks = list(set([p.week for p in all_predictions]))
        weeks.sort(key=lambda x: int(x) if x.isdigit() else 999)
        
        for week in weeks:
            week_predictions = [p for p in all_predictions if p.week == week]
            week_manual = [p for p in week_predictions if p.prediction_type == 'manual']
            week_automated = [p for p in week_predictions if p.prediction_type == 'automated']
            week_completed = [p for p in week_predictions if p.game_completed]
            
            # Calculate FCS exclusions for this specific week
            week_fcs_stats = calculate_week_fcs_exclusions(week)
            
            weekly_breakdown[week] = {
                'total': len(week_predictions),
                'manual': len(week_manual),
                'automated': len(week_automated),
                'completed': len(week_completed),
                'pending': len(week_predictions) - len(week_completed),
                'fcs_excluded': week_fcs_stats['fcs_excluded'],
                'total_scheduled': week_fcs_stats['total_scheduled'],
                'fbs_games': week_fcs_stats['fbs_games']
            }
        
        # Recent predictions (last 20)
        recent_predictions = sorted(all_predictions, key=lambda x: x.prediction_date or datetime.min, reverse=True)[:20]
        
        # Calculate overall prediction coverage (how many FBS games we're predicting vs total FBS games)
        total_fbs_games = fcs_exclusions['total_fbs_games']
        prediction_coverage = round((len(all_predictions) / total_fbs_games * 100), 1) if total_fbs_games > 0 else 0
        
        return {
            'total_predictions': len(all_predictions),
            'manual_predictions': len(manual_predictions),
            'automated_predictions': len(automated_predictions),
            'completed_predictions': len(completed_predictions),
            'accuracy_by_type': accuracy_by_type,
            'weekly_breakdown': weekly_breakdown,
            'recent_predictions': [p.to_dict() for p in recent_predictions],
            'fcs_exclusions': fcs_exclusions,
            'prediction_coverage': prediction_coverage
        }
        
    except Exception as e:
        print(f"Error getting enhanced ML dashboard data: {e}")
        return None


def calculate_fcs_exclusion_stats():
    """Calculate FCS exclusion statistics across all scheduled games"""
    try:
        # Count total scheduled games (including FCS)
        total_scheduled = ScheduledGame.query.filter(ScheduledGame.completed == False).count()
        
        # Count FBS vs FBS games only
        fbs_scheduled = ScheduledGame.query.filter(
            ScheduledGame.completed == False,
            ~(ScheduledGame.home_team.ilike('%FCS%')),
            ~(ScheduledGame.away_team.ilike('%FCS%')),
            ScheduledGame.home_team != 'FCS',
            ScheduledGame.away_team != 'FCS'
        ).count()
        
        # Count completed games for historical context
        total_completed = ScheduledGame.query.filter(ScheduledGame.completed == True).count()
        
        fbs_completed = ScheduledGame.query.filter(
            ScheduledGame.completed == True,
            ~(ScheduledGame.home_team.ilike('%FCS%')),
            ~(ScheduledGame.away_team.ilike('%FCS%')),
            ScheduledGame.home_team != 'FCS',
            ScheduledGame.away_team != 'FCS'
        ).count()
        
        fcs_excluded_upcoming = total_scheduled - fbs_scheduled
        fcs_excluded_completed = total_completed - fbs_completed
        
        return {
            'total_scheduled': total_scheduled,
            'fbs_games': fbs_scheduled,
            'fcs_excluded': fcs_excluded_upcoming,
            'total_completed': total_completed,
            'fbs_completed': fbs_completed,
            'fcs_excluded_completed': fcs_excluded_completed,
            'total_fbs_games': fbs_scheduled + fbs_completed,
            'exclusion_percentage': round((fcs_excluded_upcoming / total_scheduled * 100), 1) if total_scheduled > 0 else 0
        }
        
    except Exception as e:
        print(f"Error calculating FCS exclusion stats: {e}")
        return {
            'total_scheduled': 0,
            'fbs_games': 0,
            'fcs_excluded': 0,
            'total_completed': 0,
            'fbs_completed': 0,
            'fcs_excluded_completed': 0,
            'total_fbs_games': 0,
            'exclusion_percentage': 0
        }


def calculate_week_fcs_exclusions(week):
    """Calculate FCS exclusions for a specific week"""
    try:
        # Count total scheduled games for this week
        total_scheduled = ScheduledGame.query.filter(
            ScheduledGame.week == str(week),
            ScheduledGame.completed == False
        ).count()
        
        # Count FBS vs FBS games for this week
        fbs_games = ScheduledGame.query.filter(
            ScheduledGame.week == str(week),
            ScheduledGame.completed == False,
            ~(ScheduledGame.home_team.ilike('%FCS%')),
            ~(ScheduledGame.away_team.ilike('%FCS%')),
            ScheduledGame.home_team != 'FCS',
            ScheduledGame.away_team != 'FCS'
        ).count()
        
        fcs_excluded = total_scheduled - fbs_games
        
        return {
            'total_scheduled': total_scheduled,
            'fbs_games': fbs_games,
            'fcs_excluded': fcs_excluded
        }
        
    except Exception as e:
        print(f"Error calculating week {week} FCS exclusions: {e}")
        return {
            'total_scheduled': 0,
            'fbs_games': 0,
            'fcs_excluded': 0
        }
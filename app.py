from flask import Flask, request, render_template
from models import db, Response
from marshmallow import Schema, fields, ValidationError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import os
from dotenv import load_dotenv
from datetime import timedelta, datetime
from sqlalchemy import func

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')

CORS(app=app, origins=['https://witrent-survey-frontend.vercel.app', 'witrent-insight-dash.lovable.app'])

db.init_app(app)
with app.app_context():
    db.create_all()

from flask import request, jsonify


# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,  
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

class SurveySchema(Schema):
    currentlyLooking = fields.Str(required=True, validate=lambda x: x in ['yes', 'no'])
    whenLookNext = fields.Str(allow_none=True)
    userType = fields.Str(required=True, validate=lambda x: x in ['student', 'shift-worker', 'other'])
    userTypeOther = fields.Str(allow_none=True)
    ageGroup = fields.Str(required=True)
    priorities = fields.List(fields.Str(), allow_none=True)
    maxBudget = fields.Str(allow_none=True)
    searchMethod = fields.Str(allow_none=True)
    biggestChallenge = fields.Str(required=True)
    paymentMethod = fields.Str(required=True)
    desiredFeatures = fields.List(fields.Str(), allow_none=True)
    wantsEarlyAccess = fields.Str(validate=lambda x: x in ['yes', 'no'])
    phoneNumber = fields.Str(allow_none=True)

@app.route('/submit', methods=['POST'])
@limiter.limit("5 per minute")
def submit_survey():
    try:
        # Validate input
        schema = SurveySchema()
        data = schema.load(request.get_json())
        
        # Create and save response
        response = Response(
            currently_looking=data['currentlyLooking'],
            when_look_next=data.get('whenLookNext'),
            user_type=data['userType'],
            user_type_other=data.get('userTypeOther'),
            age_group=data['ageGroup'],
            priorities=data.get('priorities', []),
            max_budget=data.get('maxBudget'),
            search_method=data.get('searchMethod'),
            biggest_challenge=data['biggestChallenge'],
            payment_method=data['paymentMethod'],
            desired_features=data.get('desiredFeatures', []),
            wants_early_access=data.get('wantsEarlyAccess', 'no'),
            phone_number=data.get('phoneNumber')
        )
        
        db.session.add(response)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'id': response.id,
            'message': 'Response saved successfully'
        }), 201

    except ValidationError as e:
        return jsonify({
            'success': False,
            'errors': e.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Submission failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/survey/responses', methods=['GET'])
def get_survey_responses():
    try:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Filter parameters (matching your frontend filters)
        user_type = request.args.get('userType')
        age_group = request.args.get('ageGroup')
        currently_looking = request.args.get('currentlyLooking')
        
        # Date range filter (converting from frontend format)
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')
        
        # Base query
        query = Response.query
        
        # Apply filters (matching your frontend filter options)
        if user_type:
            query = query.filter(Response.user_type == user_type)
        if age_group:
            query = query.filter(Response.age_group == age_group)
        if currently_looking:
            query = query.filter(Response.currently_looking == currently_looking.lower())
        
        # Date range filter
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Response.timestamp >= date_from)
            except ValueError:
                return jsonify({'error': 'Invalid dateFrom format. Use YYYY-MM-DD'}), 400
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(Response.timestamp <= date_to)
            except ValueError:
                return jsonify({'error': 'Invalid dateTo format. Use YYYY-MM-DD'}), 400
        
        # Paginate results
        paginated = query.order_by(Response.timestamp.desc()).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # Format response to match your frontend's SurveyResponse type
        responses = [{
            'id': r.id,
            'timestamp': r.timestamp.isoformat() + 'Z',
            'currently_looking': r.currently_looking,
            'when_look_next': r.when_look_next,
            'user_type': r.user_type,
            'age_group': r.age_group,
            'priorities': r.get_priorities_list(),
            'max_budget': r.max_budget,
            'search_method': r.search_method,
            'biggest_challenge': r.biggest_challenge,
            'desired_features': r.get_features_list()
        } for r in paginated.items]
        
        return jsonify({
            'data': responses,
            'pagination': {
                'total': paginated.total,
                'pages': paginated.pages,
                'current_page': paginated.page,
                'per_page': paginated.per_page
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/survey/analytics', methods=['GET'])
def get_survey_analytics():
    try:
        # Get filter parameters (same as responses endpoint)
        user_type = request.args.get('userType')
        age_group = request.args.get('ageGroup')
        currently_looking = request.args.get('currentlyLooking')
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')
        
        # Base query
        query = Response.query
        
        # Apply same filters as responses endpoint
        if user_type:
            query = query.filter(Response.user_type == user_type)
        if age_group:
            query = query.filter(Response.age_group == age_group)
        if currently_looking:
            query = query.filter(Response.currently_looking == currently_looking.lower())
        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Response.timestamp >= date_from)
        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Response.timestamp <= date_to)
        
        # Get all filtered responses
        responses = query.all()
        
        if not responses:
            return jsonify({'error': 'No survey data found'}), 404
        
        # Calculate analytics to match your frontend needs
        analytics = {
            'totalResponses': len(responses),
            'currentlyLookingPercentage': round(
                100 * sum(1 for r in responses if r.currently_looking == 'yes') / len(responses),
                1
            ),
            'userTypeDistribution': {},
            'ageGroupDistribution': {},
            'budgetDistribution': {},
            'topPriorities': [],
            'topChallenges': []
        }
        
        # User type distribution
        user_types = db.session.query(
            Response.user_type, 
            func.count(Response.id)
        ).group_by(Response.user_type).all()
        
        analytics['userTypeDistribution'] = {ut[0]: ut[1] for ut in user_types}
        
        # Age group distribution
        age_groups = db.session.query(
            Response.age_group, 
            func.count(Response.id)
        ).group_by(Response.age_group).all()
        
        analytics['ageGroupDistribution'] = {ag[0]: ag[1] for ag in age_groups}
        
        # Budget distribution
        budgets = db.session.query(
            Response.max_budget, 
            func.count(Response.id)
        ).group_by(Response.max_budget).all()
        
        analytics['budgetDistribution'] = {b[0]: b[1] for b in budgets if b[0]}
        
        # Top priorities (flatten lists and count)
        priorities = {}
        for r in responses:
            for p in r.get_priorities_list():
                priorities[p] = priorities.get(p, 0) + 1
                
        analytics['topPriorities'] = [
            {'priority': p, 'count': c} 
            for p, c in sorted(priorities.items(), key=lambda x: x[1], reverse=True)
        ][:5]  # Top 5
        
        # Top challenges
        challenges = db.session.query(
            Response.biggest_challenge, 
            func.count(Response.id)
        ).group_by(Response.biggest_challenge).all()
        
        analytics['topChallenges'] = [
            {'challenge': c[0], 'count': c[1]} 
            for c in sorted(challenges, key=lambda x: x[1], reverse=True)
        ][:5]  # Top 5
        
        return jsonify(analytics)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

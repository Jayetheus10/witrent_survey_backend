from flask import Flask, request, render_template
from models import db, Response
from marshmallow import Schema, fields, ValidationError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import os
from sqlalchemy import func
import logging
from logging.handlers import RotatingFileHandler
import sys

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')

CORS(app=app, origins=['https://witrent-survey-frontend.vercel.app', 'https://witrent-insight-dash.lovable.app'])

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


# Configure logging
file_handler = RotatingFileHandler('witrent_survey.log', maxBytes=10*1024*1024, backupCount=10)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
app.logger.addHandler(file_handler)
app.logger.addHandler(console_handler)
app.logger.setLevel(logging.INFO)

@app.route('/api/survey/responses', methods=['GET'])
def get_all_responses():
    try:
        app.logger.info("Fetching all survey responses")
        
        # Get all responses ordered by timestamp
        responses = Response.query.order_by(Response.timestamp.desc()).all()
        
        formatted_responses = [{
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
        } for r in responses]
        
        app.logger.info(f"Returning {len(responses)} total responses")
        return jsonify({
            'success': True,
            'data': formatted_responses,
            'count': len(responses)
        })
        
    except Exception as e:
        app.logger.error(f"Failed to fetch responses: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to fetch survey responses'
        }), 500

@app.route('/api/survey/analytics', methods=['GET'])
def get_complete_analytics():
    try:
        app.logger.info("Generating complete survey analytics")
        
        # Get all responses
        responses = Response.query.all()
        
        if not responses:
            app.logger.warning("No survey data found for analytics")
            return jsonify({
                'success': False,
                'error': 'No survey data available'
            }), 404
        
        # Calculate comprehensive analytics
        analytics = {
            'success': True,
            'summary': {
                'total_responses': len(responses),
                'currently_looking': sum(1 for r in responses if r.currently_looking == 'yes'),
                'not_looking': sum(1 for r in responses if r.currently_looking == 'no'),
                'earliest_response': min(r.timestamp for r in responses).isoformat() + 'Z',
                'latest_response': max(r.timestamp for r in responses).isoformat() + 'Z'
            },
            'demographics': {
                'user_types': dict(db.session.query(Response.user_type, func.count(Response.id))
                                 .group_by(Response.user_type).all()),
                'age_groups': dict(db.session.query(Response.age_group, func.count(Response.id))
                                  .group_by(Response.age_group).all())
            },
            'preferences': {
                'budgets': dict(db.session.query(Response.max_budget, func.count(Response.id))
                              .group_by(Response.max_budget).all()),
                'search_methods': dict(db.session.query(Response.search_method, func.count(Response.id))
                                     .group_by(Response.search_method).all())
            },
            'challenges': dict(db.session.query(Response.biggest_challenge, func.count(Response.id))
                             .group_by(Response.biggest_challenge).all()),
            'features': {}
        }
        
        # Calculate feature popularity
        features = {}
        for r in responses:
            for feature in r.get_features_list():
                features[feature] = features.get(feature, 0) + 1
        analytics['features'] = features
        
        # Calculate priority popularity
        priorities = {}
        for r in responses:
            for priority in r.get_priorities_list():
                priorities[priority] = priorities.get(priority, 0) + 1
        analytics['priorities'] = priorities
        
        app.logger.info("Successfully generated analytics")
        return jsonify(analytics)
        
    except Exception as e:
        app.logger.error(f"Failed to generate analytics: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to generate analytics'
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f"404 Not Found: {request.url}")
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 Internal Server Error: {str(error)}", exc_info=True)
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

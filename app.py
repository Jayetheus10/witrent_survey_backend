from flask import Flask, request, render_template
from models import db, Response
from marshmallow import Schema, fields, ValidationError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import os

app = Flask(__name__)


app.config['SECRET_KEY'] = 'witrent_secret_key_that_is_super_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

CORS(app=app, origins=['*'])

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

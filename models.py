from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Response(db.Model):
    __tablename__ = 'responses'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Section A: Basic Profile
    currently_looking = db.Column(db.String(3), nullable=False)  # 'yes' or 'no'
    when_look_next = db.Column(db.String(20))  # nullable for active seekers
    user_type = db.Column(db.String(20), nullable=False)  # 'student', 'shift-worker', 'other'
    user_type_other = db.Column(db.String(50))  # only if user_type == 'other'
    age_group = db.Column(db.String(10), nullable=False)  # e.g. '18-24'
    
    # Section B: Rental Preferences (only if currently_looking == 'yes')
    priorities = db.Column(db.JSON)  # Stores list like ['Price', 'Safety']
    max_budget = db.Column(db.String(20))  # e.g. '1500-2000'
    search_method = db.Column(db.String(20))  # 'app', 'website', etc.
    
    # Section C: Pain Points
    biggest_challenge = db.Column(db.String(50), nullable=False)  # e.g. 'scams'
    payment_method = db.Column(db.String(20), nullable=False)  # 'cash', 'eft', etc.
    
    # Section D: Feature Wishlist
    desired_features = db.Column(db.JSON)  # Stores list like ['Verified listings', ...]
    
    # Section E: Early Access
    wants_early_access = db.Column(db.String(3), default='no')  # 'yes' or 'no'
    phone_number = db.Column(db.String(20))  # only if wants_early_access == 'yes'

    def __repr__(self):
        return f'<Response {self.id} ({self.user_type})>'

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'currently_looking': self.currently_looking,
            'when_look_next': self.when_look_next,
            'user_type': self.user_type,
            'user_type_other': self.user_type_other,
            'age_group': self.age_group,
            'priorities': self.priorities,
            'max_budget': self.max_budget,
            'search_method': self.search_method,
            'biggest_challenge': self.biggest_challenge,
            'payment_method': self.payment_method,
            'desired_features': self.desired_features,
            'wants_early_access': self.wants_early_access,
            'phone_number': self.phone_number
        }
# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp
# Create db instance here
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    two_factor_secret = db.Column(db.String(16))
    bio = db.Column(db.Text, default="")
    balance = db.Column(db.Float, default=0.0)
    last_generation = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    @property
    def is_authenticated(self):
        return True  # This is always True for a valid user object
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_totp_uri(self):
        return pyotp.totp.TOTP(self.two_factor_secret).provisioning_uri(
            name=self.username, 
            issuer_name="Banknote Gallery"
        )
    
    def verify_totp(self, token):
        return pyotp.TOTP(self.two_factor_secret).verify(token)
    
    # In your User model
    # In your User model (models.py)
    # In User model - only check cooldown and database
    def can_generate_money(self):
        # Check cooldown period
        if self.last_generation and (datetime.utcnow() - self.last_generation).days < 7:
            return False
        
        # Check for pending tasks
        from models import GenerationTask
        pending_tasks = GenerationTask.query.filter_by(
            user_id=self.id, 
            status='processing'
        ).first()
        
        return pending_tasks is None
        
    def days_until_next_generation(self):
        if not self.last_generation:
            return 0
        next_generation = self.last_generation + timedelta(days=365)
        days_left = (next_generation - datetime.utcnow()).days
        return max(0, days_left)

class GenerationTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    message = db.Column(db.Text, default="")  # Add this field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    user = db.relationship('User', backref=db.backref('generation_tasks', lazy=True))

class Banknote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    serial_number = db.Column(db.String(100), nullable=False)  # No unique constraint
    seed_text = db.Column(db.Text, nullable=False)
    denomination = db.Column(db.String(50), nullable=False)
    side = db.Column(db.String(10), nullable=False)  # 'front' or 'back'
    svg_path = db.Column(db.String(500), nullable=False)
    png_path = db.Column(db.String(500))
    pdf_path = db.Column(db.String(500))
    qr_data = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add composite unique constraint instead of individual unique
    __table_args__ = (
        db.UniqueConstraint('serial_number', 'side', name='unique_serial_side'),
    )
    
    user = db.relationship('User', backref=db.backref('banknotes', lazy=True))

class SerialNumber(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # This should be the only primary key
    serial = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    banknote_id = db.Column(db.Integer, db.ForeignKey('banknote.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('serials', lazy=True))
    banknote = db.relationship('Banknote', backref=db.backref('serials', lazy=True))
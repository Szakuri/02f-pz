from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship


class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Klucz obcy do tabeli User

    user = db.relationship("User", back_populates="positions")  # Relacja do User
    keywords = db.relationship("Keyword", back_populates="position", cascade="all, delete-orphan")


class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey("position.id"), nullable=False)
    weight = db.Column(db.Integer, nullable=False, default=1)

    position = db.relationship("Position", back_populates="keywords")  # Relacja z Position


class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cv_text = db.Column(db.Text, nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey("position.id"), nullable=False)
    points = db.Column(db.Integer, default=0)
    first_words = db.Column(db.String(100), nullable=True)
    email_cv = db.Column(db.String(120), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    user = db.relationship("User", back_populates="candidates")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    positions = db.relationship("Position", back_populates="user")
    candidates = db.relationship("Candidate", back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


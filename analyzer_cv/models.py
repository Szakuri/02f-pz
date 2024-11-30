from app import db
from werkzeug.security import generate_password_hash, check_password_hash


class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )
    is_global = db.Column(
        db.Boolean, default=False
    )
    keywords = db.relationship("Keyword", backref="position", lazy=True)


class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey("position.id"), nullable=False)


class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cv_text = db.Column(db.Text, nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey("position.id"), nullable=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    positions = db.relationship("Position", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

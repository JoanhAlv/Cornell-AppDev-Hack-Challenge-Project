from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Keep the original column name so existing prototype accounts still work.
    username = db.Column("email", db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    token_hash = db.Column(db.String(64), unique=True)
    coins = db.Column(db.Integer, nullable=False, default=0)
    study_sessions = db.relationship("FocusSession", back_populates="user", cascade="all, delete-orphan")
    purchases = db.relationship("Purchase", back_populates="user", cascade="all, delete-orphan")


# Reuse the old focus-session table so previously saved completed sessions remain available.
class FocusSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False)
    elapsed_seconds = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    coins_earned = db.Column(db.Integer, nullable=False, default=0)
    user = db.relationship("User", back_populates="study_sessions")


class Decoration(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cost = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(500), nullable=False, default="")
    purchases = db.relationship("Purchase", back_populates="decoration")


class Purchase(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    decoration_id = db.Column(db.String(100), db.ForeignKey("decoration.id"), primary_key=True)
    user = db.relationship("User", back_populates="purchases")
    decoration = db.relationship("Decoration", back_populates="purchases")

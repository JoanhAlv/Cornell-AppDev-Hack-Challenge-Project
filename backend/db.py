from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column("email", db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    token_hash = db.Column(db.String(64), unique=True)
    coins = db.Column(db.Integer, nullable=False, default=0)

    focus_sessions = db.relationship("FocusSession", back_populates="user", cascade="all, delete-orphan")
    settings = db.relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    blocked_apps = db.relationship("BlockedApp", back_populates="user", cascade="all, delete-orphan")

    def serialize(self):
        return {"id": self.id, "name": self.name, "username": self.username, "coins": self.coins}


class FocusSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False)
    elapsed_seconds = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    coins_earned = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("User", back_populates="focus_sessions")

    def serialize(self, now):
        elapsed = self.elapsed_seconds
        if self.status == "active":
            elapsed += max(0, int((now - self.started_at).total_seconds()))
        elapsed = min(elapsed, self.duration_seconds)
        return {
            "id": self.id, "user_id": self.user_id,
            "duration_seconds": self.duration_seconds,
            "elapsed_seconds": elapsed,
            "remaining_seconds": self.duration_seconds - elapsed,
            "status": self.status, "coins_earned": self.coins_earned
        }


class UserSettings(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    default_duration_minutes = db.Column(db.Integer, nullable=False, default=10)
    deep_focus = db.Column(db.Boolean, nullable=False, default=False)
    user = db.relationship("User", back_populates="settings")


class BlockedApp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    app_identifier = db.Column(db.String(255), nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "app_identifier"),)
    user = db.relationship("User", back_populates="blocked_apps")

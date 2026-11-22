from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    token_hash = db.Column(db.String(64), unique=True)
    coins = db.Column(db.Integer, nullable=False, default=0)

    def serialize(self):
        return {"id": self.id, "name": self.name, "email": self.email, "coins": self.coins}


class FocusSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False)
    elapsed_seconds = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    coins_earned = db.Column(db.Integer, nullable=False, default=0)

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

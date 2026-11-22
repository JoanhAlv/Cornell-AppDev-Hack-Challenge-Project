import hashlib
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from db import db, BlockedApp, FocusSession, User, UserSettings

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///touchdown.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()


def now_utc():
    return datetime.utcnow()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def require_user(route):
    @wraps(route)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401
        user = User.query.filter_by(token_hash=token_hash(header[7:])).first()
        if user is None:
            return jsonify({"error": "Invalid token"}), 401
        return route(user, *args, **kwargs)
    return wrapped


def body_json():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def issue_token(user):
    token = secrets.token_urlsafe(32)
    user.token_hash = token_hash(token)
    db.session.commit()
    return token


# CREATE AN ACCOUNT
@app.route("/api/users/", methods=["POST"])
def create_user():
    body = body_json()
    username, password = body.get("username"), body.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or len(password) < 8:
        return jsonify({"error": "Username and a password of at least 8 characters are required"}), 400
    username = username.strip().lower()
    if len(username) > 100:
        return jsonify({"error": "Username must be 100 characters or fewer"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already registered"}), 409
    user = User(name=username, username=username, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    return jsonify({"user": user.serialize(), "token": issue_token(user)}), 201


# LOG IN AND LOG OUT
@app.route("/api/login/", methods=["POST"])
def login():
    body = body_json()
    username, password = body.get("username"), body.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "Invalid username or password"}), 401
    user = User.query.filter_by(username=username.strip().lower()).first()
    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid username or password"}), 401
    return jsonify({"user": user.serialize(), "token": issue_token(user)}), 200


@app.route("/api/logout/", methods=["POST"])
@require_user
def logout(user):
    user.token_hash = None
    db.session.commit()
    return jsonify({"message": "Logged out"}), 200


# GET THE CURRENT USER'S PROFILE
@app.route("/api/me/", methods=["GET"])
@require_user
def get_profile(user):
    return jsonify(user.serialize()), 200


# READ OR UPDATE TIMER AND APP BLOCKING PREFERENCES
@app.route("/api/settings/", methods=["GET", "PUT"])
@require_user
def settings(user):
    settings = UserSettings.query.filter_by(user_id=user.id).first()
    if settings is None:
        settings = UserSettings(user_id=user.id, default_duration_minutes=10, deep_focus=False)
        db.session.add(settings)
    if request.method == "PUT":
        body = body_json()
        duration = body.get("default_duration_minutes", settings.default_duration_minutes)
        deep_focus = body.get("deep_focus", settings.deep_focus)
        apps = body.get("blocked_apps")
        if type(duration) is not int or not 1 <= duration <= 180:
            return jsonify({"error": "default_duration_minutes must be an integer from 1 to 180"}), 400
        if type(deep_focus) is not bool:
            return jsonify({"error": "deep_focus must be a boolean"}), 400
        if apps is not None and (not isinstance(apps, list) or any(not isinstance(a, str) or not a.strip() or len(a) > 255 for a in apps)):
            return jsonify({"error": "blocked_apps must be a list of app identifiers"}), 400
        settings.default_duration_minutes = duration
        settings.deep_focus = deep_focus
        if apps is not None:
            BlockedApp.query.filter_by(user_id=user.id).delete()
            for identifier in sorted(set(a.strip() for a in apps)):
                db.session.add(BlockedApp(user_id=user.id, app_identifier=identifier))
    db.session.commit()
    apps = BlockedApp.query.filter_by(user_id=user.id).order_by(BlockedApp.app_identifier).all()
    return jsonify({"default_duration_minutes": settings.default_duration_minutes, "deep_focus": settings.deep_focus, "blocked_apps": [a.app_identifier for a in apps]}), 200


# LIST SESSIONS SO THE CLIENT CAN RESTORE A TIMER OR SHOW HISTORY
@app.route("/api/focus-sessions/", methods=["GET"])
@require_user
def list_focus(user):
    sessions = FocusSession.query.filter_by(user_id=user.id).order_by(FocusSession.id.desc()).all()
    now = now_utc()
    return jsonify({"sessions": [session.serialize(now) for session in sessions]}), 200


# START A FOCUS SESSION
@app.route("/api/focus-sessions/", methods=["POST"])
@require_user
def start_focus(user):
    duration = body_json().get("duration_minutes")
    if type(duration) is not int or not 1 <= duration <= 180:
        return jsonify({"error": "duration_minutes must be an integer from 1 to 180"}), 400
    if FocusSession.query.filter_by(user_id=user.id).filter(FocusSession.status.in_(["active", "paused"])).first():
        return jsonify({"error": "Finish or cancel your current session first"}), 409
    session = FocusSession(user_id=user.id, duration_seconds=duration * 60, started_at=now_utc())
    db.session.add(session)
    db.session.commit()
    return jsonify(session.serialize(now_utc())), 201


def find_session(user, session_id):
    return FocusSession.query.filter_by(id=session_id, user_id=user.id).first()


@app.route("/api/focus-sessions/<int:session_id>/", methods=["GET"])
@require_user
def get_focus(user, session_id):
    session = find_session(user, session_id)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session.serialize(now_utc())), 200


# PAUSE, RESUME, COMPLETE, OR CANCEL A SESSION
@app.route("/api/focus-sessions/<int:session_id>/<action>/", methods=["POST"])
@require_user
def update_focus(user, session_id, action):
    session = find_session(user, session_id)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    now = now_utc()
    if action == "pause" and session.status == "active":
        session.elapsed_seconds = session.serialize(now)["elapsed_seconds"]
        session.started_at = None
        session.status = "paused"
    elif action == "resume" and session.status == "paused":
        session.started_at = now
        session.status = "active"
    elif action == "complete" and session.status in ("active", "paused"):
        elapsed = session.serialize(now)["elapsed_seconds"]
        if elapsed < session.duration_seconds:
            return jsonify({"error": "Focus session is not finished"}), 400
        session.elapsed_seconds = elapsed
        session.started_at = None
        session.status = "completed"
        session.completed_at = now
        session.coins_earned = session.duration_seconds // 60
        user.coins += session.coins_earned
    elif action == "cancel" and session.status in ("active", "paused"):
        session.elapsed_seconds = session.serialize(now)["elapsed_seconds"]
        session.started_at = None
        session.status = "cancelled"
    elif action not in ("pause", "resume", "complete", "cancel"):
        return jsonify({"error": "Unknown action"}), 404
    else:
        return jsonify({"error": "Action is not available for this session"}), 409
    db.session.commit()
    return jsonify(session.serialize(now)), 200


# WEEKLY LEADERBOARD AND DAILY FOCUS TOTALS (MONDAY THROUGH SUNDAY, UTC)
@app.route("/api/leaderboard/weekly/", methods=["GET"])
@require_user
def weekly_leaderboard(user):
    now = now_utc()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    sessions = FocusSession.query.filter(FocusSession.status == "completed", FocusSession.completed_at >= week_start, FocusSession.completed_at < week_start + timedelta(days=7)).all()
    totals = {}
    daily = [0] * 7
    for session in sessions:
        totals[session.user_id] = totals.get(session.user_id, 0) + session.duration_seconds
        if session.user_id == user.id:
            daily[session.completed_at.weekday()] += session.duration_seconds
    users = User.query.filter(User.id.in_(list(totals))).all() if totals else []
    names = {person.id: person.name for person in users}
    ranking = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    return jsonify({"week_start": week_start.date().isoformat(), "timezone": "UTC", "leaderboard": [{"rank": index + 1, "user_id": uid, "name": names[uid], "focus_seconds": seconds} for index, (uid, seconds) in enumerate(ranking)], "daily_focus_seconds": daily}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

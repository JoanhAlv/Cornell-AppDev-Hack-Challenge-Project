import hashlib
import os
import secrets
from datetime import datetime
from functools import wraps

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from db import db, Decoration, FocusSession, Purchase, User

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///touchdown.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()


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


# ACCOUNT ROUTES
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
    return jsonify({"userId": str(user.id), "username": user.username, "token": issue_token(user)}), 201


@app.route("/api/login/", methods=["POST"])
def login():
    body = body_json()
    username, password = body.get("username"), body.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "Invalid username or password"}), 401
    user = User.query.filter_by(username=username.strip().lower()).first()
    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid username or password"}), 401
    return jsonify({"userId": str(user.id), "username": user.username, "token": issue_token(user)}), 200


@app.route("/api/logout/", methods=["POST"])
@require_user
def logout(user):
    user.token_hash = None
    db.session.commit()
    return jsonify({"message": "Logged out"}), 200


# COINS AND STUDY TIME
@app.route("/api/coins", methods=["GET"])
@require_user
def get_coins(user):
    return jsonify({"coins": user.coins}), 200


@app.route("/api/study/submit", methods=["POST"])
@require_user
def submit_study(user):
    seconds = body_json().get("studyTimeSeconds")
    if type(seconds) is not int or not 1 <= seconds <= 86400:
        return jsonify({"error": "studyTimeSeconds must be an integer from 1 to 86400"}), 400
    earned = seconds // 60
    session = FocusSession(user_id=user.id, duration_seconds=seconds, elapsed_seconds=seconds,
                           status="completed", completed_at=datetime.utcnow(), coins_earned=earned)
    user.coins += earned
    db.session.add(session)
    db.session.commit()
    return jsonify({"success": True, "earnedCoins": earned, "totalCoins": user.coins}), 200


# LEADERBOARD: ALL-TIME STUDY SECONDS
@app.route("/api/leaderboard", methods=["GET"])
@require_user
def leaderboard(user):
    totals = db.session.query(User.id, User.username, db.func.sum(FocusSession.duration_seconds)).join(
        FocusSession, FocusSession.user_id == User.id
    ).filter(FocusSession.status == "completed").group_by(User.id, User.username).all()
    ranking = sorted(totals, key=lambda row: (-row[2], row[0]))
    return jsonify([{"userId": str(uid), "username": username, "studyTimeSeconds": int(seconds), "rank": index + 1}
                    for index, (uid, username, seconds) in enumerate(ranking)]), 200


# SPRITE AND DECORATIONS
@app.route("/api/sprite", methods=["GET"])
@require_user
def sprite(user):
    return jsonify({"imageUrl": os.environ.get("SPRITE_IMAGE_URL", "")}), 200


def serialize_decoration(decoration, unlocked):
    return {"id": decoration.id, "name": decoration.name, "cost": decoration.cost,
            "isUnlocked": unlocked, "imageUrl": decoration.image_url}


@app.route("/api/decorations", methods=["GET"])
@require_user
def decorations(user):
    owned = {p.decoration_id for p in user.purchases}
    return jsonify([serialize_decoration(d, d.id in owned) for d in Decoration.query.order_by(Decoration.id).all()]), 200


@app.route("/api/decorations/images", methods=["GET"])
@require_user
def decoration_images(user):
    return jsonify([{"id": d.id, "imageUrl": d.image_url} for d in Decoration.query.order_by(Decoration.id).all()]), 200


@app.route("/api/decorations/<string:decoration_id>/image", methods=["GET"])
@require_user
def decoration_image(user, decoration_id):
    decoration = db.session.get(Decoration, decoration_id)
    if decoration is None:
        return jsonify({"error": "Decoration not found"}), 404
    return jsonify({"id": decoration.id, "imageUrl": decoration.image_url}), 200


@app.route("/api/decorations/buy", methods=["POST"])
@require_user
def buy_decoration(user):
    decoration_id = body_json().get("decorationId")
    if not isinstance(decoration_id, str) or not decoration_id:
        return jsonify({"error": "decorationId is required"}), 400
    decoration = db.session.get(Decoration, decoration_id)
    if decoration is None:
        return jsonify({"error": "Decoration not found"}), 404
    if db.session.get(Purchase, (user.id, decoration.id)):
        return jsonify({"error": "Decoration already unlocked"}), 409
    if user.coins < decoration.cost:
        return jsonify({"error": "Not enough coins"}), 400
    user.coins -= decoration.cost
    db.session.add(Purchase(user_id=user.id, decoration_id=decoration.id))
    db.session.commit()
    return jsonify(serialize_decoration(decoration, True)), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

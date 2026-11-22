# TouchDown backend

A starting Flask API for the focus app shown in the design. It follows the PA4 structure: routes in `app.py`, database models in `db.py`, and a local SQLite database.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The API runs at `http://localhost:8000`. SQLite data is created in `instance/touchdown.db`. Set `DATABASE_URL` to override the database location. The built-in debug server is for local development only.

## API for the Kotlin team

Send JSON with `Content-Type: application/json`. After signup or login, save the returned token securely and send `Authorization: Bearer <token>` with all protected requests. Logging in again replaces the previous token.

| Method | Route | JSON body / behavior |
| --- | --- | --- |
| POST | `/api/users/` | `{"name":"Jo", "email":"jo@example.edu", "password":"password123"}`; returns user and token |
| POST | `/api/login/` | `{"email":"jo@example.edu", "password":"password123"}`; returns user and token |
| POST | `/api/logout/` | Invalidates the current token |
| GET | `/api/me/` | Current profile and coin balance |
| POST | `/api/focus-sessions/` | `{"duration_minutes":30}`; starts a session, 1–180 minutes |
| GET | `/api/focus-sessions/<id>/` | Session status and remaining seconds |
| POST | `/api/focus-sessions/<id>/pause/` | Pauses the timer |
| POST | `/api/focus-sessions/<id>/resume/` | Resumes the timer |
| POST | `/api/focus-sessions/<id>/complete/` | Completes a finished timer and awards coins once |
| POST | `/api/focus-sessions/<id>/cancel/` | Cancels without a reward |
| GET | `/api/leaderboard/weekly/` | All users with completed sessions this UTC week, ranked by focus seconds; also returns the current user's daily seconds starting Monday |

Errors are JSON objects with an `error` field. A user can have one active or paused session at a time. The client should call complete when the timer reaches zero; merely reaching zero does not award coins automatically.

## Decisions to confirm with the team

- The picture shows 30 coins for a 30-minute session, so this prototype awards one coin per completed minute.
- The leaderboard currently includes all users, not just friends. Weeks run Monday–Sunday in UTC, and sessions count on their completion day.
- School email/password signup is a prototype. NetID login and school email verification need the school's identity provider and agreed authentication flow. Passwords are hashed; tokens do not expire and a new login invalidates the previous token. Production use needs a reviewed authentication and deployment design.
- Blocking other apps and requesting device permissions are handled by the mobile app and operating system, not these routes.
- A paused session can be resumed or cancelled. Rewards are granted only when the client requests completion after the server timer reaches zero.

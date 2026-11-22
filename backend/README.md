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

## Database design

The database uses four tables. Primary keys identify each record; foreign keys connect data to its owner:

```text
User 1 ───── many FocusSession
User 1 ───── 0 or 1 UserSettings
User 1 ───── many BlockedApp
```

- **User** stores the account name, normalized email, password hash, token hash, and coin balance. Passwords and tokens are not returned in profiles.
- **FocusSession** belongs to one user and records the intended duration, elapsed time, running/paused/completed/cancelled state, completion time, and earned coins. The server computes remaining time from timestamps. Completed sessions supply the leaderboard and weekly chart.
- **UserSettings** belongs to one user and stores the default timer length and deep-focus preference. Defaults are created on first access.
- **BlockedApp** belongs to one user and stores an app identifier. A user cannot have the same identifier twice. These records are preferences for the mobile client; they do not block an app by themselves.

SQLAlchemy relationships in `db.py` connect the models in both directions. Deleting a user through SQLAlchemy also deletes their related records. `db.create_all()` creates missing tables but is not a migration system: future changes to existing columns will need a database migration.

## API design

Routes represent accounts, the signed-in user's settings, focus sessions, and the weekly leaderboard. The server authenticates requests using a bearer token and checks that a session belongs to the requesting user. The client controls the display and device-specific permissions, while the server tracks session time, calculates rewards, and aggregates completed sessions. Responses are JSON with HTTP status codes; errors contain an `error` message.

Additional routes for the screens:

| Method | Route | JSON body / behavior |
| --- | --- | --- |
| GET | `/api/settings/` | Returns `default_duration_minutes`, `deep_focus`, and `blocked_apps` |
| PUT | `/api/settings/` | Update any of those fields, e.g. `{"deep_focus":true,"blocked_apps":["com.example.app"]}`. The app list replaces the previous list. |
| GET | `/api/focus-sessions/` | Returns the user's sessions, newest first, including active and paused sessions for restoring the timer |

The identifiers in `blocked_apps` must be agreed with the Kotlin developer and are platform-specific. Settings do not prove a device has granted permissions or that blocking is active. Deep focus is saved as a preference; its exact device behavior needs agreement with the team.

NetID single sign-on, school email verification, and a friends-only leaderboard cannot be completed from the drawing alone: they need the identity provider and product rules. The existing email/password login and global leaderboard are prototypes. This is a development backend, not a production-ready authentication or deployment system.

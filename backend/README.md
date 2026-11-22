# TouchDown backend

A Flask and SQLite backend for the Kotlin app. Routes live in `app.py` and models in `db.py`.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The server runs on port 8000. SQLite is created at `instance/touchdown.db`; `DATABASE_URL` overrides it. The development server is not intended for production.

## Accounts

Create an account with `POST /api/users/` or sign in with `POST /api/login/`, both with `{"username":"jo","password":"password123"}`. The password must have at least eight characters. Both return `{"userId":"1","username":"jo","token":"..."}`. Save the token securely on the device, and send `Authorization: Bearer <token>` on every route below. `POST /api/logout/` invalidates it. Signing in again replaces the old token. Usernames are case-insensitive. The Kotlin interface in the screenshot does not show these account calls or an authorization header; the frontend must add them to save each person's stats.

## Kotlin API

The following paths intentionally have no trailing slash, matching the Retrofit interface. Requests and responses are JSON and use the exact camelCase field names shown by the frontend.

| Method | Path | Response or body |
| --- | --- | --- |
| GET | `/api/coins` | `{"coins":30}` |
| GET | `/api/leaderboard` | `[{"userId":"1","username":"jo","studyTimeSeconds":1800,"rank":1}]` |
| POST | `/api/study/submit` | Body `{"studyTimeSeconds":1800}`; response `{"success":true,"earnedCoins":30,"totalCoins":30}` |
| GET | `/api/sprite` | `{"imageUrl":""}` |
| GET | `/api/decorations` | Array of `{"id":"hat","name":"Hat","cost":10,"isUnlocked":false,"imageUrl":""}` |
| GET | `/api/decorations/images` | Array of `{"id":"hat","imageUrl":""}` |
| GET | `/api/decorations/{id}/image` | `{"id":"hat","imageUrl":""}`, or 404 |
| POST | `/api/decorations/buy` | Body `{"decorationId":"hat"}`; returns the purchased Decoration with `isUnlocked: true` |

The screenshot's `buyDecoration()` method has no argument, so it must be updated to accept a JSON request body with `decorationId`. Errors return `{"error":"..."}` with a non-2xx HTTP status. The frontend should handle these errors.

## Database and API design

```text
User 1 ─── many FocusSession
User 1 ─── many Purchase ─── 1 Decoration
```

A **User** stores a username, password hash, token hash, and coin balance. **FocusSession** stores each submitted study duration, its owner, completion time, and earned coins; old completed sessions are retained. **Decoration** stores an item's ID, name, cost, and image URL. **Purchase** joins a user and decoration, with a composite primary key to prevent duplicate ownership. The API calculates the leaderboard by summing completed study time per user and checks purchases against the user's balance and ownership.

The backend awards one coin per full minute submitted. The current leaderboard is **all-time** and includes users with recorded study time, sorted by duration, with user ID breaking ties. These are assumptions for the team to confirm. Study time is reported by the client; the server cannot independently verify that a user studied. Repeated submissions each add time and coins, so the client should submit only once per session. Production use would need a trusted verification and retry/idempotency design.

The decoration catalog starts empty because no item names, prices, or assets were supplied. Add rows to `Decoration` when your team provides them; image URLs can be empty until images are hosted. Set `SPRITE_IMAGE_URL` to a hosted sprite URL (otherwise the response is empty). The API doesn't host or create image files.

Old timer, settings, and app-blocking routes were removed to match the frontend interface. Existing SQLite tables are not deleted, and the original `email` column stores usernames for compatibility. `db.create_all()` does not migrate existing columns; future schema changes need a migration. Existing active or paused sessions are no longer controlled by this API. The account system is a prototype: tokens do not expire, and production deployment requires further security review.

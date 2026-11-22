import os
import tempfile
import unittest
from datetime import timedelta

fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE_URL"] = "sqlite:///" + path
from app import app, db, FocusSession, now_utc


class BackendTests(unittest.TestCase):
    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()
        self.client = app.test_client()
        result = self.client.post("/api/users/", json={"name": "Test", "email": "test@example.edu", "password": "password123"})
        self.headers = {"Authorization": "Bearer " + result.json["token"]}

    def test_settings_and_session_ownership(self):
        result = self.client.put("/api/settings/", headers=self.headers, json={"deep_focus": True, "blocked_apps": ["com.example.app", "com.example.app"]})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["blocked_apps"], ["com.example.app"])
        self.assertEqual(self.client.get("/api/settings/", headers=self.headers).json["deep_focus"], True)
        self.assertEqual(self.client.put("/api/settings/", headers=self.headers, json={"deep_focus": "yes"}).status_code, 400)
        session = self.client.post("/api/focus-sessions/", headers=self.headers, json={"duration_minutes": 30}).json
        self.assertEqual(self.client.get("/api/focus-sessions/", headers=self.headers).json["sessions"][0]["id"], session["id"])
        other = self.client.post("/api/users/", json={"name": "Other", "email": "other@example.edu", "password": "password123"})
        other_headers = {"Authorization": "Bearer " + other.json["token"]}
        self.assertEqual(self.client.get('/api/focus-sessions/%s/' % session["id"], headers=other_headers).status_code, 404)

    def test_timer_rewards_and_leaderboard(self):
        session = self.client.post("/api/focus-sessions/", headers=self.headers, json={"duration_minutes": 30}).json
        route = '/api/focus-sessions/%s/' % session["id"]
        self.assertEqual(self.client.post(route + 'complete/', headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post(route + 'pause/', headers=self.headers).json["status"], "paused")
        self.assertEqual(self.client.post(route + 'resume/', headers=self.headers).json["status"], "active")
        with app.app_context():
            stored = db.session.get(FocusSession, session["id"])
            stored.started_at = now_utc() - timedelta(minutes=30)
            db.session.commit()
        self.assertEqual(self.client.post(route + 'complete/', headers=self.headers).json["coins_earned"], 30)
        self.assertEqual(self.client.post(route + 'complete/', headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get('/api/me/', headers=self.headers).json["coins"], 30)
        self.assertEqual(self.client.get('/api/leaderboard/weekly/', headers=self.headers).json["leaderboard"][0]["focus_seconds"], 1800)


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        os.unlink(path)

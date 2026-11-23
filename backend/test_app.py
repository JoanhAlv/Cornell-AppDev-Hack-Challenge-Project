import os
import tempfile
import unittest

fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE_URL"] = "sqlite:///" + path
from app import app, db
from db import Decoration


class BackendTests(unittest.TestCase):
    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()
            db.session.add(Decoration(id="hat", name="Hat", cost=10, image_url="https://example.com/hat.png"))
            db.session.commit()
        self.client = app.test_client()
        result = self.client.post("/api/users/", json={"username": "test", "password": "password123"})
        self.headers = {"Authorization": "Bearer " + result.json["token"]}

    def test_accounts_and_study(self):
        self.assertEqual(self.client.get('/api/coins').status_code, 401)
        self.assertEqual(self.client.post('/api/study/submit', headers=self.headers, json={"studyTimeSeconds": -1}).status_code, 400)
        response = self.client.post('/api/study/submit', headers=self.headers, json={"studyTimeSeconds": 1800})
        self.assertEqual(response.json, {"success": True, "earnedCoins": 30, "totalCoins": 30})
        self.assertEqual(self.client.get('/api/coins', headers=self.headers).json, {"coins": 30})
        entry = self.client.get('/api/leaderboard', headers=self.headers).json[0]
        self.assertEqual((entry['username'], entry['studyTimeSeconds'], entry['rank']), ('test', 1800, 1))
        login = self.client.post('/api/login/', json={"username": "test", "password": "password123"})
        self.assertEqual(login.status_code, 200)
        headers = {"Authorization": "Bearer " + login.json['token']}
        self.assertEqual(self.client.get('/api/coins', headers=headers).json['coins'], 30)

    def test_user_stats_and_username(self):
        self.assertEqual(self.client.get('/api/user/stats').status_code, 401)
        stats = self.client.get('/api/user/stats', headers=self.headers).json
        self.assertEqual((stats['studyTimeSeconds'], stats['rank']), (0, 0))
        self.client.post('/api/study/submit', headers=self.headers, json={"studyTimeSeconds": 1800})
        result = self.client.post('/api/user/username', headers=self.headers, json={"username": "New Name"})
        self.assertEqual(result.json, {"userId": stats['userId'], "username": "new name", "studyTimeSeconds": 1800, "rank": 1})
        self.assertEqual(self.client.post('/api/user/username', headers=self.headers, json={"username": " "}).status_code, 400)
        self.client.post('/api/users/', json={"username": "other", "password": "password123"})
        self.assertEqual(self.client.post('/api/user/username', headers=self.headers, json={"username": "other"}).status_code, 409)
        self.assertEqual(self.client.post('/api/login/', json={"username": "new name", "password": "password123"}).status_code, 200)

    def test_decorations(self):
        self.assertEqual(self.client.get('/api/sprite', headers=self.headers).json, {"imageUrl": ""})
        self.assertEqual(self.client.get('/api/decorations/images', headers=self.headers).json[0]['id'], 'hat')
        self.assertEqual(self.client.get('/api/decorations/hat/image', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/decorations/missing/image', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post('/api/decorations/buy', headers=self.headers, json={}).status_code, 400)
        self.assertEqual(self.client.post('/api/decorations/buy', headers=self.headers, json={"decorationId": "hat"}).status_code, 400)
        self.client.post('/api/study/submit', headers=self.headers, json={"studyTimeSeconds": 1800})
        result = self.client.post('/api/decorations/buy', headers=self.headers, json={"decorationId": "hat"})
        self.assertTrue(result.json['isUnlocked'])
        self.assertEqual(self.client.get('/api/coins', headers=self.headers).json['coins'], 20)
        self.assertEqual(self.client.post('/api/decorations/buy', headers=self.headers, json={"decorationId": "hat"}).status_code, 409)
        self.assertTrue(self.client.get('/api/decorations', headers=self.headers).json[0]['isUnlocked'])


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        os.unlink(path)

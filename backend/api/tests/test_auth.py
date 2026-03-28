from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient


class RegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_success(self):
        resp = self.client.post("/api/auth/register/", {
            "username": "newuser",
            "password": "securepass1",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["username"], "newuser")
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_register_duplicate_username(self):
        User.objects.create_user(username="taken", password="pw12345678")
        resp = self.client.post("/api/auth/register/", {
            "username": "taken",
            "password": "securepass1",
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_short_password(self):
        resp = self.client.post("/api/auth/register/", {
            "username": "newuser",
            "password": "short",
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_missing_fields(self):
        resp = self.client.post("/api/auth/register/", {})
        self.assertEqual(resp.status_code, 400)

    def test_register_logs_user_in(self):
        """After registration the session should be authenticated."""
        self.client.post("/api/auth/register/", {
            "username": "newuser",
            "password": "securepass1",
        })
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], "newuser")


class LoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pass12345")

    def test_login_success(self):
        resp = self.client.post("/api/auth/login/", {
            "username": "alice",
            "password": "pass12345",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], "alice")

    def test_login_wrong_password(self):
        resp = self.client.post("/api/auth/login/", {
            "username": "alice",
            "password": "wrong",
        })
        self.assertEqual(resp.status_code, 401)

    def test_login_nonexistent_user(self):
        resp = self.client.post("/api/auth/login/", {
            "username": "nobody",
            "password": "pass12345",
        })
        self.assertEqual(resp.status_code, 401)


class LogoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pass12345")

    def test_logout_success(self):
        self.client.force_login(self.user)
        resp = self.client.post("/api/auth/logout/")
        self.assertEqual(resp.status_code, 200)
        # Session should be cleared
        me_resp = self.client.get("/api/auth/me/")
        self.assertEqual(me_resp.status_code, 403)

    def test_logout_unauthenticated(self):
        resp = self.client.post("/api/auth/logout/")
        self.assertEqual(resp.status_code, 403)


class MeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pass12345")

    def test_me_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], "alice")
        self.assertIn("is_staff", data)
        self.assertIn("oidc_identities", data)

    def test_me_unauthenticated(self):
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, 403)

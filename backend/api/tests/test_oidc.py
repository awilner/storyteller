from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import OIDCIdentity


MOCK_CLAIMS = {
    "sub": "oidc-subject-123",
    "email": "alice@example.com",
    "iss": "https://accounts.example.com",
}


class OIDCLoginViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("api.views.get_authorization_url", return_value="https://idp.example.com/auth?state=xyz")
    def test_oidc_login_returns_url(self, _mock):
        resp = self.client.get("/api/auth/oidc/login/?redirect_uri=http://localhost/cb")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("authorization_url", resp.json())

    def test_oidc_login_missing_redirect_uri(self):
        resp = self.client.get("/api/auth/oidc/login/")
        self.assertEqual(resp.status_code, 400)


class OIDCCallbackViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("api.views.exchange_code_for_claims", return_value=MOCK_CLAIMS)
    def test_callback_creates_user_and_identity(self, _mock):
        # Set up session state
        session = self.client.session
        session["oidc_state"] = "test-state"
        session.save()

        resp = self.client.post("/api/auth/oidc/callback/", {
            "code": "auth-code",
            "redirect_uri": "http://localhost/cb",
            "state": "test-state",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("username", data)

        # User and identity should exist
        self.assertTrue(OIDCIdentity.objects.filter(sub="oidc-subject-123").exists())

    @patch("api.views.exchange_code_for_claims", return_value=MOCK_CLAIMS)
    def test_callback_logs_in_existing_linked_user(self, _mock):
        user = User.objects.create_user(username="alice", password="pw")
        OIDCIdentity.objects.create(
            user=user,
            provider="https://accounts.example.com",
            sub="oidc-subject-123",
        )

        session = self.client.session
        session["oidc_state"] = "test-state"
        session.save()

        resp = self.client.post("/api/auth/oidc/callback/", {
            "code": "auth-code",
            "redirect_uri": "http://localhost/cb",
            "state": "test-state",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], "alice")

    def test_callback_missing_code(self):
        resp = self.client.post("/api/auth/oidc/callback/", {
            "redirect_uri": "http://localhost/cb",
            "state": "s",
        })
        self.assertEqual(resp.status_code, 400)

    def test_callback_invalid_state(self):
        session = self.client.session
        session["oidc_state"] = "correct"
        session.save()

        resp = self.client.post("/api/auth/oidc/callback/", {
            "code": "auth-code",
            "redirect_uri": "http://localhost/cb",
            "state": "wrong",
        })
        self.assertEqual(resp.status_code, 400)


class OIDCLinkViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.client.force_login(self.user)

    @patch("api.views.exchange_code_for_claims", return_value=MOCK_CLAIMS)
    def test_link_identity(self, _mock):
        session = self.client.session
        session["oidc_state"] = "test-state"
        session.save()

        resp = self.client.post("/api/auth/oidc/link/", {
            "code": "auth-code",
            "redirect_uri": "http://localhost/cb",
            "state": "test-state",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            OIDCIdentity.objects.filter(user=self.user, sub="oidc-subject-123").exists()
        )

    @patch("api.views.exchange_code_for_claims", return_value=MOCK_CLAIMS)
    def test_link_already_linked_identity(self, _mock):
        other = User.objects.create_user(username="bob", password="pw")
        OIDCIdentity.objects.create(
            user=other,
            provider="https://accounts.example.com",
            sub="oidc-subject-123",
        )

        session = self.client.session
        session["oidc_state"] = "test-state"
        session.save()

        resp = self.client.post("/api/auth/oidc/link/", {
            "code": "auth-code",
            "redirect_uri": "http://localhost/cb",
            "state": "test-state",
        })
        self.assertEqual(resp.status_code, 409)

    def test_link_unauthenticated(self):
        self.client.logout()
        resp = self.client.post("/api/auth/oidc/link/", {
            "code": "auth-code",
            "redirect_uri": "http://localhost/cb",
            "state": "s",
        })
        self.assertEqual(resp.status_code, 403)


class OIDCUnlinkViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.identity = OIDCIdentity.objects.create(
            user=self.user, provider="google", sub="sub1",
        )
        self.client.force_login(self.user)

    def test_unlink_own_identity(self):
        resp = self.client.delete(f"/api/auth/oidc/unlink/{self.identity.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(OIDCIdentity.objects.filter(pk=self.identity.pk).exists())

    def test_unlink_other_users_identity(self):
        other = User.objects.create_user(username="bob", password="pw")
        other_id = OIDCIdentity.objects.create(
            user=other, provider="google", sub="sub2",
        )
        resp = self.client.delete(f"/api/auth/oidc/unlink/{other_id.pk}/")
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(OIDCIdentity.objects.filter(pk=other_id.pk).exists())

    def test_unlink_nonexistent(self):
        resp = self.client.delete("/api/auth/oidc/unlink/99999/")
        self.assertEqual(resp.status_code, 404)

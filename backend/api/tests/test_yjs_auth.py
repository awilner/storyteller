# Feature: project-sharing — Integration tests for HocusPocus auth callback
"""
Integration tests for the /api/internal/yjs-auth/ endpoint.

**Validates: Requirements 10.4, 11.4**
"""

import json
import os

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from api.models import Folder, ObjectPermissionOverride, Project, ProjectFile, ProjectShare


HOCUSPOCUS_SECRET = "test-hocuspocus-secret"


class YjsAuthEndpointTests(TestCase):
    """
    Integration tests for the internal Yjs auth endpoint used by HocusPocus.

    The endpoint validates a session cookie, resolves the user, computes
    effective permission on the file, and returns user info.

    **Validates: Requirements 10.4, 11.4**
    """

    def setUp(self):
        os.environ["HOCUSPOCUS_SECRET"] = HOCUSPOCUS_SECRET

        self.owner = User.objects.create_user(
            username="yjs_owner", password="testpass"
        )
        self.coauthor = User.objects.create_user(
            username="yjs_coauthor", password="testpass"
        )
        self.reader = User.objects.create_user(
            username="yjs_reader", password="testpass"
        )
        self.stranger = User.objects.create_user(
            username="yjs_stranger", password="testpass"
        )

        self.project = Project.objects.create(
            owner=self.owner, title="Yjs Test Project"
        )
        self.folder = Folder.objects.create(
            project=self.project, title="Chapter", order=0
        )
        self.file = ProjectFile.objects.create(
            project=self.project,
            folder=self.folder,
            file_type=ProjectFile.FileType.TEXT,
            title="Scene",
            order=0,
        )

        ProjectShare.objects.create(
            project=self.project, user=self.coauthor, role="co-author"
        )
        ProjectShare.objects.create(
            project=self.project, user=self.reader, role="read-only"
        )

    def tearDown(self):
        os.environ.pop("HOCUSPOCUS_SECRET", None)

    def _get_session_cookie(self, username):
        """Log in via a separate client and return the session cookie string."""
        from django.test import Client
        c = Client()
        c.login(username=username, password="testpass")
        session_key = c.session.session_key
        return f"sessionid={session_key}"

    def _post_yjs_auth(self, file_id, cookie="", secret=HOCUSPOCUS_SECRET):
        """POST to the yjs-auth endpoint."""
        headers = {}
        if secret:
            headers["HTTP_X_HOCUSPOCUS_SECRET"] = secret
        return self.client.post(
            "/api/internal/yjs-auth/",
            data=json.dumps({"file_id": file_id, "cookie": cookie}),
            content_type="application/json",
            **headers,
        )

    # ── Valid session + co-author → 200 with permission data ─

    def test_coauthor_gets_200_with_coauthor_permission(self):
        """A co-author with a valid session gets 200 and co-author permission."""
        cookie = self._get_session_cookie("yjs_coauthor")
        resp = self._post_yjs_auth(self.file.pk, cookie=cookie)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["user_id"], self.coauthor.pk)
        self.assertEqual(data["username"], "yjs_coauthor")
        self.assertEqual(data["permission"], "co-author")

    # ── Valid session + read-only → 200 with read-only flag ──

    def test_reader_gets_200_with_readonly_permission(self):
        """A read-only user with a valid session gets 200 and read-only permission."""
        cookie = self._get_session_cookie("yjs_reader")
        resp = self._post_yjs_auth(self.file.pk, cookie=cookie)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["user_id"], self.reader.pk)
        self.assertEqual(data["permission"], "read-only")

    # ── Owner gets 200 with owner permission ─────────────────

    def test_owner_gets_200_with_owner_permission(self):
        """The project owner gets 200 and owner permission."""
        cookie = self._get_session_cookie("yjs_owner")
        resp = self._post_yjs_auth(self.file.pk, cookie=cookie)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["permission"], "owner")

    # ── Invalid session → 401 ────────────────────────────────

    def test_invalid_session_returns_401(self):
        """An invalid session cookie returns 401."""
        resp = self._post_yjs_auth(
            self.file.pk, cookie="sessionid=invalid-session-id"
        )
        self.assertEqual(resp.status_code, 401)

    def test_missing_session_returns_401(self):
        """A request with no session cookie returns 401."""
        resp = self._post_yjs_auth(self.file.pk, cookie="")
        self.assertEqual(resp.status_code, 401)

    # ── No access to file → 403 ─────────────────────────────

    def test_stranger_gets_403(self):
        """A user with no project access gets 403."""
        cookie = self._get_session_cookie("yjs_stranger")
        resp = self._post_yjs_auth(self.file.pk, cookie=cookie)
        self.assertEqual(resp.status_code, 403)

    # ── Override blocks access → 403 ─────────────────────────

    def test_none_override_returns_403(self):
        """A collaborator with a 'none' override on the file's folder gets 403."""
        ObjectPermissionOverride.objects.create(
            project=self.project,
            user=self.coauthor,
            target_folder=self.folder,
            permission="none",
        )
        cookie = self._get_session_cookie("yjs_coauthor")
        resp = self._post_yjs_auth(self.file.pk, cookie=cookie)
        self.assertEqual(resp.status_code, 403)

    # ── Invalid/missing secret → 403 ─────────────────────────

    def test_wrong_secret_returns_403(self):
        """A request with the wrong shared secret returns 403."""
        cookie = self._get_session_cookie("yjs_owner")
        resp = self._post_yjs_auth(
            self.file.pk, cookie=cookie, secret="wrong-secret"
        )
        self.assertEqual(resp.status_code, 403)

    def test_missing_secret_returns_403(self):
        """A request with no shared secret returns 403."""
        cookie = self._get_session_cookie("yjs_owner")
        resp = self._post_yjs_auth(
            self.file.pk, cookie=cookie, secret=""
        )
        self.assertEqual(resp.status_code, 403)

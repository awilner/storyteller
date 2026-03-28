from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from api.models import Project, ProjectFile
from api.permissions import IsProjectOwner


class _FakeView:
    """Minimal stand-in for a DRF view with kwargs."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs


class IsProjectOwnerTests(TestCase):
    """Unit tests for the IsProjectOwner permission class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsProjectOwner()
        self.owner = User.objects.create_user(username="owner", password="pw")
        self.other = User.objects.create_user(username="other", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.file = ProjectFile.objects.create(
            project=self.project,
            file_type=ProjectFile.FileType.TEXT,
            title="Opening",
        )

    # ── Unauthenticated ──────────────────────────────────────
    def test_anonymous_user_denied(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        view = _FakeView(project_pk=self.project.pk)
        self.assertFalse(self.permission.has_permission(request, view))

    # ── project_pk path ──────────────────────────────────────
    def test_owner_allowed_via_project_pk(self):
        request = self.factory.get("/")
        request.user = self.owner
        view = _FakeView(project_pk=self.project.pk)
        self.assertTrue(self.permission.has_permission(request, view))

    def test_non_owner_denied_via_project_pk(self):
        request = self.factory.get("/")
        request.user = self.other
        view = _FakeView(project_pk=self.project.pk)
        self.assertFalse(self.permission.has_permission(request, view))

    def test_missing_project_returns_false(self):
        request = self.factory.get("/")
        request.user = self.owner
        view = _FakeView(project_pk=99999)
        self.assertFalse(self.permission.has_permission(request, view))

    # ── file_pk path ─────────────────────────────────────────
    def test_owner_allowed_via_file_pk(self):
        request = self.factory.get("/")
        request.user = self.owner
        view = _FakeView(file_pk=self.file.pk)
        self.assertTrue(self.permission.has_permission(request, view))

    def test_non_owner_denied_via_file_pk(self):
        request = self.factory.get("/")
        request.user = self.other
        view = _FakeView(file_pk=self.file.pk)
        self.assertFalse(self.permission.has_permission(request, view))

    def test_missing_file_returns_false(self):
        request = self.factory.get("/")
        request.user = self.owner
        view = _FakeView(file_pk=99999)
        self.assertFalse(self.permission.has_permission(request, view))

    # ── No kwargs at all ─────────────────────────────────────
    def test_no_kwargs_returns_false(self):
        request = self.factory.get("/")
        request.user = self.owner
        view = _FakeView()
        self.assertFalse(self.permission.has_permission(request, view))

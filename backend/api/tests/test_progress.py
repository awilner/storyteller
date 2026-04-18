# Unit tests for per-user progress tracking
"""
Unit and integration tests for per-user progress tracking.

Covers target clearing, manuscript target sharing, role-based visibility,
ranking toggles, session state storage, API backward compatibility,
and migration idempotence.

Requirements: 1.6, 2.1, 2.2, 2.3, 2.4, 6.1, 6.2, 6.3, 6.4, 7.1, 8.1, 8.6, 10.1, 10.4
"""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import (
    Project,
    ProjectShare,
    UserProgressSettings,
)


# ── Helpers ───────────────────────────────────────────────────

def _make_user(prefix="user"):
    """Create a unique user."""
    username = f"{prefix}_{User.objects.count()}_{id(object())}"
    return User.objects.create_user(username=username, password="testpass")


def _auth_client(user):
    """Return an APIClient authenticated as the given user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _progress_url(project):
    return f"/api/projects/{project.pk}/progress/"


# ── Test: Target clearing ─────────────────────────────────────


class TargetClearingTest(TestCase):
    """
    Test that setting a target then sending null clears it from
    UserProgressSettings.

    Validates: Requirement 1.6
    """

    def test_clear_daily_target_with_null(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")
        client = _auth_client(owner)

        # Set a daily target
        resp = client.patch(
            _progress_url(project),
            data={"daily_target": 500},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["daily_target"], 500)

        # Clear it with null
        resp = client.patch(
            _progress_url(project),
            data={"daily_target": None},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["daily_target"])

        # Verify in the database
        ups = UserProgressSettings.objects.get(project=project, user=owner)
        self.assertIsNone(ups.daily_target)

    def test_clear_session_target_with_null(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")
        client = _auth_client(owner)

        # Set a session target
        resp = client.patch(
            _progress_url(project),
            data={"session_target": 1000},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        # Clear it with null
        resp = client.patch(
            _progress_url(project),
            data={"session_target": None},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["session_target"])

        ups = UserProgressSettings.objects.get(project=project, user=owner)
        self.assertIsNone(ups.session_target)


# ── Test: Manuscript target shared ────────────────────────────


class ManuscriptTargetSharedTest(TestCase):
    """
    Test that manuscript_target is project-level: owner updates it,
    co-author sees the same value.

    Validates: Requirements 2.1, 2.2
    """

    def test_owner_sets_manuscript_target_coauthor_sees_it(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")
        coauthor = _make_user("coauthor")
        ProjectShare.objects.create(project=project, user=coauthor, role="co-author")

        owner_client = _auth_client(owner)
        coauthor_client = _auth_client(coauthor)

        # Owner sets manuscript_target
        resp = owner_client.patch(
            _progress_url(project),
            data={"manuscript_target": 80000},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        # Co-author sees the same value
        resp = coauthor_client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["manuscript_target"], 80000)


# ── Test: Co-author can update manuscript_target ──────────────


class CoAuthorCanUpdateManuscriptTargetTest(TestCase):
    """
    Test that a co-author can update manuscript_target via PATCH.

    Validates: Requirement 2.3
    """

    def test_coauthor_patches_manuscript_target(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")
        coauthor = _make_user("coauthor")
        ProjectShare.objects.create(project=project, user=coauthor, role="co-author")

        coauthor_client = _auth_client(coauthor)

        resp = coauthor_client.patch(
            _progress_url(project),
            data={"manuscript_target": 60000},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["manuscript_target"], 60000)

        # Verify owner sees the updated value
        owner_client = _auth_client(owner)
        resp = owner_client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["manuscript_target"], 60000)


# ── Test: Read-only user sees only manuscript data ────────────


class ReadOnlyUserSeesOnlyManuscriptDataTest(TestCase):
    """
    Test that a read-only user sees only manuscript data — no daily/session
    targets, charts, or controls.

    Validates: Requirements 6.1, 6.2, 6.3
    """

    def test_readonly_response_limited_fields(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")
        readonly_user = _make_user("readonly")
        ProjectShare.objects.create(project=project, user=readonly_user, role="read-only")

        client = _auth_client(readonly_user)
        resp = client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)

        data = resp.data
        # Should have manuscript-level fields
        self.assertIn("current_word_count", data)
        self.assertIn("manuscript_target", data)
        self.assertIn("snapshots", data)
        self.assertIn("owner_timezone", data)
        self.assertIn("user_timezone", data)

        # Should NOT have per-user targets, charts, or session data
        self.assertNotIn("daily_target", data)
        self.assertNotIn("session_target", data)
        self.assertNotIn("daily_word_count", data)
        self.assertNotIn("session_word_count", data)
        self.assertNotIn("daily_counts", data)
        self.assertNotIn("sessions", data)
        self.assertNotIn("day_cutover_hour", data)


# ── Test: Default ranking toggles ─────────────────────────────


class DefaultRankingVisibilityTest(TestCase):
    """
    Test that a new project has ranking_visibility defaulting to "owner".

    Validates: Requirement 8.6
    """

    def test_new_project_ranking_visibility_defaults_to_owner(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")

        client = _auth_client(owner)
        resp = client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)

        # Owner sees the visibility setting, defaults to "owner"
        self.assertEqual(resp.data["ranking_visibility"], "owner")

        # Verify it's not stored in project.settings (using default)
        project.refresh_from_db()
        self.assertNotIn("ranking_visibility", project.settings or {})


# ── Test: Owner always sees contribution_ranking ──────────────


class OwnerAlwaysSeesRankingTest(TestCase):
    """
    Test that the owner always sees contribution_ranking in the GET response.

    Validates: Requirement 7.1
    """

    def test_owner_sees_contribution_ranking(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")

        client = _auth_client(owner)
        resp = client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("contribution_ranking", resp.data)


# ── Test: Ranking toggle fields owner-only ────────────────────


class RankingVisibilityFieldOwnerOnlyTest(TestCase):
    """
    Test that ranking_visibility is present only for the owner,
    absent for co-author and read-only.

    Validates: Requirement 10.4
    """

    def test_visibility_field_present_for_owner(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")

        client = _auth_client(owner)
        resp = client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ranking_visibility", resp.data)

    def test_visibility_field_absent_for_coauthor(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")
        coauthor = _make_user("coauthor")
        ProjectShare.objects.create(project=project, user=coauthor, role="co-author")

        client = _auth_client(coauthor)
        resp = client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("ranking_visibility", resp.data)

    def test_visibility_field_absent_for_readonly(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")
        readonly_user = _make_user("readonly")
        ProjectShare.objects.create(project=project, user=readonly_user, role="read-only")

        client = _auth_client(readonly_user)
        resp = client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("ranking_visibility", resp.data)


# ── Test: API backward compatibility ──────────────────────────


class APIBackwardCompatibilityTest(TestCase):
    """
    Test that all expected top-level field names are present in the GET
    response for owner and co-author.

    Validates: Requirement 10.1
    """

    EXPECTED_OWNER_FIELDS = {
        "current_word_count",
        "manuscript_target",
        "daily_target",
        "session_target",
        "daily_word_count",
        "session_word_count",
        "snapshots",
        "daily_counts",
        "sessions",
        "owner_timezone",
        "user_timezone",
        "day_cutover_hour",
        "contribution_ranking",
        "ranking_visibility",
    }

    EXPECTED_COAUTHOR_FIELDS = {
        "current_word_count",
        "manuscript_target",
        "daily_target",
        "session_target",
        "daily_word_count",
        "session_word_count",
        "snapshots",
        "daily_counts",
        "sessions",
        "owner_timezone",
        "user_timezone",
        "day_cutover_hour",
    }

    def test_owner_response_has_all_expected_fields(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")

        client = _auth_client(owner)
        resp = client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)

        actual_fields = set(resp.data.keys())
        for field in self.EXPECTED_OWNER_FIELDS:
            self.assertIn(field, actual_fields, f"Missing field: {field}")

    def test_coauthor_response_has_all_expected_fields(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")
        coauthor = _make_user("coauthor")
        ProjectShare.objects.create(project=project, user=coauthor, role="co-author")

        client = _auth_client(coauthor)
        resp = client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)

        actual_fields = set(resp.data.keys())
        for field in self.EXPECTED_COAUTHOR_FIELDS:
            self.assertIn(field, actual_fields, f"Missing field: {field}")


# ── Test: Session state in UserProgressSettings ───────────────


class SessionStateInUserProgressSettingsTest(TestCase):
    """
    Test that after a session reset, session state is stored in
    UserProgressSettings, not in project.settings.

    Validates: Requirement 2.4 (session state not in project.settings)
    """

    def test_session_reset_stores_state_in_user_progress_settings(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")

        client = _auth_client(owner)

        # Trigger a GET to initialize session state
        resp = client.get(_progress_url(project))
        self.assertEqual(resp.status_code, 200)

        # Reset the session
        resp = client.post(
            _progress_url(project),
            data={"action": "reset_session"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        # Verify session state is in UserProgressSettings
        ups = UserProgressSettings.objects.get(project=project, user=owner)
        self.assertIsNotNone(ups.session_start_word_count)
        self.assertIsNotNone(ups.session_started_at)

        # Verify session state is NOT in project.settings
        project.refresh_from_db()
        proj_settings = project.settings or {}
        self.assertNotIn("session_start_word_count", proj_settings)
        self.assertNotIn("session_started_at", proj_settings)


# ── Test: Co-author cannot set ranking visibility toggles ─────


class CoAuthorCannotSetRankingVisibilityTest(TestCase):
    """
    Test that a co-author cannot set ranking_visibility (403).

    Validates: Requirements 8.1, 6.4
    """

    def test_coauthor_cannot_set_ranking_visibility(self):
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test")
        coauthor = _make_user("coauthor")
        ProjectShare.objects.create(project=project, user=coauthor, role="co-author")

        client = _auth_client(coauthor)
        resp = client.patch(
            _progress_url(project),
            data={"ranking_visibility": "all"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)


# ── Test: Migration idempotence ───────────────────────────────


class MigrationIdempotenceTest(TestCase):
    """
    Test that running the migration logic twice produces the same result.

    Validates: Requirement 9.4
    """

    def test_migration_logic_idempotent(self):
        """Run the forward migration logic twice and verify same result."""
        import importlib

        migration_mod = importlib.import_module(
            "api.migrations.0010_user_progress_settings"
        )
        forwards = migration_mod.forwards

        # Create a project with legacy settings
        owner = _make_user("owner")
        project = Project.objects.create(
            owner=owner,
            title="Legacy Project",
            settings={
                "daily_target": 1000,
                "session_target": 500,
                "session_start_word_count": 200,
                "manuscript_target": 80000,
            },
        )

        from django.apps import apps

        # First run
        forwards(apps, None)

        project.refresh_from_db()
        ups = UserProgressSettings.objects.get(project=project, user=owner)
        self.assertEqual(ups.daily_target, 1000)
        self.assertEqual(ups.session_target, 500)
        self.assertEqual(ups.session_start_word_count, 200)

        # Migrated keys should be removed from project.settings
        self.assertNotIn("daily_target", project.settings)
        self.assertNotIn("session_target", project.settings)
        self.assertNotIn("session_start_word_count", project.settings)
        # manuscript_target should remain
        self.assertEqual(project.settings.get("manuscript_target"), 80000)

        # Second run — should produce the same result (idempotent)
        forwards(apps, None)

        project.refresh_from_db()
        ups.refresh_from_db()
        self.assertEqual(ups.daily_target, 1000)
        self.assertEqual(ups.session_target, 500)
        self.assertEqual(ups.session_start_word_count, 200)
        self.assertNotIn("daily_target", project.settings)
        self.assertNotIn("session_target", project.settings)
        self.assertNotIn("session_start_word_count", project.settings)
        self.assertEqual(project.settings.get("manuscript_target"), 80000)

        # Only one UserProgressSettings record should exist
        self.assertEqual(
            UserProgressSettings.objects.filter(project=project, user=owner).count(),
            1,
        )

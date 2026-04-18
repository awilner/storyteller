# Feature: project-sharing — Unit tests for sharing edge cases
"""
Unit tests for sharing API edge cases.

**Validates: Requirements 1.2, 1.3, 7.3**
"""

from django.contrib.auth.models import User
from django.test import TestCase

from api.models import Folder, ObjectPermissionOverride, Project, ProjectFile, ProjectShare


class ShareEdgeCaseTests(TestCase):
    """Unit tests for sharing edge cases using Django test client."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", password="testpass"
        )
        self.collaborator = User.objects.create_user(
            username="collaborator", password="testpass"
        )
        self.project = Project.objects.create(
            owner=self.owner, title="Test Project"
        )
        self.client.login(username="owner", password="testpass")

    # ── Share-with-self error (400) ──────────────────────────
    # Validates: Requirement 1.3

    def test_share_with_self_returns_400(self):
        """Owner cannot share the project with themselves."""
        response = self.client.post(
            f"/api/projects/{self.project.pk}/shares/",
            data={"username": "owner", "role": "co-author"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("owner", response.json()["detail"].lower())

    # ── Duplicate share error (409) ──────────────────────────
    # Validates: Requirement 1.2

    def test_duplicate_share_returns_409(self):
        """Sharing with a user who already has access returns 409."""
        # First share succeeds
        response = self.client.post(
            f"/api/projects/{self.project.pk}/shares/",
            data={"username": "collaborator", "role": "read-only"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

        # Second share with same user returns 409
        response = self.client.post(
            f"/api/projects/{self.project.pk}/shares/",
            data={"username": "collaborator", "role": "co-author"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("already", response.json()["detail"].lower())

    # ── Share with non-existent user error (404) ─────────────
    # Validates: Requirement 1.2

    def test_share_with_nonexistent_user_returns_404(self):
        """Sharing with a user that doesn't exist returns 404."""
        response = self.client.post(
            f"/api/projects/{self.project.pk}/shares/",
            data={"username": "ghost_user_does_not_exist", "role": "read-only"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    # ── Revoke non-existent share returns 404 ────────────────
    # Validates: Requirement 1.2

    def test_revoke_nonexistent_share_returns_404(self):
        """Deleting a share that doesn't exist returns 404."""
        response = self.client.delete(
            f"/api/projects/{self.project.pk}/shares/99999/",
        )
        self.assertEqual(response.status_code, 404)

    # ── Override upgrade attempt returns 400 ─────────────────
    # Validates: Requirement 7.3

    def test_override_upgrade_attempt_returns_400(self):
        """
        Creating an override that would upgrade a read-only user's
        permission is rejected with 400.
        """
        # Share with collaborator as read-only
        ProjectShare.objects.create(
            project=self.project,
            user=self.collaborator,
            role="read-only",
        )

        # Create a folder to target
        folder = Folder.objects.create(
            project=self.project,
            title="Secret Folder",
            order=0,
        )

        # Attempt to create a "read-only" override on a read-only user
        # This is NOT a downgrade (same level), so it should be rejected
        response = self.client.post(
            f"/api/projects/{self.project.pk}/overrides/",
            data={
                "user": self.collaborator.pk,
                "target_folder": folder.pk,
                "target_file": None,
                "permission": "read-only",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot exceed", response.json()["detail"].lower())


# ── Integration tests: end-to-end permission flow ────────────
# Validates: Requirements 1.1, 1.5, 5.2, 7.1, 8.1


class EndToEndPermissionFlowTests(TestCase):
    """
    Integration test: create project → share → verify access → set override
    → verify restricted access → revoke → verify no access.

    Uses the Django test client to exercise the full HTTP stack.

    **Validates: Requirements 1.1, 1.5, 5.2, 7.1, 8.1**
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username="e2e_owner", password="testpass"
        )
        self.collaborator = User.objects.create_user(
            username="e2e_collab", password="testpass"
        )

    # ── helpers ───────────────────────────────────────────────

    def _login_as(self, username):
        self.client.login(username=username, password="testpass")

    def _create_project(self):
        """Create a project via the API (seeds default folders/files)."""
        self._login_as("e2e_owner")
        resp = self.client.post(
            "/api/projects/",
            data={"title": "E2E Project"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        project_pk = resp.json()["id"]

        # The project creation seeds a Manuscript → Chapter 1 → Scene 1 tree.
        # Retrieve the seeded folder and file.
        project = Project.objects.get(pk=project_pk)
        folder = Folder.objects.filter(
            project=project, title="Chapter 1"
        ).first()
        file_obj = ProjectFile.objects.filter(
            project=project, title="Scene 1"
        ).first()

        self.assertIsNotNone(folder)
        self.assertIsNotNone(file_obj)

        return project_pk, folder.pk, file_obj.pk

    # ── full flow ─────────────────────────────────────────────

    def test_full_permission_lifecycle(self):
        """
        End-to-end: share → access → override → restricted → revoke → no access.
        """
        project_pk, folder_pk, file_pk = self._create_project()

        # 1. Share with collaborator as co-author
        resp = self.client.post(
            f"/api/projects/{project_pk}/shares/",
            data={"username": "e2e_collab", "role": "co-author"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        share_pk = resp.json()["id"]

        # 2. Collaborator can access the project tree
        self._login_as("e2e_collab")
        resp = self.client.get(f"/api/projects/{project_pk}/tree/")
        self.assertEqual(resp.status_code, 200)

        # 3. Collaborator can read a file
        resp = self.client.get(f"/api/files/{file_pk}/")
        self.assertEqual(resp.status_code, 200)

        # 4. Owner sets a "none" override on the folder → collaborator loses access
        self._login_as("e2e_owner")
        resp = self.client.post(
            f"/api/projects/{project_pk}/overrides/",
            data={
                "user": self.collaborator.pk,
                "target_folder": folder_pk,
                "target_file": None,
                "permission": "none",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)

        # 5. Collaborator can no longer access the folder
        self._login_as("e2e_collab")
        resp = self.client.get(
            f"/api/projects/{project_pk}/folders/{folder_pk}/"
        )
        self.assertEqual(resp.status_code, 403)

        # 6. Collaborator can no longer access the file inside the folder
        resp = self.client.get(f"/api/files/{file_pk}/")
        self.assertEqual(resp.status_code, 403)

        # 7. Owner revokes access entirely
        self._login_as("e2e_owner")
        resp = self.client.delete(
            f"/api/projects/{project_pk}/shares/{share_pk}/"
        )
        self.assertEqual(resp.status_code, 204)

        # 8. Collaborator has no access at all
        self._login_as("e2e_collab")
        resp = self.client.get(f"/api/projects/{project_pk}/tree/")
        self.assertEqual(resp.status_code, 403)

        # 9. All overrides for the collaborator are also gone
        self.assertEqual(
            ObjectPermissionOverride.objects.filter(
                project_id=project_pk, user=self.collaborator
            ).count(),
            0,
        )

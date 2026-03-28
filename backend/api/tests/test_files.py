from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import FileVersion, Folder, Project, ProjectFile


class FileDetailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.folder = Folder.objects.create(
            project=self.project, title="F1", order=0,
        )
        self.text = ProjectFile.objects.create(
            project=self.project,
            folder=self.folder,
            file_type=ProjectFile.FileType.TEXT,
            title="Opening",
            content="# Opening\n\nOnce upon a time...",
        )

    def test_get_file_content(self):
        self.client.force_login(self.owner)
        resp = self.client.get(f"/api/files/{self.text.pk}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["title"], "Opening")
        self.assertIn("Once upon a time", data["content"])
        self.assertEqual(data["source"], "persisted")

    def test_get_file_non_owner(self):
        self.client.force_login(self.other)
        resp = self.client.get(f"/api/files/{self.text.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_get_file_nonexistent(self):
        self.client.force_login(self.owner)
        resp = self.client.get("/api/files/99999/")
        self.assertEqual(resp.status_code, 403)


class FileCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.text = ProjectFile.objects.create(
            project=self.project,
            file_type=ProjectFile.FileType.TEXT,
            title="Opening",
            content="original",
        )
        self.client.force_login(self.owner)

    def test_put_and_get_cache(self):
        resp = self.client.put(
            f"/api/files/{self.text.pk}/cache/",
            {"content": "draft content"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f"/api/files/{self.text.pk}/cache/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["content"], "draft content")

    def test_get_cache_empty(self):
        resp = self.client.get(f"/api/files/{self.text.pk}/cache/")
        self.assertEqual(resp.status_code, 404)

    def test_delete_cache(self):
        self.client.put(
            f"/api/files/{self.text.pk}/cache/",
            {"content": "draft"},
            format="json",
        )
        resp = self.client.delete(f"/api/files/{self.text.pk}/cache/")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f"/api/files/{self.text.pk}/cache/")
        self.assertEqual(resp.status_code, 404)

    def test_file_detail_prefers_cache(self):
        """file_detail_view should return cached content when available."""
        self.client.put(
            f"/api/files/{self.text.pk}/cache/",
            {"content": "cached draft"},
            format="json",
        )
        resp = self.client.get(f"/api/files/{self.text.pk}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["content"], "cached draft")
        self.assertEqual(data["source"], "cache")


class FileVersionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.text = ProjectFile.objects.create(
            project=self.project,
            file_type=ProjectFile.FileType.TEXT,
            title="Opening",
            content="v0",
        )
        self.client.force_login(self.owner)

    def test_create_version(self):
        resp = self.client.post(
            f"/api/files/{self.text.pk}/versions/",
            {"content": "version 1 content"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["content"], "version 1 content")
        self.assertEqual(data["content_length"], len("version 1 content"))
        self.text.refresh_from_db()
        self.assertEqual(self.text.content, "version 1 content")

    def test_list_versions(self):
        FileVersion.objects.create(file=self.text, content="v1")
        FileVersion.objects.create(file=self.text, content="v2 longer")
        resp = self.client.get(f"/api/files/{self.text.pk}/versions/")
        self.assertEqual(resp.status_code, 200)
        versions = resp.json()
        self.assertEqual(len(versions), 2)
        self.assertGreaterEqual(
            versions[0]["created_at"], versions[1]["created_at"],
        )
        self.assertNotIn("content", versions[0])

    def test_get_version_detail(self):
        version = FileVersion.objects.create(file=self.text, content="snapshot")
        resp = self.client.get(
            f"/api/files/{self.text.pk}/versions/{version.pk}/"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["content"], "snapshot")

    def test_get_version_wrong_file(self):
        """Version belongs to a different file — should 404."""
        other_text = ProjectFile.objects.create(
            project=self.project,
            file_type=ProjectFile.FileType.TEXT,
            title="Other",
        )
        version = FileVersion.objects.create(file=other_text, content="x")
        resp = self.client.get(
            f"/api/files/{self.text.pk}/versions/{version.pk}/"
        )
        self.assertEqual(resp.status_code, 404)

    def test_versions_non_owner(self):
        self.client.force_login(self.other)
        resp = self.client.get(f"/api/files/{self.text.pk}/versions/")
        self.assertEqual(resp.status_code, 403)

    def test_create_version_clears_cache(self):
        """Creating a version should clear the draft cache."""
        self.client.put(
            f"/api/files/{self.text.pk}/cache/",
            {"content": "draft"},
            format="json",
        )
        self.client.post(
            f"/api/files/{self.text.pk}/versions/",
            {"content": "saved"},
            format="json",
        )
        resp = self.client.get(f"/api/files/{self.text.pk}/cache/")
        self.assertEqual(resp.status_code, 404)


class FileVersionRevertTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.text = ProjectFile.objects.create(
            project=self.project,
            file_type=ProjectFile.FileType.TEXT,
            title="Opening",
            content="current",
        )
        self.old_version = FileVersion.objects.create(
            file=self.text, content="old content",
        )
        self.client.force_login(self.owner)

    def test_revert_to_version(self):
        resp = self.client.post(
            f"/api/files/{self.text.pk}/versions/{self.old_version.pk}/revert/"
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["content"], "old content")
        self.text.refresh_from_db()
        self.assertEqual(self.text.content, "old content")
        self.assertEqual(self.text.versions.count(), 2)

    def test_revert_clears_cache(self):
        self.client.put(
            f"/api/files/{self.text.pk}/cache/",
            {"content": "draft"},
            format="json",
        )
        self.client.post(
            f"/api/files/{self.text.pk}/versions/{self.old_version.pk}/revert/"
        )
        resp = self.client.get(f"/api/files/{self.text.pk}/cache/")
        self.assertEqual(resp.status_code, 404)

    def test_revert_nonexistent_version(self):
        resp = self.client.post(
            f"/api/files/{self.text.pk}/versions/99999/revert/"
        )
        self.assertEqual(resp.status_code, 404)

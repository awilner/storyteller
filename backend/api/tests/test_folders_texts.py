from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Folder, Project, ProjectFile


class FolderCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")

    def test_create_folder(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/",
            {"title": "Folder 1", "order": 0},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "Folder 1")
        self.assertEqual(data["order"], 0)
        self.assertTrue(
            Folder.objects.filter(project=self.project, title="Folder 1").exists()
        )

    def test_create_folder_non_owner(self):
        self.client.force_login(self.other)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/",
            {"title": "Nope", "order": 0},
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_folder_unauthenticated(self):
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/",
            {"title": "Nope", "order": 0},
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_folder_missing_title(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/",
            {"order": 0},
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_folder_nonexistent_project(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            "/api/projects/99999/folders/",
            {"title": "Ghost", "order": 0},
        )
        self.assertEqual(resp.status_code, 403)


class FolderDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.folder = Folder.objects.create(
            project=self.project, title="Folder 1", order=0,
        )

    def test_delete_folder(self):
        self.client.force_login(self.owner)
        resp = self.client.delete(
            f"/api/projects/{self.project.pk}/folders/{self.folder.pk}/"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Folder.objects.filter(pk=self.folder.pk).exists())

    def test_delete_folder_cascades_files(self):
        """Deleting a folder should delete its files (CASCADE)."""
        self.client.force_login(self.owner)
        text = ProjectFile.objects.create(
            project=self.project,
            folder=self.folder,
            file_type=ProjectFile.FileType.TEXT,
            title="Text 1",
        )
        self.client.delete(
            f"/api/projects/{self.project.pk}/folders/{self.folder.pk}/"
        )
        self.assertFalse(ProjectFile.objects.filter(pk=text.pk).exists())

    def test_delete_folder_non_owner(self):
        self.client.force_login(self.other)
        resp = self.client.delete(
            f"/api/projects/{self.project.pk}/folders/{self.folder.pk}/"
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_folder_wrong_project(self):
        """Folder belongs to a different project — should 404."""
        self.client.force_login(self.owner)
        other_project = Project.objects.create(owner=self.owner, title="Other")
        resp = self.client.delete(
            f"/api/projects/{other_project.pk}/folders/{self.folder.pk}/"
        )
        self.assertEqual(resp.status_code, 404)


class FolderUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.folder = Folder.objects.create(
            project=self.project, title="Folder 1", order=0,
        )

    def url(self):
        return f"/api/projects/{self.project.pk}/folders/{self.folder.pk}/"

    def test_update_title(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"title": "Renamed"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.title, "Renamed")

    def test_update_description(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"description": "A dark night."}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.description, "A dark night.")

    def test_update_notes(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"notes": "Remember the twist."}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.notes, "Remember the twist.")

    def test_update_tags(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"tags": ["action", "drama"]}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.tags, ["action", "drama"])

    def test_update_target_word_count(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"target_word_count": 5000}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.target_word_count, 5000)

    def test_update_target_word_count_null(self):
        self.client.force_login(self.owner)
        self.folder.target_word_count = 3000
        self.folder.save()
        resp = self.client.patch(self.url(), {"target_word_count": None}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.folder.refresh_from_db()
        self.assertIsNone(self.folder.target_word_count)

    def test_partial_update_only_changes_specified_fields(self):
        self.client.force_login(self.owner)
        self.folder.description = "Original"
        self.folder.save()
        resp = self.client.patch(self.url(), {"notes": "New note"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.description, "Original")
        self.assertEqual(self.folder.notes, "New note")

    def test_update_non_owner_denied(self):
        self.client.force_login(self.other)
        resp = self.client.patch(self.url(), {"title": "Nope"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_update_unauthenticated(self):
        resp = self.client.patch(self.url(), {"title": "Nope"}, format="json")
        self.assertEqual(resp.status_code, 403)


class TextCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.folder = Folder.objects.create(
            project=self.project, title="Folder 1", order=0,
        )

    def test_create_text(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/{self.folder.pk}/texts/",
            {"title": "Opening Text", "order": 0},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "Opening Text")
        text = ProjectFile.objects.get(pk=data["id"])
        self.assertEqual(text.file_type, ProjectFile.FileType.TEXT)
        self.assertEqual(text.folder_id, self.folder.pk)
        self.assertEqual(text.project_id, self.project.pk)

    def test_create_text_non_owner(self):
        self.client.force_login(self.other)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/{self.folder.pk}/texts/",
            {"title": "Nope", "order": 0},
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_text_missing_title(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/{self.folder.pk}/texts/",
            {"order": 0},
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_text_nonexistent_folder(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/99999/texts/",
            {"title": "Ghost", "order": 0},
        )
        self.assertEqual(resp.status_code, 404)


class TextDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.folder = Folder.objects.create(
            project=self.project, title="Folder 1", order=0,
        )
        self.text = ProjectFile.objects.create(
            project=self.project,
            folder=self.folder,
            file_type=ProjectFile.FileType.TEXT,
            title="Text 1",
        )

    def test_delete_text(self):
        self.client.force_login(self.owner)
        resp = self.client.delete(
            f"/api/projects/{self.project.pk}/texts/{self.text.pk}/"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ProjectFile.objects.filter(pk=self.text.pk).exists())

    def test_delete_text_non_owner(self):
        self.client.force_login(self.other)
        resp = self.client.delete(
            f"/api/projects/{self.project.pk}/texts/{self.text.pk}/"
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_non_text_file_allowed(self):
        """Deleting a character file via the text endpoint should succeed."""
        self.client.force_login(self.owner)
        char_file = ProjectFile.objects.create(
            project=self.project,
            folder=self.folder,
            file_type=ProjectFile.FileType.CHARACTER,
            title="Hero",
        )
        resp = self.client.delete(
            f"/api/projects/{self.project.pk}/texts/{char_file.pk}/"
        )
        self.assertEqual(resp.status_code, 204)


class TextUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.folder = Folder.objects.create(
            project=self.project, title="Folder 1", order=0,
        )
        self.text = ProjectFile.objects.create(
            project=self.project,
            folder=self.folder,
            file_type=ProjectFile.FileType.TEXT,
            title="Text 1",
        )

    def url(self):
        return f"/api/projects/{self.project.pk}/texts/{self.text.pk}/"

    def test_update_title(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"title": "Renamed Text"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.text.refresh_from_db()
        self.assertEqual(self.text.title, "Renamed Text")

    def test_update_description(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"description": "A tense moment."}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.text.refresh_from_db()
        self.assertEqual(self.text.description, "A tense moment.")

    def test_update_notes(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"notes": "Add foreshadowing."}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.text.refresh_from_db()
        self.assertEqual(self.text.notes, "Add foreshadowing.")

    def test_update_tags(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"tags": ["suspense", "reveal"]}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.text.refresh_from_db()
        self.assertEqual(self.text.tags, ["suspense", "reveal"])

    def test_update_target_word_count(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(self.url(), {"target_word_count": 2000}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.text.refresh_from_db()
        self.assertEqual(self.text.target_word_count, 2000)

    def test_update_target_word_count_null(self):
        self.client.force_login(self.owner)
        self.text.target_word_count = 1500
        self.text.save()
        resp = self.client.patch(self.url(), {"target_word_count": None}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.text.refresh_from_db()
        self.assertIsNone(self.text.target_word_count)

    def test_partial_update_only_changes_specified_fields(self):
        self.client.force_login(self.owner)
        self.text.description = "Original desc"
        self.text.save()
        resp = self.client.patch(self.url(), {"notes": "New note"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.text.refresh_from_db()
        self.assertEqual(self.text.description, "Original desc")
        self.assertEqual(self.text.notes, "New note")

    def test_update_non_owner_denied(self):
        self.client.force_login(self.other)
        resp = self.client.patch(self.url(), {"title": "Nope"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_update_unauthenticated(self):
        resp = self.client.patch(self.url(), {"title": "Nope"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_update_non_text_via_text_endpoint_allowed(self):
        """PATCH on a character file via the text endpoint should succeed."""
        self.client.force_login(self.owner)
        char_file = ProjectFile.objects.create(
            project=self.project,
            folder=self.folder,
            file_type=ProjectFile.FileType.CHARACTER,
            title="Hero",
        )
        resp = self.client.patch(
            f"/api/projects/{self.project.pk}/texts/{char_file.pk}/",
            {"title": "Updated Hero"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        char_file.refresh_from_db()
        self.assertEqual(char_file.title, "Updated Hero")


class SubfolderCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.parent = Folder.objects.create(
            project=self.project, title="Parent", order=0,
        )

    def test_create_subfolder(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/",
            {"title": "Child", "order": 0, "parent": self.parent.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "Child")
        self.assertEqual(data["parent"], self.parent.pk)
        child = Folder.objects.get(pk=data["id"])
        self.assertEqual(child.parent, self.parent)
        self.assertEqual(child.project, self.project)

    def test_create_root_folder_no_parent(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/",
            {"title": "Root", "order": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIsNone(data["parent"])

    def test_create_subfolder_wrong_project(self):
        """Parent folder belongs to a different project — should 400."""
        self.client.force_login(self.owner)
        other_project = Project.objects.create(owner=self.owner, title="Other")
        resp = self.client.post(
            f"/api/projects/{other_project.pk}/folders/",
            {"title": "Bad", "order": 0, "parent": self.parent.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_subfolder_non_owner(self):
        self.client.force_login(self.other)
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/folders/",
            {"title": "Nope", "order": 0, "parent": self.parent.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_parent_cascades_subfolder(self):
        self.client.force_login(self.owner)
        child = Folder.objects.create(
            project=self.project, title="Child", order=0, parent=self.parent,
        )
        resp = self.client.delete(
            f"/api/projects/{self.project.pk}/folders/{self.parent.pk}/"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Folder.objects.filter(pk=child.pk).exists())

    def test_delete_parent_cascades_nested_texts(self):
        """Texts in a subfolder should be deleted when parent folder is deleted (CASCADE)."""
        self.client.force_login(self.owner)
        child = Folder.objects.create(
            project=self.project, title="Child", order=0, parent=self.parent,
        )
        text = ProjectFile.objects.create(
            project=self.project,
            folder=child,
            file_type=ProjectFile.FileType.TEXT,
            title="Nested Text",
        )
        self.client.delete(
            f"/api/projects/{self.project.pk}/folders/{self.parent.pk}/"
        )
        self.assertFalse(ProjectFile.objects.filter(pk=text.pk).exists())

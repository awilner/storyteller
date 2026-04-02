from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Folder, Project, ProjectFile


class ProjectTreeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.f1 = Folder.objects.create(
            project=self.project, title="Folder 1", order=0,
        )
        self.f2 = Folder.objects.create(
            project=self.project, title="Folder 2", order=1,
        )
        self.text1 = ProjectFile.objects.create(
            project=self.project,
            folder=self.f1,
            file_type=ProjectFile.FileType.TEXT,
            title="Opening",
            order=0,
        )
        self.char_folder = Folder.objects.create(
            project=self.project, title="Characters", order=2,
        )
        self.char_file = ProjectFile.objects.create(
            project=self.project,
            folder=self.char_folder,
            file_type=ProjectFile.FileType.CHARACTER,
            title="Hero",
            order=0,
        )
        self.loc_folder = Folder.objects.create(
            project=self.project, title="Locations", order=3,
        )
        self.loc_file = ProjectFile.objects.create(
            project=self.project,
            folder=self.loc_folder,
            file_type=ProjectFile.FileType.LOCATION,
            title="Castle",
            order=0,
        )

    def test_tree_returns_full_hierarchy(self):
        self.client.force_login(self.owner)
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["title"], "Novel")
        self.assertEqual(len(data["folders"]), 4)

        f1_data = next(f for f in data["folders"] if f["id"] == self.f1.pk)
        self.assertEqual(len(f1_data["items"]), 1)
        self.assertEqual(f1_data["items"][0]["title"], "Opening")

        char_folder = next(f for f in data["folders"] if f["title"] == "Characters")
        self.assertEqual(len(char_folder["items"]), 1)
        self.assertEqual(char_folder["items"][0]["title"], "Hero")

        loc_folder = next(f for f in data["folders"] if f["title"] == "Locations")
        self.assertEqual(len(loc_folder["items"]), 1)
        self.assertEqual(loc_folder["items"][0]["title"], "Castle")

    def test_tree_non_owner_denied(self):
        self.client.force_login(self.other)
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        self.assertEqual(resp.status_code, 403)

    def test_tree_unauthenticated(self):
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        self.assertEqual(resp.status_code, 403)

    def test_tree_nonexistent_project(self):
        self.client.force_login(self.owner)
        resp = self.client.get("/api/projects/99999/tree/")
        self.assertEqual(resp.status_code, 403)

    def test_tree_empty_project(self):
        self.client.force_login(self.owner)
        empty = Project.objects.create(owner=self.owner, title="Empty")
        resp = self.client.get(f"/api/projects/{empty.pk}/tree/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["folders"], [])

    def test_tree_response_is_json(self):
        """Verify we get JSON, not HTML (regression for BrowsableAPI bug)."""
        self.client.force_login(self.owner)
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        self.assertEqual(resp["Content-Type"], "application/json")

    def test_tree_includes_property_fields(self):
        """Tree response should include description, notes, tags, target_word_count."""
        self.client.force_login(self.owner)
        self.f1.description = "Dark beginning"
        self.f1.tags = ["intro"]
        self.f1.target_word_count = 3000
        self.f1.save()
        self.text1.description = "Text desc"
        self.text1.tags = ["action"]
        self.text1.target_word_count = 1000
        self.text1.save()

        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        data = resp.json()
        f1_data = next(f for f in data["folders"] if f["id"] == self.f1.pk)
        self.assertEqual(f1_data["description"], "Dark beginning")
        self.assertEqual(f1_data["tags"], ["intro"])
        self.assertEqual(f1_data["target_word_count"], 3000)
        self.assertIn("notes", f1_data)

        text_data = f1_data["items"][0]
        self.assertEqual(text_data["description"], "Text desc")
        self.assertEqual(text_data["tags"], ["action"])
        self.assertEqual(text_data["target_word_count"], 1000)
        self.assertIn("notes", text_data)


class NestedFolderTreeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")
        self.root = Folder.objects.create(
            project=self.project, title="Act 1", order=0,
        )
        self.child = Folder.objects.create(
            project=self.project, title="Chapter 1", order=0, parent=self.root,
        )
        self.grandchild = Folder.objects.create(
            project=self.project, title="Section A", order=0, parent=self.child,
        )
        self.text_in_root = ProjectFile.objects.create(
            project=self.project,
            folder=self.root,
            file_type=ProjectFile.FileType.TEXT,
            title="Prologue",
            order=0,
        )
        self.text_in_child = ProjectFile.objects.create(
            project=self.project,
            folder=self.child,
            file_type=ProjectFile.FileType.TEXT,
            title="Scene 1",
            order=0,
        )
        self.text_in_grandchild = ProjectFile.objects.create(
            project=self.project,
            folder=self.grandchild,
            file_type=ProjectFile.FileType.TEXT,
            title="Paragraph 1",
            order=0,
        )

    def test_tree_includes_nested_children(self):
        self.client.force_login(self.owner)
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Only root folders at top level
        self.assertEqual(len(data["folders"]), 1)
        root_data = data["folders"][0]
        self.assertEqual(root_data["title"], "Act 1")
        self.assertEqual(len(root_data["items"]), 1)
        self.assertEqual(root_data["items"][0]["title"], "Prologue")
        # Child folder nested
        self.assertEqual(len(root_data["children"]), 1)
        child_data = root_data["children"][0]
        self.assertEqual(child_data["title"], "Chapter 1")
        self.assertEqual(len(child_data["items"]), 1)
        self.assertEqual(child_data["items"][0]["title"], "Scene 1")
        # Grandchild folder nested
        self.assertEqual(len(child_data["children"]), 1)
        gc_data = child_data["children"][0]
        self.assertEqual(gc_data["title"], "Section A")
        self.assertEqual(len(gc_data["items"]), 1)
        self.assertEqual(gc_data["items"][0]["title"], "Paragraph 1")

    def test_tree_excludes_subfolders_from_root(self):
        """Subfolders should not appear at the top-level folders list."""
        self.client.force_login(self.owner)
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        data = resp.json()
        top_ids = [f["id"] for f in data["folders"]]
        self.assertNotIn(self.child.pk, top_ids)
        self.assertNotIn(self.grandchild.pk, top_ids)

    def test_tree_children_have_property_fields(self):
        self.client.force_login(self.owner)
        self.child.description = "First chapter"
        self.child.tags = ["intro"]
        self.child.save()
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        data = resp.json()
        child_data = data["folders"][0]["children"][0]
        self.assertEqual(child_data["description"], "First chapter")
        self.assertEqual(child_data["tags"], ["intro"])

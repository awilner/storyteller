from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from api.models import FileVersion, Folder, OIDCIdentity, Project, ProjectFile


class ProjectModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pw")

    def test_str(self):
        p = Project.objects.create(owner=self.user, title="My Novel")
        self.assertEqual(str(p), "My Novel")

    def test_ordering(self):
        """Projects should be ordered by -updated_at (most recent first)."""
        p1 = Project.objects.create(owner=self.user, title="First")
        p2 = Project.objects.create(owner=self.user, title="Second")
        p1.title = "First Updated"
        p1.save()
        projects = list(Project.objects.all())
        self.assertEqual(projects[0].pk, p1.pk)


class FolderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.user, title="Novel")

    def test_str(self):
        f = Folder.objects.create(project=self.project, title="Intro", order=1)
        self.assertEqual(str(f), "1. Intro")

    def test_duplicate_order_allowed(self):
        """After removing unique_together, duplicate order values are allowed."""
        Folder.objects.create(project=self.project, title="F1", order=0)
        f2 = Folder.objects.create(project=self.project, title="F2", order=0)
        self.assertEqual(f2.order, 0)

    def test_nested_subfolder(self):
        parent = Folder.objects.create(project=self.project, title="Parent", order=0)
        child = Folder.objects.create(project=self.project, title="Child", order=0, parent=parent)
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())

    def test_cascade_delete_subfolder(self):
        """Deleting a parent folder should cascade-delete its subfolders."""
        parent = Folder.objects.create(project=self.project, title="Parent", order=0)
        child = Folder.objects.create(project=self.project, title="Child", order=0, parent=parent)
        parent.delete()
        self.assertFalse(Folder.objects.filter(pk=child.pk).exists())

    def test_cascade_delete_with_project(self):
        Folder.objects.create(project=self.project, title="F1", order=0)
        self.project.delete()
        self.assertEqual(Folder.objects.count(), 0)


class ProjectFileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.user, title="Novel")

    def test_str(self):
        f = ProjectFile.objects.create(
            project=self.project,
            file_type=ProjectFile.FileType.TEXT,
            title="Opening",
        )
        self.assertEqual(str(f), "[text] Opening")

    def test_default_content_empty(self):
        f = ProjectFile.objects.create(
            project=self.project,
            file_type=ProjectFile.FileType.NOTE,
            title="Note",
        )
        self.assertEqual(f.content, "")

    def test_folder_set_null_on_delete(self):
        """Deleting a folder should set text's folder FK to NULL, not delete the text."""
        folder = Folder.objects.create(project=self.project, title="F1", order=0)
        text = ProjectFile.objects.create(
            project=self.project,
            folder=folder,
            file_type=ProjectFile.FileType.TEXT,
            title="Text",
        )
        folder.delete()
        text.refresh_from_db()
        self.assertIsNone(text.folder)


class FileVersionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.user, title="Novel")
        self.text = ProjectFile.objects.create(
            project=self.project,
            file_type=ProjectFile.FileType.TEXT,
            title="Opening",
        )

    def test_content_length_auto_calculated(self):
        v = FileVersion.objects.create(file=self.text, content="hello world")
        self.assertEqual(v.content_length, 11)

    def test_str(self):
        v = FileVersion.objects.create(file=self.text, content="x")
        self.assertIn("Version", str(v))

    def test_ordering_newest_first(self):
        v1 = FileVersion.objects.create(file=self.text, content="first")
        v2 = FileVersion.objects.create(file=self.text, content="second")
        versions = list(self.text.versions.all())
        self.assertEqual(versions[0].pk, v2.pk)

    def test_cascade_delete_with_file(self):
        FileVersion.objects.create(file=self.text, content="v1")
        self.text.delete()
        self.assertEqual(FileVersion.objects.count(), 0)


class OIDCIdentityModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pw")

    def test_str(self):
        oid = OIDCIdentity.objects.create(
            user=self.user, provider="google", sub="abc123",
        )
        self.assertIn("google", str(oid))
        self.assertIn("abc123", str(oid))

    def test_unique_together_provider_sub(self):
        OIDCIdentity.objects.create(
            user=self.user, provider="google", sub="abc123",
        )
        user2 = User.objects.create_user(username="bob", password="pw")
        with self.assertRaises(IntegrityError):
            OIDCIdentity.objects.create(
                user=user2, provider="google", sub="abc123",
            )

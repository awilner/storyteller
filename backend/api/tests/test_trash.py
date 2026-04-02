"""Tests for trash folder behavior."""

import io
import zipfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Folder, Project, ProjectFile
from api.scrivener import import_scrivener_zip
from api.ywriter import import_ywriter


def _make_zip(file_dict):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in file_dict.items():
            zf.writestr(path, content)
    buf.seek(0)
    return SimpleUploadedFile("test.zip", buf.read(), content_type="application/zip")


class TrashFolderAutoCreationTests(TestCase):
    """Test auto-creation of trash folder on tree fetch."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.user, title="Novel")
        self.client.force_login(self.user)

    def test_tree_auto_creates_trash_folder(self):
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        trash_folders = [f for f in data["folders"] if f.get("is_trash")]
        self.assertEqual(len(trash_folders), 1)
        self.assertEqual(trash_folders[0]["title"], "Trash")

    def test_trash_folder_appears_last(self):
        Folder.objects.create(project=self.project, title="Chapter 1", order=0)
        Folder.objects.create(project=self.project, title="Chapter 2", order=1)
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        data = resp.json()
        self.assertTrue(data["folders"][-1]["is_trash"])

    def test_no_duplicate_trash_on_second_fetch(self):
        self.client.get(f"/api/projects/{self.project.pk}/tree/")
        self.client.get(f"/api/projects/{self.project.pk}/tree/")
        self.assertEqual(
            self.project.folders.filter(is_trash=True).count(), 1
        )

    def test_trash_has_correct_icon(self):
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        trash = [f for f in resp.json()["folders"] if f["is_trash"]][0]
        self.assertEqual(trash["icon"], "🗑️")

    def test_is_trash_field_in_serialized_output(self):
        resp = self.client.get(f"/api/projects/{self.project.pk}/tree/")
        data = resp.json()
        for folder in data["folders"]:
            self.assertIn("is_trash", folder)


class TrashFolderProtectionTests(TestCase):
    """Test that trash folder cannot be deleted or reparented."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.user, title="Novel")
        self.trash = Folder.objects.create(
            project=self.project, title="Trash", icon="🗑️",
            is_trash=True, order=9999,
        )
        self.client.force_login(self.user)

    def test_delete_trash_folder_returns_400(self):
        resp = self.client.delete(
            f"/api/projects/{self.project.pk}/folders/{self.trash.pk}/"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Cannot delete", resp.json()["detail"])
        self.assertTrue(Folder.objects.filter(pk=self.trash.pk).exists())

    def test_reparent_trash_folder_succeeds_server_side(self):
        """Server allows reorder — drag prevention is handled by the frontend."""
        other = Folder.objects.create(
            project=self.project, title="Other", order=0,
        )
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/reorder/",
            {"folders": [{"id": self.trash.pk, "order": 0, "parent": other.pk}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_reorder_trash_without_reparent_succeeds(self):
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/reorder/",
            {"folders": [{"id": self.trash.pk, "order": 5, "parent": None}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)


class SoftDeleteTests(TestCase):
    """Test soft-delete (move to trash) via PATCH."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.user, title="Novel")
        self.trash = Folder.objects.create(
            project=self.project, title="Trash", icon="🗑️",
            is_trash=True, order=9999,
        )
        self.folder = Folder.objects.create(
            project=self.project, title="Chapter 1", order=0,
        )
        self.text = ProjectFile.objects.create(
            project=self.project, folder=self.folder,
            file_type=ProjectFile.FileType.TEXT, title="Scene 1", order=0,
        )
        self.client.force_login(self.user)

    def test_soft_delete_folder(self):
        resp = self.client.patch(
            f"/api/projects/{self.project.pk}/folders/{self.folder.pk}/",
            {"parent": self.trash.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.parent_id, self.trash.pk)

    def test_soft_delete_text(self):
        resp = self.client.patch(
            f"/api/projects/{self.project.pk}/texts/{self.text.pk}/",
            {"folder": self.trash.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.text.refresh_from_db()
        self.assertEqual(self.text.folder_id, self.trash.pk)


class PermanentDeleteTests(TestCase):
    """Test permanent delete of items inside trash."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.user, title="Novel")
        self.trash = Folder.objects.create(
            project=self.project, title="Trash", icon="🗑️",
            is_trash=True, order=9999,
        )
        self.client.force_login(self.user)

    def test_delete_folder_inside_trash(self):
        folder = Folder.objects.create(
            project=self.project, title="Deleted Chapter",
            parent=self.trash, order=0,
        )
        child_text = ProjectFile.objects.create(
            project=self.project, folder=folder,
            file_type=ProjectFile.FileType.TEXT, title="Scene", order=0,
        )
        resp = self.client.delete(
            f"/api/projects/{self.project.pk}/folders/{folder.pk}/"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Folder.objects.filter(pk=folder.pk).exists())
        self.assertFalse(ProjectFile.objects.filter(pk=child_text.pk).exists())

    def test_delete_text_inside_trash(self):
        text = ProjectFile.objects.create(
            project=self.project, folder=self.trash,
            file_type=ProjectFile.FileType.TEXT, title="Deleted Scene", order=0,
        )
        resp = self.client.delete(
            f"/api/projects/{self.project.pk}/texts/{text.pk}/"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ProjectFile.objects.filter(pk=text.pk).exists())


class EmptyTrashTests(TestCase):
    """Test empty trash endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.project = Project.objects.create(owner=self.user, title="Novel")
        self.trash = Folder.objects.create(
            project=self.project, title="Trash", icon="🗑️",
            is_trash=True, order=9999,
        )
        self.client.force_login(self.user)

    def test_empty_trash_removes_contents(self):
        child_folder = Folder.objects.create(
            project=self.project, title="Old Chapter",
            parent=self.trash, order=0,
        )
        child_text = ProjectFile.objects.create(
            project=self.project, folder=self.trash,
            file_type=ProjectFile.FileType.TEXT, title="Old Scene", order=0,
        )
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/trash/empty/"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Folder.objects.filter(pk=child_folder.pk).exists())
        self.assertFalse(ProjectFile.objects.filter(pk=child_text.pk).exists())

    def test_empty_trash_keeps_trash_folder(self):
        self.client.post(f"/api/projects/{self.project.pk}/trash/empty/")
        self.assertTrue(Folder.objects.filter(pk=self.trash.pk).exists())

    def test_empty_trash_when_already_empty(self):
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/trash/empty/"
        )
        self.assertEqual(resp.status_code, 204)

    def test_empty_trash_no_trash_folder_returns_404(self):
        self.trash.delete()
        resp = self.client.post(
            f"/api/projects/{self.project.pk}/trash/empty/"
        )
        self.assertEqual(resp.status_code, 404)


class ScrivenerTrashImportTests(TestCase):
    """Test Scrivener import with TrashFolder binder items."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pw")

    def _scrivener_zip_with_trash(self):
        scrivx = """\
<?xml version="1.0" encoding="UTF-8"?>
<ScrivenerProject>
  <Binder>
    <BinderItem Type="DraftFolder" ID="0">
      <Title>Draft</Title>
      <Children>
        <BinderItem Type="Folder" ID="10">
          <Title>Chapter One</Title>
          <Children>
            <BinderItem Type="Text" ID="11">
              <Title>Opening</Title>
            </BinderItem>
          </Children>
        </BinderItem>
      </Children>
    </BinderItem>
    <BinderItem Type="TrashFolder" ID="99">
      <Title>Trash</Title>
      <Children>
        <BinderItem Type="Text" ID="100">
          <Title>Deleted Scene</Title>
        </BinderItem>
      </Children>
    </BinderItem>
  </Binder>
</ScrivenerProject>
"""
        files = {
            "MyNovel.scriv/MyNovel.scrivx": scrivx,
            "MyNovel.scriv/Files/Docs/11.md": "Opening content.",
            "MyNovel.scriv/Files/Docs/100.md": "Deleted content.",
        }
        return _make_zip(files)

    def _scrivener_zip_without_trash(self):
        scrivx = """\
<?xml version="1.0" encoding="UTF-8"?>
<ScrivenerProject>
  <Binder>
    <BinderItem Type="DraftFolder" ID="0">
      <Title>Draft</Title>
      <Children>
        <BinderItem Type="Text" ID="11">
          <Title>Opening</Title>
        </BinderItem>
      </Children>
    </BinderItem>
  </Binder>
</ScrivenerProject>
"""
        files = {
            "MyNovel.scriv/MyNovel.scrivx": scrivx,
            "MyNovel.scriv/Files/Docs/11.md": "Opening content.",
        }
        return _make_zip(files)

    def test_scrivener_import_with_trash_folder(self):
        project = import_scrivener_zip(self._scrivener_zip_with_trash(), self.user)
        trash = project.folders.filter(is_trash=True)
        self.assertEqual(trash.count(), 1)
        trash_folder = trash.first()
        self.assertEqual(trash_folder.title, "Trash")
        # Trash should contain the deleted scene
        trash_texts = trash_folder.texts.all()
        self.assertEqual(trash_texts.count(), 1)
        self.assertEqual(trash_texts.first().title, "Deleted Scene")

    def test_scrivener_import_without_trash_creates_empty_trash(self):
        project = import_scrivener_zip(self._scrivener_zip_without_trash(), self.user)
        trash = project.folders.filter(is_trash=True)
        self.assertEqual(trash.count(), 1)
        trash_folder = trash.first()
        self.assertEqual(trash_folder.texts.count(), 0)
        self.assertEqual(trash_folder.children.count(), 0)


class YWriterTrashImportTests(TestCase):
    """Test yWriter import creates empty trash folder."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pw")

    def test_ywriter_import_creates_trash_folder(self):
        yw7_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<YWRITER7>
  <PROJECT>
    <Title><![CDATA[Test Novel]]></Title>
  </PROJECT>
  <CHAPTERS>
    <CHAPTER>
      <ID>1</ID>
      <Title><![CDATA[Chapter One]]></Title>
      <SortOrder>1</SortOrder>
      <Scenes><ScID>1</ScID></Scenes>
    </CHAPTER>
  </CHAPTERS>
  <SCENES>
    <SCENE>
      <ID>1</ID>
      <Title><![CDATA[Opening]]></Title>
      <SceneContent><![CDATA[Hello world.]]></SceneContent>
    </SCENE>
  </SCENES>
</YWRITER7>
"""
        uploaded = _make_zip({"novel/novel.yw7": yw7_xml})
        project = import_ywriter(uploaded, self.user)
        trash = project.folders.filter(is_trash=True)
        self.assertEqual(trash.count(), 1)
        trash_folder = trash.first()
        self.assertEqual(trash_folder.title, "Trash")
        self.assertEqual(trash_folder.icon, "🗑️")
        self.assertEqual(trash_folder.texts.count(), 0)


class TrashTranslationTests(TestCase):
    """Test that trash translation keys exist."""

    def setUp(self):
        self.client = APIClient()

    def test_trash_translation_keys_exist(self):
        resp = self.client.get("/api/i18n/strings/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("trash.title", data)
        self.assertIn("trash.empty_trash", data)
        self.assertIn("trash.permanently_delete", data)
        self.assertIn("trash.confirm_empty", data)
        self.assertIn("trash.confirm_permanent_delete", data)
        self.assertIn("trash.confirm_permanent_delete_folder", data)

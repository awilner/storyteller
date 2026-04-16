"""Tests for Scrivener and yWriter7 import functionality."""

import io
import os
import zipfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Folder, Project, ProjectFile
from api.import_export import import_scrivener_zip
from api.import_export import import_ywriter
from api.import_export.ywriter_common import bbcode_to_markdown as _bbcode_to_markdown


# ── Helpers ───────────────────────────────────────────────────

def _make_zip(file_dict):
    """Create an in-memory zip from {path: content} dict and return SimpleUploadedFile."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in file_dict.items():
            zf.writestr(path, content)
    buf.seek(0)
    return SimpleUploadedFile("test.zip", buf.read(), content_type="application/zip")


MINIMAL_SCRIVX = """\
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
              <TextSettings><Target Type="Words">500</Target></TextSettings>
            </BinderItem>
            <BinderItem Type="Text" ID="12">
              <Title>Conflict</Title>
            </BinderItem>
          </Children>
        </BinderItem>
        <BinderItem Type="Folder" ID="20">
          <Title>Chapter Two</Title>
          <Children>
            <BinderItem Type="Text" ID="21">
              <Title>Resolution</Title>
            </BinderItem>
          </Children>
        </BinderItem>
      </Children>
    </BinderItem>
    <BinderItem Type="Folder" ID="90">
      <Title>Characters</Title>
      <Children>
        <BinderItem Type="Text" ID="91">
          <Title>Hero</Title>
        </BinderItem>
      </Children>
    </BinderItem>
    <BinderItem Type="Folder" ID="95">
      <Title>Places</Title>
      <Children>
        <BinderItem Type="Text" ID="96">
          <Title>Castle</Title>
        </BinderItem>
      </Children>
    </BinderItem>
  </Binder>
</ScrivenerProject>
"""


def _scrivener_zip(extra_docs=None):
    """Build a minimal Scrivener .scriv.zip."""
    files = {
        "MyNovel.scriv/MyNovel.scrivx": MINIMAL_SCRIVX,
        "MyNovel.scriv/Files/Docs/11.md": "It was a dark and stormy night.",
        "MyNovel.scriv/Files/Docs/12.md": "The hero faced the villain.",
        "MyNovel.scriv/Files/Docs/21.md": "Peace was restored.",
        "MyNovel.scriv/Files/Docs/91.md": "A brave warrior.",
        "MyNovel.scriv/Files/Docs/96.md": "An ancient fortress.",
        "MyNovel.scriv/Files/Docs/11_synopsis.txt": "The story begins.",
    }
    if extra_docs:
        files.update(extra_docs)
    return _make_zip(files)


MINIMAL_YW7 = """\
<?xml version="1.0" encoding="UTF-8"?>
<YWRITER7>
  <PROJECT>
    <Title><![CDATA[Test Novel]]></Title>
    <Desc><![CDATA[A test project]]></Desc>
  </PROJECT>
  <CHAPTERS>
    <CHAPTER>
      <ID>1</ID>
      <Title><![CDATA[Chapter One]]></Title>
      <Desc><![CDATA[First chapter]]></Desc>
      <SortOrder>1</SortOrder>
      <Scenes><ScID>1</ScID><ScID>2</ScID></Scenes>
    </CHAPTER>
    <CHAPTER>
      <ID>2</ID>
      <Title><![CDATA[Chapter Two]]></Title>
      <SortOrder>2</SortOrder>
      <Scenes><ScID>3</ScID></Scenes>
    </CHAPTER>
  </CHAPTERS>
  <SCENES>
    <SCENE>
      <ID>1</ID>
      <Title><![CDATA[Opening]]></Title>
      <BelongsToChID>1</BelongsToChID>
      <SceneContent><![CDATA[Hello [i]world[/i].
Second paragraph.]]></SceneContent>
      <Desc><![CDATA[Scene synopsis]]></Desc>
      <Notes><![CDATA[Author note]]></Notes>
    </SCENE>
    <SCENE>
      <ID>2</ID>
      <Title><![CDATA[Unused Scene]]></Title>
      <Unused>-1</Unused>
      <BelongsToChID>1</BelongsToChID>
      <SceneContent><![CDATA[Should be skipped.]]></SceneContent>
    </SCENE>
    <SCENE>
      <ID>3</ID>
      <Title><![CDATA[Finale]]></Title>
      <BelongsToChID>2</BelongsToChID>
      <SceneContent><![CDATA[[b]Bold[/b] and [s]struck[/s].]]></SceneContent>
    </SCENE>
  </SCENES>
  <CHARACTERS>
    <CHARACTER>
      <ID>1</ID>
      <Title><![CDATA[Hero]]></Title>
      <Desc><![CDATA[Brave]]></Desc>
      <Bio><![CDATA[Born in a village]]></Bio>
      <Notes><![CDATA[Protagonist]]></Notes>
      <FullName><![CDATA[John Doe]]></FullName>
      <SortOrder>1</SortOrder>
      <Major>-1</Major>
    </CHARACTER>
    <CHARACTER>
      <ID>2</ID>
      <Title><![CDATA[Sidekick]]></Title>
      <SortOrder>2</SortOrder>
    </CHARACTER>
  </CHARACTERS>
  <LOCATIONS>
    <LOCATION>
      <ID>1</ID>
      <Title><![CDATA[Village]]></Title>
      <Desc><![CDATA[A small village]]></Desc>
      <SortOrder>1</SortOrder>
    </LOCATION>
  </LOCATIONS>
  <ITEMS>
    <ITEM>
      <ID>1</ID>
      <Title><![CDATA[Magic Sword]]></Title>
      <Desc><![CDATA[A legendary blade]]></Desc>
      <SortOrder>1</SortOrder>
    </ITEM>
  </ITEMS>
  <PROJECTNOTES>
    <PROJECTNOTE>
      <ID>1</ID>
      <Title><![CDATA[Story themes]]></Title>
      <Desc><![CDATA[Good vs evil]]></Desc>
      <SortOrder>1</SortOrder>
    </PROJECTNOTE>
    <PROJECTNOTE>
      <ID>2</ID>
      <Title><![CDATA[Research]]></Title>
      <Desc><![CDATA[Medieval weapons]]></Desc>
      <SortOrder>2</SortOrder>
    </PROJECTNOTE>
  </PROJECTNOTES>
</YWRITER7>
"""


def _ywriter_file(yw7_xml=None):
    """Build a minimal yWriter7 .yw7 uploaded file."""
    content = (yw7_xml or MINIMAL_YW7).encode("utf-8")
    return SimpleUploadedFile("novel.yw7", content, content_type="application/xml")


# ── BBCode-to-Markdown unit tests ────────────────────────────

class BBCodeToMarkdownTests(TestCase):
    """Unit tests for the _bbcode_to_markdown helper."""

    def test_italic(self):
        self.assertEqual(_bbcode_to_markdown("[i]hello[/i]"), "*hello*")

    def test_bold(self):
        self.assertEqual(_bbcode_to_markdown("[b]hello[/b]"), "**hello**")

    def test_strikethrough(self):
        self.assertEqual(_bbcode_to_markdown("[s]hello[/s]"), "~~hello~~")

    def test_mixed_tags(self):
        result = _bbcode_to_markdown("[b]bold[/b] and [i]italic[/i]")
        self.assertEqual(result, "**bold** and *italic*")

    def test_nested_tags(self):
        result = _bbcode_to_markdown("[b][i]both[/i][/b]")
        self.assertEqual(result, "***both***")

    def test_no_tags(self):
        self.assertEqual(_bbcode_to_markdown("plain text"), "plain text")

    def test_single_newline_becomes_double(self):
        result = _bbcode_to_markdown("para one\npara two")
        self.assertEqual(result, "para one\n\npara two")

    def test_existing_double_newline_preserved(self):
        result = _bbcode_to_markdown("para one\n\npara two")
        self.assertEqual(result, "para one\n\npara two")

    def test_triple_newline_normalized(self):
        result = _bbcode_to_markdown("para one\n\n\npara two")
        self.assertEqual(result, "para one\n\npara two")

    def test_multiple_paragraphs(self):
        result = _bbcode_to_markdown("one\ntwo\nthree")
        self.assertEqual(result, "one\n\ntwo\n\nthree")

    def test_italic_across_no_newline(self):
        result = _bbcode_to_markdown("He said [i]wow[/i] and left.")
        self.assertEqual(result, "He said *wow* and left.")

    def test_empty_string(self):
        self.assertEqual(_bbcode_to_markdown(""), "")

    def test_italic_trailing_space_trimmed(self):
        """Trailing space inside [i]...[/i] must move outside the markers."""
        result = _bbcode_to_markdown("[i]hello [/i]world")
        self.assertEqual(result, "*hello* world")

    def test_italic_leading_space_trimmed(self):
        result = _bbcode_to_markdown("[i] hello[/i]")
        self.assertEqual(result, " *hello*")

    def test_multiple_italic_spans_with_spaces(self):
        result = _bbcode_to_markdown("[i]one [/i]and [i]two [/i]end")
        self.assertEqual(result, "*one* and *two* end")


# ── Scrivener import tests ───────────────────────────────────

class ScrivenerImportTests(TestCase):
    """Tests for import_scrivener_zip."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pw")

    def test_basic_import(self):
        project = import_scrivener_zip(_scrivener_zip(), self.user)
        self.assertEqual(project.title, "MyNovel")
        self.assertEqual(project.owner, self.user)

    def test_folders_created(self):
        project = import_scrivener_zip(_scrivener_zip(), self.user)
        root_folders = list(project.folders.filter(parent__isnull=True).order_by("order"))
        # Manuscript, Characters, Locations + Trash
        self.assertEqual(len(root_folders), 4)
        non_trash = [f for f in root_folders if not f.is_trash]
        self.assertEqual(len(non_trash), 3)
        self.assertEqual(non_trash[0].title, "Manuscript")
        self.assertEqual(non_trash[0].icon, "📖")
        # Chapter folders are children of Manuscript
        chapters = list(non_trash[0].children.order_by("order"))
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0].title, "Chapter One")
        self.assertEqual(chapters[1].title, "Chapter Two")

    def test_texts_created_in_folders(self):
        project = import_scrivener_zip(_scrivener_zip(), self.user)
        ch1 = project.folders.get(title="Chapter One")
        texts = list(ch1.texts.order_by("order"))
        self.assertEqual(len(texts), 2)
        self.assertEqual(texts[0].title, "Opening")
        self.assertEqual(texts[0].content, "It was a dark and stormy night.")
        self.assertEqual(texts[1].title, "Conflict")

    def test_text_synopsis_imported(self):
        project = import_scrivener_zip(_scrivener_zip(), self.user)
        opening = ProjectFile.objects.get(project=project, title="Opening")
        self.assertEqual(opening.description, "The story begins.")

    def test_target_word_count(self):
        project = import_scrivener_zip(_scrivener_zip(), self.user)
        opening = ProjectFile.objects.get(project=project, title="Opening")
        self.assertEqual(opening.target_word_count, 500)

    def test_characters_imported(self):
        project = import_scrivener_zip(_scrivener_zip(), self.user)
        chars = project.files.filter(file_type="character")
        self.assertEqual(chars.count(), 1)
        self.assertEqual(chars.first().title, "Hero")

    def test_locations_imported(self):
        project = import_scrivener_zip(_scrivener_zip(), self.user)
        locs = project.files.filter(file_type="location")
        self.assertEqual(locs.count(), 1)
        self.assertEqual(locs.first().title, "Castle")

    def test_no_scrivx_raises(self):
        bad_zip = _make_zip({"readme.txt": "nothing here"})
        with self.assertRaises(ValueError) as ctx:
            import_scrivener_zip(bad_zip, self.user)
        self.assertIn(".scrivx", str(ctx.exception))

    def test_no_binder_raises(self):
        bad_scrivx = '<?xml version="1.0"?><ScrivenerProject></ScrivenerProject>'
        bad_zip = _make_zip({"proj.scriv/proj.scrivx": bad_scrivx})
        with self.assertRaises(ValueError) as ctx:
            import_scrivener_zip(bad_zip, self.user)
        self.assertIn("Binder", str(ctx.exception))


class ScrivenerImportViewTests(TestCase):
    """Tests for the scrivener import API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.client.force_login(self.user)

    def test_import_success(self):
        resp = self.client.post(
            "/api/projects/import/scrivener/",
            {"file": _scrivener_zip()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["title"], "MyNovel")
        self.assertEqual(Project.objects.filter(owner=self.user).count(), 1)

    def test_import_no_file(self):
        resp = self.client.post("/api/projects/import/scrivener/")
        self.assertEqual(resp.status_code, 400)

    def test_import_unauthenticated(self):
        self.client.logout()
        resp = self.client.post(
            "/api/projects/import/scrivener/",
            {"file": _scrivener_zip()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 403)


# ── yWriter7 import tests ────────────────────────────────────

class YWriterImportTests(TestCase):
    """Tests for import_ywriter."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pw")

    def test_basic_import(self):
        project = import_ywriter(_ywriter_file(), self.user)
        self.assertEqual(project.title, "Test Novel")
        self.assertEqual(project.description, "A test project")
        self.assertEqual(project.owner, self.user)

    def test_folders_from_chapters(self):
        project = import_ywriter(_ywriter_file(), self.user)
        root_folders = list(project.folders.filter(parent__isnull=True).order_by("order"))
        # Manuscript + Characters + Locations + Items + Notes + Trash
        non_trash = [f for f in root_folders if not f.is_trash]
        self.assertEqual(len(non_trash), 5)
        self.assertEqual(non_trash[0].title, "Manuscript")
        self.assertEqual(non_trash[0].icon, "📖")
        # Chapters are children of Manuscript
        chapters = list(non_trash[0].children.order_by("order"))
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0].title, "Chapter One")
        self.assertEqual(chapters[0].description, "First chapter")
        self.assertEqual(chapters[1].title, "Chapter Two")

    def test_texts_from_scenes(self):
        project = import_ywriter(_ywriter_file(), self.user)
        ch1 = project.folders.get(title="Chapter One")
        texts = list(ch1.texts.order_by("order"))
        # Scene 2 is unused, so only scene 1 should be imported
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0].title, "Opening")

    def test_unused_scenes_skipped(self):
        project = import_ywriter(_ywriter_file(), self.user)
        self.assertFalse(
            project.files.filter(title="Unused Scene").exists()
        )

    def test_bbcode_italic_converted(self):
        project = import_ywriter(_ywriter_file(), self.user)
        opening = project.files.get(title="Opening")
        self.assertIn("*world*", opening.content)
        self.assertNotIn("[i]", opening.content)

    def test_bbcode_bold_converted(self):
        project = import_ywriter(_ywriter_file(), self.user)
        finale = project.files.get(title="Finale")
        self.assertIn("**Bold**", finale.content)
        self.assertNotIn("[b]", finale.content)

    def test_bbcode_strikethrough_converted(self):
        project = import_ywriter(_ywriter_file(), self.user)
        finale = project.files.get(title="Finale")
        self.assertIn("~~struck~~", finale.content)
        self.assertNotIn("[s]", finale.content)

    def test_newlines_converted_to_paragraphs(self):
        project = import_ywriter(_ywriter_file(), self.user)
        opening = project.files.get(title="Opening")
        # Single \n in source should become \n\n
        self.assertIn("\n\n", opening.content)
        self.assertIn("Second paragraph.", opening.content)

    def test_scene_description_and_notes(self):
        project = import_ywriter(_ywriter_file(), self.user)
        opening = project.files.get(title="Opening")
        self.assertEqual(opening.description, "Scene synopsis")
        self.assertEqual(opening.notes, "Author note")

    def test_characters_imported(self):
        project = import_ywriter(_ywriter_file(), self.user)
        chars = list(project.files.filter(file_type="character").order_by("order"))
        self.assertEqual(len(chars), 2)
        self.assertEqual(chars[0].title, "Hero")
        self.assertEqual(chars[1].title, "Sidekick")

    def test_character_content_assembled(self):
        project = import_ywriter(_ywriter_file(), self.user)
        hero = project.files.get(title="Hero")
        self.assertIn("**Full Name:** John Doe", hero.content)
        self.assertIn("**Description:** Brave", hero.content)
        self.assertIn("**Biography:** Born in a village", hero.content)
        self.assertEqual(hero.notes, "Protagonist")

    def test_character_minimal_fields(self):
        """Character with only a title should still import cleanly."""
        project = import_ywriter(_ywriter_file(), self.user)
        sidekick = project.files.get(title="Sidekick")
        # No fullname/desc/bio, so content should be empty
        self.assertEqual(sidekick.content, "")

    def test_locations_imported(self):
        project = import_ywriter(_ywriter_file(), self.user)
        locs = list(project.files.filter(file_type="location"))
        self.assertEqual(len(locs), 1)
        self.assertEqual(locs[0].title, "Village")
        self.assertEqual(locs[0].description, "A small village")

    def test_items_imported(self):
        project = import_ywriter(_ywriter_file(), self.user)
        items_folder = project.folders.get(title="Items")
        self.assertEqual(items_folder.icon, "🧰")
        items = list(items_folder.texts.order_by("order"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Magic Sword")
        self.assertEqual(items[0].content, "A legendary blade")
        self.assertEqual(items[0].file_type, "item")

    def test_project_notes_imported(self):
        project = import_ywriter(_ywriter_file(), self.user)
        notes_folder = project.folders.get(title="Notes")
        self.assertEqual(notes_folder.icon, "📒")
        notes = list(notes_folder.texts.order_by("order"))
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0].title, "Story themes")
        self.assertEqual(notes[0].content, "Good vs evil")
        self.assertEqual(notes[1].title, "Research")
        self.assertEqual(notes[1].content, "Medieval weapons")

    def test_invalid_xml_raises(self):
        bad_file = SimpleUploadedFile("bad.yw7", b"not xml at all", content_type="application/xml")
        with self.assertRaises(ValueError) as ctx:
            import_ywriter(bad_file, self.user)
        self.assertIn(".yw7", str(ctx.exception))

    def test_chapter_sort_order_respected(self):
        """Chapters should be ordered by SortOrder, not by ID."""
        # Swap sort orders: Chapter One gets sort=5, Chapter Two keeps sort=2
        xml = MINIMAL_YW7.replace(
            "<SortOrder>1</SortOrder>\n      <Scenes><ScID>1</ScID><ScID>2</ScID></Scenes>",
            "<SortOrder>5</SortOrder>\n      <Scenes><ScID>1</ScID><ScID>2</ScID></Scenes>",
        )
        project = import_ywriter(_ywriter_file(xml), self.user)
        manuscript = project.folders.get(title="Manuscript")
        chapters = list(manuscript.children.order_by("order"))
        # Chapter Two (sort=2) should come before Chapter One (sort=5)
        self.assertEqual(chapters[0].title, "Chapter Two")
        self.assertEqual(chapters[1].title, "Chapter One")


class YWriterImportViewTests(TestCase):
    """Tests for the yWriter import API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.client.force_login(self.user)

    def test_import_success(self):
        resp = self.client.post(
            "/api/projects/import/ywriter/",
            {"file": _ywriter_file()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["title"], "Test Novel")

    def test_import_no_file(self):
        resp = self.client.post("/api/projects/import/ywriter/")
        self.assertEqual(resp.status_code, 400)

    def test_import_unauthenticated(self):
        self.client.logout()
        resp = self.client.post(
            "/api/projects/import/ywriter/",
            {"file": _ywriter_file()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 403)

    def test_import_bad_file(self):
        bad_file = SimpleUploadedFile("bad.yw7", b"not xml", content_type="application/xml")
        resp = self.client.post(
            "/api/projects/import/ywriter/",
            {"file": bad_file},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("YWriter import failed", resp.json()["detail"])

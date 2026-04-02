"""
yWriter7 project (.yw7 inside a .zip) importer.

Parses the .yw7 XML and imports Chapters as Folders, Scenes as Texts,
Characters as CHARACTER ProjectFiles, and Locations as LOCATION ProjectFiles.
"""

import os
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from django.utils.translation import gettext as _

from .models import Folder, Project, ProjectFile


def _cdata_text(element, tag):
    """Safely extract text from a CDATA-wrapped child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _bbcode_replace(open_tag, close_tag, md_delim):
    """Return a regex substitution function that converts a BBCode pair to
    markdown, trimming inner whitespace so delimiters stay valid.

    Markdown requires that opening/closing emphasis markers are flush
    against the content (no space after opening or before closing marker).
    yWriter authors often write ``[i]text [/i]`` with trailing spaces, so
    we move that whitespace outside the markers.
    """
    pattern = re.compile(
        re.escape(open_tag) + r"(.*?)" + re.escape(close_tag),
        re.DOTALL,
    )

    def _replacer(m):
        inner = m.group(1)
        stripped = inner.strip()
        if not stripped:
            return inner  # nothing to emphasise
        leading = inner[: len(inner) - len(inner.lstrip())]
        trailing = inner[len(inner.rstrip()) :]
        return f"{leading}{md_delim}{stripped}{md_delim}{trailing}"

    def apply(text):
        return pattern.sub(_replacer, text)

    return apply


_italic = _bbcode_replace("[i]", "[/i]", "*")
_bold = _bbcode_replace("[b]", "[/b]", "**")
_strike = _bbcode_replace("[s]", "[/s]", "~~")


def _bbcode_to_markdown(text):
    """Convert yWriter BBCode formatting and line breaks to Markdown.

    yWriter stores paragraphs separated by single newlines and uses
    BBCode tags ([i], [b], [s]) for inline formatting.  Markdown needs
    double newlines for paragraph breaks and *, **, ~~ for formatting.
    """
    # BBCode -> Markdown inline formatting (whitespace-safe)
    text = _italic(text)
    text = _bold(text)
    text = _strike(text)

    # Convert single newlines to double newlines for markdown paragraphs.
    # First normalise any existing double-newlines so we don't quadruple them.
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", text)

    return text


def _int_text(element, tag, default=0):
    """Extract an integer from a child element, with fallback."""
    val = _cdata_text(element, tag)
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def import_ywriter(uploaded_file, user):
    """
    Import a yWriter7 file (.yw7 or .zip containing a .yw7) and return the created Project.

    Args:
        uploaded_file: An uploaded file (InMemoryUploadedFile or similar).
        user: The Django User who will own the project.

    Returns:
        The created Project instance.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save the uploaded file
        tmp_path = os.path.join(tmpdir, uploaded_file.name or "upload")
        with open(tmp_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        # Determine if it's a zip or a raw .yw7
        yw7_path = None
        if zipfile.is_zipfile(tmp_path):
            with zipfile.ZipFile(tmp_path, "r") as zf:
                zf.extractall(tmpdir)
            for root_dir, _dirs, files in os.walk(tmpdir):
                for fname in files:
                    if fname.endswith(".yw7"):
                        yw7_path = os.path.join(root_dir, fname)
                        break
                if yw7_path:
                    break
        elif tmp_path.endswith(".yw7") or uploaded_file.name.endswith(".yw7"):
            yw7_path = tmp_path
        else:
            # Try parsing as XML directly — might be a .yw7 with wrong extension
            yw7_path = tmp_path

        if not yw7_path or not os.path.isfile(yw7_path):
            raise ValueError("No .yw7 file found in the uploaded file.")

        tree = ET.parse(yw7_path)
        root_el = tree.getroot()

        # Project title from <PROJECT><Title>
        proj_el = root_el.find("PROJECT")
        project_title = _cdata_text(proj_el, "Title") if proj_el is not None else ""
        if not project_title:
            project_title = os.path.splitext(os.path.basename(yw7_path))[0]

        project = Project.objects.create(
            owner=user,
            title=project_title,
            description=_cdata_text(proj_el, "Desc") if proj_el is not None else "",
        )

        # Build a scene lookup: scene_id -> scene element
        scene_map = {}
        for scene_el in root_el.findall(".//SCENES/SCENE"):
            sid = _cdata_text(scene_el, "ID")
            if sid:
                scene_map[sid] = scene_el

        # Import chapters under a "Manuscript" folder
        chapters = root_el.findall(".//CHAPTERS/CHAPTER")
        chapters.sort(key=lambda ch: _int_text(ch, "SortOrder", 9999))

        manuscript_folder = Folder.objects.create(
            project=project,
            parent=None,
            title=_("Manuscript"),
            icon="📖",
            order=0,
        )

        for folder_order, ch_el in enumerate(chapters):
            ch_title = _cdata_text(ch_el, "Title") or "Untitled Chapter"
            ch_desc = _cdata_text(ch_el, "Desc")

            folder = Folder.objects.create(
                project=project,
                parent=manuscript_folder,
                title=ch_title,
                description=ch_desc,
                order=folder_order,
            )

            # Import scenes belonging to this chapter
            scene_ids = [sc.text for sc in ch_el.findall("Scenes/ScID") if sc.text]
            for text_order, sc_id in enumerate(scene_ids):
                sc_el = scene_map.get(sc_id)
                if sc_el is None:
                    continue

                # Skip scenes marked as unused
                if _cdata_text(sc_el, "Unused") == "-1":
                    continue

                sc_title = _cdata_text(sc_el, "Title") or "Untitled Scene"
                sc_content = _bbcode_to_markdown(_cdata_text(sc_el, "SceneContent"))
                sc_desc = _cdata_text(sc_el, "Desc")
                sc_notes = _cdata_text(sc_el, "Notes")

                ProjectFile.objects.create(
                    project=project,
                    folder=folder,
                    file_type=ProjectFile.FileType.TEXT,
                    title=sc_title,
                    description=sc_desc,
                    notes=sc_notes,
                    content=sc_content,
                    order=text_order,
                )

        # Import characters into a "Characters" folder
        characters = root_el.findall(".//CHARACTERS/CHARACTER")
        characters.sort(key=lambda c: _int_text(c, "SortOrder", 9999))

        if characters:
            next_root_order = project.folders.filter(parent__isnull=True).count()
            char_folder = Folder.objects.create(
                project=project, title=_("Characters"), icon="👥", order=next_root_order,
            )

            for char_order, char_el in enumerate(characters):
                char_title = _cdata_text(char_el, "Title") or "Untitled Character"
                full_name = _cdata_text(char_el, "FullName")
                desc = _cdata_text(char_el, "Desc")
                bio = _cdata_text(char_el, "Bio")
                notes = _cdata_text(char_el, "Notes")

                content_parts = []
                if full_name:
                    content_parts.append(f"**Full Name:** {full_name}")
                if desc:
                    content_parts.append(f"**Description:** {desc}")
                if bio:
                    content_parts.append(f"**Biography:** {bio}")
                content = "\n\n".join(content_parts)

                ProjectFile.objects.create(
                    project=project,
                    folder=char_folder,
                    file_type=ProjectFile.FileType.CHARACTER,
                    title=char_title,
                    description=desc,
                    notes=notes,
                    content=content,
                    order=char_order,
                )

        # Import locations into a "Locations" folder
        locations = root_el.findall(".//LOCATIONS/LOCATION")
        locations.sort(key=lambda loc: _int_text(loc, "SortOrder", 9999))

        if locations:
            next_root_order = project.folders.filter(parent__isnull=True).count()
            loc_folder = Folder.objects.create(
                project=project, title=_("Locations"), icon="🌎", order=next_root_order,
            )

            for loc_order, loc_el in enumerate(locations):
                loc_title = _cdata_text(loc_el, "Title") or "Untitled Location"
                loc_desc = _cdata_text(loc_el, "Desc")

                ProjectFile.objects.create(
                    project=project,
                    folder=loc_folder,
                    file_type=ProjectFile.FileType.LOCATION,
                    title=loc_title,
                    description=loc_desc,
                    content=loc_desc,
                    order=loc_order,
                )

        # Import items into an "Items" folder
        items_els = root_el.findall(".//ITEMS/ITEM")
        items_els.sort(key=lambda it: _int_text(it, "SortOrder", 9999))

        if items_els:
            next_root_order = project.folders.filter(parent__isnull=True).count()
            items_folder = Folder.objects.create(
                project=project, title=_("Items"), icon="🧰", order=next_root_order,
            )

            for item_order, item_el in enumerate(items_els):
                item_title = _cdata_text(item_el, "Title") or "Untitled Item"
                item_desc = _cdata_text(item_el, "Desc")

                ProjectFile.objects.create(
                    project=project,
                    folder=items_folder,
                    file_type=ProjectFile.FileType.ITEM,
                    title=item_title,
                    description=item_desc,
                    content=item_desc,
                    order=item_order,
                )

        # Import project notes into a "Notes" folder
        notes_els = root_el.findall(".//PROJECTNOTES/PROJECTNOTE")
        notes_els.sort(key=lambda n: _int_text(n, "SortOrder", 9999))

        if notes_els:
            next_root_order = project.folders.filter(parent__isnull=True).count()
            notes_folder = Folder.objects.create(
                project=project, title=_("Notes"), icon="📒", order=next_root_order,
            )

            for note_order, note_el in enumerate(notes_els):
                note_title = _cdata_text(note_el, "Title") or "Untitled Note"
                note_desc = _cdata_text(note_el, "Desc")

                ProjectFile.objects.create(
                    project=project,
                    folder=notes_folder,
                    file_type=ProjectFile.FileType.NOTE,
                    title=note_title,
                    description=note_desc,
                    content=note_desc,
                    order=note_order,
                )

    return project

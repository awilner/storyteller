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


def import_ywriter_zip(zip_file, user):
    """
    Import a yWriter7 .zip file and return the created Project.

    The zip is expected to contain a .yw7 XML file.

    Args:
        zip_file: An uploaded file (InMemoryUploadedFile or similar).
        user: The Django User who will own the project.

    Returns:
        The created Project instance.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "upload.zip")
        with open(zip_path, "wb") as f:
            for chunk in zip_file.chunks():
                f.write(chunk)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        # Find the .yw7 file
        yw7_path = None
        for root_dir, _dirs, files in os.walk(tmpdir):
            for fname in files:
                if fname.endswith(".yw7"):
                    yw7_path = os.path.join(root_dir, fname)
                    break
            if yw7_path:
                break

        if not yw7_path:
            raise ValueError("No .yw7 file found in the uploaded archive.")

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

        # Import chapters as Folders, sorted by SortOrder
        chapters = root_el.findall(".//CHAPTERS/CHAPTER")
        chapters.sort(key=lambda ch: _int_text(ch, "SortOrder", 9999))

        for folder_order, ch_el in enumerate(chapters):
            ch_title = _cdata_text(ch_el, "Title") or "Untitled Chapter"
            ch_desc = _cdata_text(ch_el, "Desc")

            folder = Folder.objects.create(
                project=project,
                parent=None,
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

        # Import characters
        characters = root_el.findall(".//CHARACTERS/CHARACTER")
        characters.sort(key=lambda c: _int_text(c, "SortOrder", 9999))

        for char_order, char_el in enumerate(characters):
            char_title = _cdata_text(char_el, "Title") or "Untitled Character"
            full_name = _cdata_text(char_el, "FullName")
            desc = _cdata_text(char_el, "Desc")
            bio = _cdata_text(char_el, "Bio")
            notes = _cdata_text(char_el, "Notes")

            # Combine bio and description into content
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
                folder=None,
                file_type=ProjectFile.FileType.CHARACTER,
                title=char_title,
                description=desc,
                notes=notes,
                content=content,
                order=char_order,
            )

        # Import locations
        locations = root_el.findall(".//LOCATIONS/LOCATION")
        locations.sort(key=lambda loc: _int_text(loc, "SortOrder", 9999))

        for loc_order, loc_el in enumerate(locations):
            loc_title = _cdata_text(loc_el, "Title") or "Untitled Location"
            loc_desc = _cdata_text(loc_el, "Desc")

            ProjectFile.objects.create(
                project=project,
                folder=None,
                file_type=ProjectFile.FileType.LOCATION,
                title=loc_title,
                description=loc_desc,
                content=loc_desc,
                order=loc_order,
            )

    return project

"""
yWriter7 project (.yw7) importer.

Parses the .yw7 XML and imports Chapters as Folders, Scenes as Texts,
Characters, Locations, Items, and Notes as world-building ProjectFiles.
"""

import os
import tempfile

import defusedxml.ElementTree as ET
from django.utils.translation import gettext as _

from ..models import Folder, Project, ProjectFile
from .ywriter_common import bbcode_to_markdown


def _cdata_text(element, tag):
    """Safely extract text from a CDATA-wrapped child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _int_text(element, tag, default=0):
    """Extract an integer from a child element, with fallback."""
    val = _cdata_text(element, tag)
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def import_ywriter(uploaded_file, user):
    """Import a yWriter7 .yw7 file and return the created Project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".yw7", dir=tmpdir, delete=False) as f:
            tmp_path_real = os.path.realpath(f.name)
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        try:
            tree = ET.parse(tmp_path_real)
        except ET.ParseError:
            raise ValueError("Invalid .yw7 file: could not parse XML.")
        root_el = tree.getroot()

        proj_el = root_el.find("PROJECT")
        project_title = _cdata_text(proj_el, "Title") if proj_el is not None else ""
        if not project_title:
            project_title = os.path.splitext(uploaded_file.name or "Untitled")[0]

        project = Project.objects.create(
            owner=user, title=project_title,
            description=_cdata_text(proj_el, "Desc") if proj_el is not None else "",
        )

        # Build scene lookup
        scene_map = {}
        for scene_el in root_el.findall(".//SCENES/SCENE"):
            sid = _cdata_text(scene_el, "ID")
            if sid:
                scene_map[sid] = scene_el

        # Import chapters
        chapters = root_el.findall(".//CHAPTERS/CHAPTER")
        chapters.sort(key=lambda ch: _int_text(ch, "SortOrder", 9999))

        manuscript_folder = Folder.objects.create(
            project=project, parent=None, title=_("Manuscript"), icon="📖", order=0,
        )

        for folder_order, ch_el in enumerate(chapters):
            folder = Folder.objects.create(
                project=project, parent=manuscript_folder,
                title=_cdata_text(ch_el, "Title") or "Untitled Chapter",
                description=_cdata_text(ch_el, "Desc"), order=folder_order,
            )
            scene_ids = [sc.text for sc in ch_el.findall("Scenes/ScID") if sc.text]
            for text_order, sc_id in enumerate(scene_ids):
                sc_el = scene_map.get(sc_id)
                if sc_el is None or _cdata_text(sc_el, "Unused") == "-1":
                    continue
                ProjectFile.objects.create(
                    project=project, folder=folder,
                    file_type=ProjectFile.FileType.TEXT,
                    title=_cdata_text(sc_el, "Title") or "Untitled Scene",
                    description=_cdata_text(sc_el, "Desc"),
                    notes=_cdata_text(sc_el, "Notes"),
                    content=bbcode_to_markdown(_cdata_text(sc_el, "SceneContent")),
                    order=text_order,
                )

        # Characters
        characters = root_el.findall(".//CHARACTERS/CHARACTER")
        characters.sort(key=lambda c: _int_text(c, "SortOrder", 9999))
        if characters:
            char_folder = Folder.objects.create(
                project=project, title=_("Characters"), icon="👥",
                order=project.folders.filter(parent__isnull=True).count(),
            )
            for i, char_el in enumerate(characters):
                full_name = _cdata_text(char_el, "FullName")
                desc = _cdata_text(char_el, "Desc")
                bio = _cdata_text(char_el, "Bio")
                parts = []
                if full_name:
                    parts.append(f"**Full Name:** {full_name}")
                if desc:
                    parts.append(f"**Description:** {desc}")
                if bio:
                    parts.append(f"**Biography:** {bio}")
                ProjectFile.objects.create(
                    project=project, folder=char_folder,
                    file_type=ProjectFile.FileType.CHARACTER,
                    title=_cdata_text(char_el, "Title") or "Untitled Character",
                    description=desc, notes=_cdata_text(char_el, "Notes"),
                    content="\n\n".join(parts), order=i,
                )

        # Locations
        locations = root_el.findall(".//LOCATIONS/LOCATION")
        locations.sort(key=lambda loc: _int_text(loc, "SortOrder", 9999))
        if locations:
            loc_folder = Folder.objects.create(
                project=project, title=_("Locations"), icon="🌎",
                order=project.folders.filter(parent__isnull=True).count(),
            )
            for i, loc_el in enumerate(locations):
                loc_desc = _cdata_text(loc_el, "Desc")
                ProjectFile.objects.create(
                    project=project, folder=loc_folder,
                    file_type=ProjectFile.FileType.LOCATION,
                    title=_cdata_text(loc_el, "Title") or "Untitled Location",
                    description=loc_desc, content=loc_desc, order=i,
                )

        # Items
        items_els = root_el.findall(".//ITEMS/ITEM")
        items_els.sort(key=lambda it: _int_text(it, "SortOrder", 9999))
        if items_els:
            items_folder = Folder.objects.create(
                project=project, title=_("Items"), icon="🧰",
                order=project.folders.filter(parent__isnull=True).count(),
            )
            for i, item_el in enumerate(items_els):
                item_desc = _cdata_text(item_el, "Desc")
                ProjectFile.objects.create(
                    project=project, folder=items_folder,
                    file_type=ProjectFile.FileType.ITEM,
                    title=_cdata_text(item_el, "Title") or "Untitled Item",
                    description=item_desc, content=item_desc, order=i,
                )

        # Notes
        notes_els = root_el.findall(".//PROJECTNOTES/PROJECTNOTE")
        notes_els.sort(key=lambda n: _int_text(n, "SortOrder", 9999))
        if notes_els:
            notes_folder = Folder.objects.create(
                project=project, title=_("Notes"), icon="📒",
                order=project.folders.filter(parent__isnull=True).count(),
            )
            for i, note_el in enumerate(notes_els):
                note_desc = _cdata_text(note_el, "Desc")
                ProjectFile.objects.create(
                    project=project, folder=notes_folder,
                    file_type=ProjectFile.FileType.NOTE,
                    title=_cdata_text(note_el, "Title") or "Untitled Note",
                    description=note_desc, content=note_desc, order=i,
                )

    # Trash folder
    Folder.objects.create(
        project=project, title=_("Trash"), icon="🗑️", is_trash=True, parent=None,
        order=project.folders.filter(parent__isnull=True).count(),
    )
    return project

"""
Scrivener project (.scriv.zip) importer.

Parses the .scrivx XML binder structure and imports the DraftFolder
hierarchy as Folders/Texts, plus Characters and Places as world-building
ProjectFiles.
"""

import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from django.utils.translation import gettext as _
from striprtf.striprtf import rtf_to_text

from .models import Folder, Project, ProjectFile


def _read_content(docs_dir, binder_id):
    """Read content for a binder item, preferring .md over .rtf."""
    md_path = os.path.join(docs_dir, f"{binder_id}.md")
    if os.path.isfile(md_path):
        with open(md_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    rtf_path = os.path.join(docs_dir, f"{binder_id}.rtf")
    if os.path.isfile(rtf_path):
        with open(rtf_path, "r", encoding="utf-8", errors="replace") as f:
            try:
                return rtf_to_text(f.read())
            except Exception:
                return ""
    return ""


def _read_synopsis(docs_dir, binder_id):
    """Read synopsis text if it exists."""
    path = os.path.join(docs_dir, f"{binder_id}_synopsis.txt")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return ""


def _read_notes(docs_dir, binder_id):
    """Read notes RTF if it exists."""
    path = os.path.join(docs_dir, f"{binder_id}_notes.rtf")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            try:
                return rtf_to_text(f.read())
            except Exception:
                return ""
    return ""


def _get_target_word_count(item_el):
    """Extract target word count from <TextSettings><Target Type="Words">."""
    ts = item_el.find("TextSettings")
    if ts is not None:
        target = ts.find("Target")
        if target is not None and target.get("Type") == "Words":
            try:
                return int(target.text)
            except (TypeError, ValueError):
                pass
    return None


def _import_binder_children(children_el, project, docs_dir, parent_folder, order_start=0):
    """
    Recursively import <BinderItem> elements under a <Children> element.
    Creates Folders for Type=Folder and Texts for Type=Text.
    Returns the next available order value.
    """
    if children_el is None:
        return order_start

    order = order_start
    for item in children_el.findall("BinderItem"):
        item_type = item.get("Type", "")
        item_id = item.get("ID", "")
        title = ""
        title_el = item.find("Title")
        if title_el is not None and title_el.text:
            title = title_el.text

        if item_type == "Folder":
            folder = Folder.objects.create(
                project=project,
                parent=parent_folder,
                title=title or "Untitled Folder",
                description=_read_synopsis(docs_dir, item_id),
                notes=_read_notes(docs_dir, item_id),
                target_word_count=_get_target_word_count(item),
                order=order,
            )
            order += 1
            sub_children = item.find("Children")
            _import_binder_children(sub_children, project, docs_dir, folder, 0)

        elif item_type == "Text":
            content = _read_content(docs_dir, item_id)
            ProjectFile.objects.create(
                project=project,
                folder=parent_folder,
                file_type=ProjectFile.FileType.TEXT,
                title=title or "Untitled",
                description=_read_synopsis(docs_dir, item_id),
                notes=_read_notes(docs_dir, item_id),
                content=content,
                target_word_count=_get_target_word_count(item),
                order=order,
            )
            order += 1

    return order


def _import_world_building(children_el, project, docs_dir, file_type, folder):
    """Import children of a world-building folder (Characters, Places) as ProjectFiles."""
    if children_el is None:
        return
    order = 0
    for item in children_el.findall("BinderItem"):
        item_id = item.get("ID", "")
        title_el = item.find("Title")
        title = (title_el.text if title_el is not None and title_el.text else "Untitled")

        content = _read_content(docs_dir, item_id)
        ProjectFile.objects.create(
            project=project,
            folder=folder,
            file_type=file_type,
            title=title,
            description=_read_synopsis(docs_dir, item_id),
            notes=_read_notes(docs_dir, item_id),
            content=content,
            target_word_count=_get_target_word_count(item),
            order=order,
        )
        order += 1


def import_scrivener_zip(zip_file, user):
    """
    Import a Scrivener .scriv.zip file and return the created Project.

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

        # Find the .scrivx file
        scrivx_path = None
        scriv_root = None
        for root, _dirs, files in os.walk(tmpdir):
            for fname in files:
                if fname.endswith(".scrivx"):
                    scrivx_path = os.path.join(root, fname)
                    scriv_root = root
                    break
            if scrivx_path:
                break

        if not scrivx_path:
            raise ValueError("No .scrivx file found in the uploaded archive.")

        docs_dir = os.path.join(scriv_root, "Files", "Docs")

        tree = ET.parse(scrivx_path)
        root_el = tree.getroot()
        binder = root_el.find("Binder")
        if binder is None:
            raise ValueError("Invalid Scrivener file: no <Binder> element found.")

        # Derive project title from the .scrivx filename
        project_title = os.path.splitext(os.path.basename(scrivx_path))[0]

        project = Project.objects.create(owner=user, title=project_title)

        # Track folder order at root level
        root_order = 0

        # Walk top-level binder items
        for item in binder.findall("BinderItem"):
            item_type = item.get("Type", "")
            children_el = item.find("Children")

            if item_type == "DraftFolder":
                # Main manuscript content under a "Manuscript" folder
                manuscript_folder = Folder.objects.create(
                    project=project, title=_("Manuscript"), icon="📖", order=root_order,
                )
                root_order += 1
                _import_binder_children(children_el, project, docs_dir, manuscript_folder, 0)

            elif item_type == "Folder":
                title_el = item.find("Title")
                title = (title_el.text if title_el is not None else "").lower()
                if "character" in title:
                    char_folder = Folder.objects.create(
                        project=project, title=_("Characters"), icon="👥", order=root_order,
                    )
                    root_order += 1
                    _import_world_building(
                        children_el, project, docs_dir,
                        ProjectFile.FileType.CHARACTER, char_folder,
                    )
                elif "place" in title or "location" in title:
                    loc_folder = Folder.objects.create(
                        project=project, title=_("Locations"), icon="🌎", order=root_order,
                    )
                    root_order += 1
                    _import_world_building(
                        children_el, project, docs_dir,
                        ProjectFile.FileType.LOCATION, loc_folder,
                    )

            # Skip ResearchFolder, TrashFolder, Template Sheets, etc.

    return project

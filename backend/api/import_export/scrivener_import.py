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

from ..models import Folder, Label, Project, ProjectFile, Status
from .scrivener_common import scriv_colour_to_hex


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


def _get_metadata_id(item_el, tag):
    """Extract an integer ID from a MetaData child element."""
    meta = item_el.find("MetaData")
    if meta is not None:
        el = meta.find(tag)
        if el is not None and el.text:
            try:
                val = int(el.text)
                return val if val >= 0 else None
            except (ValueError, TypeError):
                pass
    return None


def _parse_label_settings(root_el):
    """Parse <LabelSettings> and return list of dicts with id, name, colour."""
    ls = root_el.find("LabelSettings")
    if ls is None:
        return []
    labels_el = ls.find("Labels")
    if labels_el is None:
        return []
    labels = []
    for label_el in labels_el.findall("Label"):
        lid = label_el.get("ID", "")
        try:
            lid_int = int(lid)
        except (ValueError, TypeError):
            continue
        if lid_int < 0:
            continue
        name = label_el.text or ""
        colour = scriv_colour_to_hex(label_el.get("Color", ""))
        labels.append({"scriv_id": lid_int, "name": name, "colour": colour})
    return labels


def _parse_status_settings(root_el):
    """Parse <StatusSettings> and return list of dicts with id, name."""
    ss = root_el.find("StatusSettings")
    if ss is None:
        return []
    items_el = ss.find("StatusItems")
    if items_el is None:
        return []
    statuses = []
    for status_el in items_el.findall("Status"):
        sid = status_el.get("ID", "")
        try:
            sid_int = int(sid)
        except (ValueError, TypeError):
            continue
        if sid_int < 0:
            continue
        name = status_el.text or ""
        statuses.append({"scriv_id": sid_int, "name": name})
    return statuses


def _import_binder_children(children_el, project, docs_dir, parent_folder, order_start=0, label_map=None, status_map=None):
    """Recursively import <BinderItem> elements under a <Children> element."""
    if children_el is None:
        return order_start
    if label_map is None:
        label_map = {}
    if status_map is None:
        status_map = {}

    order = order_start
    for item in children_el.findall("BinderItem"):
        item_type = item.get("Type", "")
        item_id = item.get("ID", "")
        title_el = item.find("Title")
        title = title_el.text if title_el is not None and title_el.text else ""

        label_id = label_map.get(_get_metadata_id(item, "LabelID"))
        status_id = status_map.get(_get_metadata_id(item, "StatusID"))

        if item_type == "Folder":
            folder = Folder.objects.create(
                project=project, parent=parent_folder,
                title=title or "Untitled Folder",
                description=_read_synopsis(docs_dir, item_id),
                notes=_read_notes(docs_dir, item_id),
                target_word_count=_get_target_word_count(item),
                label_id=label_id, status_id=status_id, order=order,
            )
            order += 1
            _import_binder_children(item.find("Children"), project, docs_dir, folder, 0, label_map, status_map)
        elif item_type == "Text":
            ProjectFile.objects.create(
                project=project, folder=parent_folder,
                file_type=ProjectFile.FileType.TEXT,
                title=title or "Untitled",
                description=_read_synopsis(docs_dir, item_id),
                notes=_read_notes(docs_dir, item_id),
                content=_read_content(docs_dir, item_id),
                target_word_count=_get_target_word_count(item),
                label_id=label_id, status_id=status_id, order=order,
            )
            order += 1
    return order


def _import_world_building(children_el, project, docs_dir, file_type, folder):
    """Import children of a world-building folder as ProjectFiles."""
    if children_el is None:
        return
    order = 0
    for item in children_el.findall("BinderItem"):
        item_id = item.get("ID", "")
        title_el = item.find("Title")
        title = title_el.text if title_el is not None and title_el.text else "Untitled"
        ProjectFile.objects.create(
            project=project, folder=folder, file_type=file_type,
            title=title,
            description=_read_synopsis(docs_dir, item_id),
            notes=_read_notes(docs_dir, item_id),
            content=_read_content(docs_dir, item_id),
            target_word_count=_get_target_word_count(item),
            order=order,
        )
        order += 1


def import_scrivener_zip(zip_file, user):
    """Import a Scrivener .scriv.zip file and return the created Project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "upload.zip")
        with open(zip_path, "wb") as f:
            for chunk in zip_file.chunks():
                f.write(chunk)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

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

        project_title = os.path.splitext(os.path.basename(scrivx_path))[0]
        project = Project.objects.create(owner=user, title=project_title)

        # Parse and create labels
        scriv_labels = _parse_label_settings(root_el)
        label_map = {}
        for i, sl in enumerate(scriv_labels):
            lbl = Label.objects.create(project=project, name=sl["name"], colour=sl["colour"], order=i)
            label_map[sl["scriv_id"]] = lbl.pk

        # Parse and create statuses
        scriv_statuses = _parse_status_settings(root_el)
        status_map = {}
        for i, ss in enumerate(scriv_statuses):
            st = Status.objects.create(project=project, name=ss["name"], colour="", order=i)
            status_map[ss["scriv_id"]] = st.pk

        root_order = 0
        trash_folder = None

        for item in binder.findall("BinderItem"):
            item_type = item.get("Type", "")
            children_el = item.find("Children")

            if item_type == "DraftFolder":
                manuscript_folder = Folder.objects.create(project=project, title=_("Manuscript"), icon="📖", order=root_order)
                root_order += 1
                _import_binder_children(children_el, project, docs_dir, manuscript_folder, 0, label_map, status_map)

            elif item_type == "TrashFolder":
                trash_folder = Folder.objects.create(project=project, title=_("Trash"), icon="🗑️", is_trash=True, order=root_order)
                root_order += 1
                _import_binder_children(children_el, project, docs_dir, trash_folder, 0, label_map, status_map)

            elif item_type == "Folder":
                title_el = item.find("Title")
                title = (title_el.text if title_el is not None else "").lower()
                raw_title = title_el.text if title_el is not None and title_el.text else "Untitled"
                if "character" in title:
                    char_folder = Folder.objects.create(project=project, title=_("Characters"), icon="👥", order=root_order)
                    root_order += 1
                    _import_world_building(children_el, project, docs_dir, ProjectFile.FileType.CHARACTER, char_folder)
                elif "place" in title or "location" in title:
                    loc_folder = Folder.objects.create(project=project, title=_("Locations"), icon="🌎", order=root_order)
                    root_order += 1
                    _import_world_building(children_el, project, docs_dir, ProjectFile.FileType.LOCATION, loc_folder)
                else:
                    item_id = item.get("ID", "")
                    folder = Folder.objects.create(
                        project=project, title=raw_title,
                        description=_read_synopsis(docs_dir, item_id),
                        notes=_read_notes(docs_dir, item_id), order=root_order,
                    )
                    root_order += 1
                    _import_binder_children(children_el, project, docs_dir, folder, 0, label_map, status_map)

            elif item_type in ("ResearchFolder", "TemplateSheetFolder"):
                title_el = item.find("Title")
                raw_title = title_el.text if title_el is not None and title_el.text else item_type
                item_id = item.get("ID", "")
                folder = Folder.objects.create(
                    project=project, title=raw_title,
                    description=_read_synopsis(docs_dir, item_id),
                    notes=_read_notes(docs_dir, item_id), order=root_order,
                )
                root_order += 1
                _import_binder_children(children_el, project, docs_dir, folder, 0, label_map, status_map)

            else:
                title_el = item.find("Title")
                raw_title = title_el.text if title_el is not None and title_el.text else item_type or "Untitled"
                item_id = item.get("ID", "")
                folder = Folder.objects.create(
                    project=project, title=raw_title,
                    description=_read_synopsis(docs_dir, item_id),
                    notes=_read_notes(docs_dir, item_id), order=root_order,
                )
                root_order += 1
                _import_binder_children(children_el, project, docs_dir, folder, 0, label_map, status_map)

        if trash_folder is None:
            Folder.objects.create(project=project, title=_("Trash"), icon="🗑️", is_trash=True, order=root_order)

    return project

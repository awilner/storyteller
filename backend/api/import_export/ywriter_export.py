"""yWriter7 project (.yw7) exporter."""

import xml.etree.ElementTree as ET

from ..models import ProjectFile
from .ywriter_common import markdown_to_bbcode


def _add_cdata_element(parent, tag, text):
    """Add a child element with text content."""
    el = ET.SubElement(parent, tag)
    el.text = text or ""
    return el


def export_ywriter(project):
    """Export a project as a .yw7 XML file. Returns bytes."""
    root = ET.Element("YWRITER7")

    proj_el = ET.SubElement(root, "PROJECT")
    _add_cdata_element(proj_el, "Title", project.title)
    _add_cdata_element(proj_el, "Desc", project.description)

    # Classify root folders
    root_folders = list(project.folders.filter(parent__isnull=True).order_by("order"))
    manuscript_folder = None
    char_folders, loc_folders, item_folders, note_folders, other_folders = [], [], [], [], []

    for f in root_folders:
        if f.is_trash:
            continue
        child_types = set(f.texts.values_list("file_type", flat=True))
        for desc in f.children.all():
            child_types.update(desc.texts.values_list("file_type", flat=True))

        if child_types == {"character"} or (not child_types and "character" in f.title.lower()):
            char_folders.append(f)
        elif child_types == {"location"} or (not child_types and "location" in f.title.lower()):
            loc_folders.append(f)
        elif child_types == {"item"} or (not child_types and "item" in f.title.lower()):
            item_folders.append(f)
        elif child_types == {"note"} or (not child_types and "note" in f.title.lower()):
            note_folders.append(f)
        elif child_types <= {"text", ""} or "manuscript" in f.title.lower():
            if manuscript_folder is None:
                manuscript_folder = f
            else:
                other_folders.append(f)
        else:
            other_folders.append(f)

    if manuscript_folder is None and other_folders:
        manuscript_folder = other_folders.pop(0)

    # Build chapters and scenes
    scene_id = 0
    chapter_id = 0
    chapters_el = ET.SubElement(root, "CHAPTERS")
    scenes_el = ET.SubElement(root, "SCENES")

    def _export_folder_as_chapters(folder):
        nonlocal scene_id, chapter_id
        direct_texts = list(folder.texts.order_by("order"))
        child_folders = list(folder.children.order_by("order"))

        if direct_texts:
            chapter_id += 1
            ch_el = ET.SubElement(chapters_el, "CHAPTER")
            _add_cdata_element(ch_el, "ID", str(chapter_id))
            _add_cdata_element(ch_el, "Title", folder.title)
            _add_cdata_element(ch_el, "Desc", folder.description)
            _add_cdata_element(ch_el, "SortOrder", str(chapter_id))
            scenes_container = ET.SubElement(ch_el, "Scenes")
            for text in direct_texts:
                scene_id += 1
                sc_el = ET.SubElement(scenes_el, "SCENE")
                _add_cdata_element(sc_el, "ID", str(scene_id))
                _add_cdata_element(sc_el, "Title", text.title)
                _add_cdata_element(sc_el, "Desc", text.description)
                _add_cdata_element(sc_el, "Notes", text.notes)
                _add_cdata_element(sc_el, "SceneContent", markdown_to_bbcode(text.content))
                ET.SubElement(scenes_container, "ScID").text = str(scene_id)

        for child in child_folders:
            if child.is_trash:
                continue
            chapter_id += 1
            ch_el = ET.SubElement(chapters_el, "CHAPTER")
            _add_cdata_element(ch_el, "ID", str(chapter_id))
            _add_cdata_element(ch_el, "Title", child.title)
            _add_cdata_element(ch_el, "Desc", child.description)
            _add_cdata_element(ch_el, "SortOrder", str(chapter_id))
            scenes_container = ET.SubElement(ch_el, "Scenes")
            for text in child.texts.order_by("order"):
                scene_id += 1
                sc_el = ET.SubElement(scenes_el, "SCENE")
                _add_cdata_element(sc_el, "ID", str(scene_id))
                _add_cdata_element(sc_el, "Title", text.title)
                _add_cdata_element(sc_el, "Desc", text.description)
                _add_cdata_element(sc_el, "Notes", text.notes)
                _add_cdata_element(sc_el, "SceneContent", markdown_to_bbcode(text.content))
                ET.SubElement(scenes_container, "ScID").text = str(scene_id)

    if manuscript_folder:
        _export_folder_as_chapters(manuscript_folder)
    for f in other_folders:
        _export_folder_as_chapters(f)

    # Characters
    chars_el = ET.SubElement(root, "CHARACTERS")
    char_id = 0
    for folder in char_folders:
        for text in folder.texts.order_by("order"):
            char_id += 1
            c_el = ET.SubElement(chars_el, "CHARACTER")
            _add_cdata_element(c_el, "ID", str(char_id))
            _add_cdata_element(c_el, "Title", text.title)
            _add_cdata_element(c_el, "Desc", text.description)
            _add_cdata_element(c_el, "Notes", text.notes)
            _add_cdata_element(c_el, "SortOrder", str(char_id))

    # Locations
    locs_el = ET.SubElement(root, "LOCATIONS")
    loc_id = 0
    for folder in loc_folders:
        for text in folder.texts.order_by("order"):
            loc_id += 1
            l_el = ET.SubElement(locs_el, "LOCATION")
            _add_cdata_element(l_el, "ID", str(loc_id))
            _add_cdata_element(l_el, "Title", text.title)
            _add_cdata_element(l_el, "Desc", text.description)
            _add_cdata_element(l_el, "SortOrder", str(loc_id))

    # Items
    items_el = ET.SubElement(root, "ITEMS")
    item_id = 0
    for folder in item_folders:
        for text in folder.texts.order_by("order"):
            item_id += 1
            i_el = ET.SubElement(items_el, "ITEM")
            _add_cdata_element(i_el, "ID", str(item_id))
            _add_cdata_element(i_el, "Title", text.title)
            _add_cdata_element(i_el, "Desc", text.description)
            _add_cdata_element(i_el, "SortOrder", str(item_id))

    # Notes
    notes_el = ET.SubElement(root, "PROJECTNOTES")
    note_id = 0
    for folder in note_folders:
        for text in folder.texts.order_by("order"):
            note_id += 1
            n_el = ET.SubElement(notes_el, "PROJECTNOTE")
            _add_cdata_element(n_el, "ID", str(note_id))
            _add_cdata_element(n_el, "Title", text.title)
            _add_cdata_element(n_el, "Desc", text.description)
            _add_cdata_element(n_el, "SortOrder", str(note_id))

    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes).encode("utf-8")

"""
Project exporters for Scrivener (.scriv.zip) and yWriter7 (.yw7) formats.

Each exporter takes a Project instance and returns bytes suitable for
streaming as an HTTP response.
"""

import io
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .models import Folder, ProjectFile
from .models import Label, Status


# ── Helpers ───────────────────────────────────────────────────

def _hex_to_scriv_colour(hex_str):
    """Convert hex colour (e.g. '#F3EA54') to Scrivener RGB float string."""
    if not hex_str or len(hex_str) < 7:
        return ""
    try:
        r = int(hex_str[1:3], 16) / 255.0
        g = int(hex_str[3:5], 16) / 255.0
        b = int(hex_str[5:7], 16) / 255.0
        return f"{r:.6f} {g:.6f} {b:.6f}"
    except (ValueError, IndexError):
        return ""


def _markdown_to_bbcode(text):
    """Convert markdown inline formatting back to yWriter BBCode.

    Handles bold (**), italic (*), and strikethrough (~~).
    Also converts double newlines back to single newlines (yWriter paragraphs).
    """
    # Bold before italic (** before *)
    text = re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/b]", text, flags=re.DOTALL)
    text = re.sub(r"\*(.+?)\*", r"[i]\1[/i]", text, flags=re.DOTALL)
    text = re.sub(r"~~(.+?)~~", r"[s]\1[/s]", text, flags=re.DOTALL)
    # Double newlines -> single newline (yWriter paragraph separator)
    text = re.sub(r"\n\n+", "\n", text)
    return text


def _collect_folders_recursive(folder):
    """Yield (folder, depth) for a folder and all its descendants, depth-first."""
    yield folder
    for child in folder.children.order_by("order"):
        yield from _collect_folders_recursive(child)


# ── yWriter7 export ──────────────────────────────────────────

def _add_cdata_element(parent, tag, text):
    """Add a child element with text content (will be CDATA in output)."""
    el = ET.SubElement(parent, tag)
    el.text = text or ""
    return el


def export_ywriter(project):
    """Export a project as a .yw7 XML file. Returns bytes."""
    root = ET.Element("YWRITER7")

    # PROJECT
    proj_el = ET.SubElement(root, "PROJECT")
    _add_cdata_element(proj_el, "Title", project.title)
    _add_cdata_element(proj_el, "Desc", project.description)

    # Collect all data
    root_folders = list(project.folders.filter(parent__isnull=True).order_by("order"))
    manuscript_folder = None
    char_folders = []
    loc_folders = []
    item_folders = []
    note_folders = []
    other_folders = []

    for f in root_folders:
        if f.is_trash:
            continue
        # Identify by content type of children, or by icon/title heuristics
        child_types = set(
            f.texts.values_list("file_type", flat=True)
        )
        # Also check nested folders
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

    # If no manuscript identified, treat first folder with text children as manuscript
    if manuscript_folder is None and other_folders:
        manuscript_folder = other_folders.pop(0)

    # Build scenes and chapters
    scene_id = 0
    chapter_id = 0
    chapters_el = ET.SubElement(root, "CHAPTERS")
    scenes_el = ET.SubElement(root, "SCENES")

    def _export_folder_as_chapters(folder):
        """Export a folder's children as chapters with scenes."""
        nonlocal scene_id, chapter_id
        # Each child folder becomes a chapter; direct texts become scenes in a chapter
        direct_texts = list(folder.texts.order_by("order"))
        child_folders = list(folder.children.order_by("order"))

        # If folder has direct texts, wrap them in a chapter
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
                _add_cdata_element(sc_el, "SceneContent",
                                   _markdown_to_bbcode(text.content))
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
                _add_cdata_element(sc_el, "SceneContent",
                                   _markdown_to_bbcode(text.content))
                ET.SubElement(scenes_container, "ScID").text = str(scene_id)

    if manuscript_folder:
        _export_folder_as_chapters(manuscript_folder)

    # Also export "other" folders as additional chapters
    for f in other_folders:
        _export_folder_as_chapters(f)

    # CHARACTERS
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

    # LOCATIONS
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

    # ITEMS
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

    # PROJECTNOTES
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


# ── Scrivener export ─────────────────────────────────────────

def _next_binder_id():
    """Generate a unique integer ID for binder items."""
    if not hasattr(_next_binder_id, "_counter"):
        _next_binder_id._counter = 0
    _next_binder_id._counter += 1
    return _next_binder_id._counter


def _reset_binder_ids():
    """Reset the binder ID counter (for testing)."""
    _next_binder_id._counter = 0


def _build_binder_item(item_type, title, children_elements=None, item_id=None, label_id=None, status_id=None):
    """Build a <BinderItem> element."""
    bid = item_id or _next_binder_id()
    el = ET.Element("BinderItem", Type=item_type, ID=str(bid))
    title_el = ET.SubElement(el, "Title")
    title_el.text = title
    if label_id is not None or status_id is not None:
        meta = ET.SubElement(el, "MetaData")
        if label_id is not None:
            lid = ET.SubElement(meta, "LabelID")
            lid.text = str(label_id)
        if status_id is not None:
            sid = ET.SubElement(meta, "StatusID")
            sid.text = str(status_id)
    if children_elements:
        children_el = ET.SubElement(el, "Children")
        for child in children_elements:
            children_el.append(child)
    return el, bid


def _folder_to_binder(folder, docs, is_draft=False, label_id_map=None, status_id_map=None):
    """Recursively convert a Folder to BinderItem elements."""
    if label_id_map is None:
        label_id_map = {}
    if status_id_map is None:
        status_id_map = {}
    items = []

    child_folders = list(folder.children.order_by("order"))
    child_texts = list(folder.texts.order_by("order"))

    combined = []
    for cf in child_folders:
        if cf.is_trash:
            continue
        combined.append(("folder", cf))
    for ct in child_texts:
        combined.append(("text", ct))
    combined.sort(key=lambda x: x[1].order)

    for kind, obj in combined:
        if kind == "folder":
            sub_items = _folder_to_binder(obj, docs, is_draft=is_draft, label_id_map=label_id_map, status_id_map=status_id_map)
            scriv_label = label_id_map.get(obj.label_id)
            scriv_status = status_id_map.get(obj.status_id)
            el, bid = _build_binder_item("Folder", obj.title, sub_items, label_id=scriv_label, status_id=scriv_status)
            if obj.description:
                docs[f"{bid}_synopsis"] = obj.description
            if obj.notes:
                docs[f"{bid}_notes"] = obj.notes
            items.append(el)
        else:
            scriv_label = label_id_map.get(obj.label_id)
            scriv_status = status_id_map.get(obj.status_id)
            el, bid = _build_binder_item("Text", obj.title, label_id=scriv_label, status_id=scriv_status)
            docs[str(bid)] = obj.content
            if obj.description:
                docs[f"{bid}_synopsis"] = obj.description
            if obj.notes:
                docs[f"{bid}_notes"] = obj.notes
            if obj.target_word_count:
                ts = ET.SubElement(el, "TextSettings")
                target = ET.SubElement(ts, "Target", Type="Words")
                target.text = str(obj.target_word_count)
            items.append(el)

    return items


def export_scrivener(project):
    """Export a project as a Scrivener .scriv.zip file. Returns bytes."""
    _reset_binder_ids()

    root_el = ET.Element("ScrivenerProject")
    binder = ET.SubElement(root_el, "Binder")
    docs = {}

    # Build label/status ID maps: db pk -> scrivener integer ID
    labels = list(Label.objects.filter(project=project).order_by("order"))
    statuses = list(Status.objects.filter(project=project).order_by("order"))
    label_id_map = {}  # db label pk -> scriv ID
    status_id_map = {}  # db status pk -> scriv ID
    for i, lbl in enumerate(labels):
        label_id_map[lbl.pk] = i + 1
    for i, st in enumerate(statuses):
        status_id_map[st.pk] = i + 1

    root_folders = list(project.folders.filter(parent__isnull=True).order_by("order"))

    for folder in root_folders:
        if folder.is_trash:
            trash_items = _folder_to_binder(folder, docs, is_draft=True, label_id_map=label_id_map, status_id_map=status_id_map)
            el, _ = _build_binder_item("TrashFolder", folder.title, trash_items)
            binder.append(el)
            continue

        child_types = set(folder.texts.values_list("file_type", flat=True))
        for desc in folder.children.all():
            child_types.update(desc.texts.values_list("file_type", flat=True))

        if child_types <= {"text", ""} or "manuscript" in folder.title.lower():
            draft_items = _folder_to_binder(folder, docs, is_draft=True, label_id_map=label_id_map, status_id_map=status_id_map)
            el, _ = _build_binder_item("DraftFolder", folder.title, draft_items)
            binder.append(el)
        elif child_types == {"character"}:
            items = _folder_to_binder(folder, docs, is_draft=False, label_id_map=label_id_map, status_id_map=status_id_map)
            el, _ = _build_binder_item("Folder", folder.title, items)
            binder.append(el)
        elif child_types == {"location"}:
            items = _folder_to_binder(folder, docs, is_draft=False, label_id_map=label_id_map, status_id_map=status_id_map)
            el, _ = _build_binder_item("Folder", folder.title, items)
            binder.append(el)
        else:
            items = _folder_to_binder(folder, docs, is_draft=True, label_id_map=label_id_map, status_id_map=status_id_map)
            el, _ = _build_binder_item("Folder", folder.title, items)
            binder.append(el)

    # Write <LabelSettings>
    ls_el = ET.SubElement(root_el, "LabelSettings")
    ls_title = ET.SubElement(ls_el, "Title")
    ls_title.text = "Label"
    ls_default = ET.SubElement(ls_el, "DefaultLabelID")
    ls_default.text = "-1"
    labels_list = ET.SubElement(ls_el, "Labels")
    no_label = ET.SubElement(labels_list, "Label", ID="-1")
    no_label.text = "No Label"
    for lbl in labels:
        scriv_id = label_id_map[lbl.pk]
        attrs = {"ID": str(scriv_id)}
        if lbl.colour:
            scriv_colour = _hex_to_scriv_colour(lbl.colour)
            if scriv_colour:
                attrs["Color"] = scriv_colour
        lbl_el = ET.SubElement(labels_list, "Label", **attrs)
        lbl_el.text = lbl.name

    # Write <StatusSettings>
    ss_el = ET.SubElement(root_el, "StatusSettings")
    ss_title = ET.SubElement(ss_el, "Title")
    ss_title.text = "Status"
    ss_default = ET.SubElement(ss_el, "DefaultStatusID")
    ss_default.text = "-1"
    status_items = ET.SubElement(ss_el, "StatusItems")
    no_status = ET.SubElement(status_items, "Status", ID="-1")
    no_status.text = "No Status"
    for st in statuses:
        scriv_id = status_id_map[st.pk]
        st_el = ET.SubElement(status_items, "Status", ID=str(scriv_id))
        st_el.text = st.name

    # Build the XML
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root_el, encoding="unicode"
    )

    # Build the zip
    safe_title = re.sub(r'[^\w\s-]', '', project.title).strip() or "Project"
    scriv_dir = f"{safe_title}.scriv"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{scriv_dir}/{safe_title}.scrivx", xml_str)
        for doc_id, content in docs.items():
            if doc_id.endswith("_synopsis"):
                base_id = doc_id.replace("_synopsis", "")
                zf.writestr(
                    f"{scriv_dir}/Files/Docs/{base_id}_synopsis.txt",
                    content,
                )
            elif doc_id.endswith("_notes"):
                base_id = doc_id.replace("_notes", "")
                zf.writestr(
                    f"{scriv_dir}/Files/Docs/{base_id}_notes.rtf",
                    content,
                )
            else:
                zf.writestr(
                    f"{scriv_dir}/Files/Docs/{doc_id}.md",
                    content,
                )

    return buf.getvalue()

"""Scrivener project (.scriv.zip) exporter."""

import io
import re
import xml.etree.ElementTree as ET
import zipfile

from ..models import Label, ProjectFile, Status
from .scrivener_common import hex_to_scriv_colour


def _next_binder_id():
    """Generate a unique integer ID for binder items."""
    if not hasattr(_next_binder_id, "_counter"):
        _next_binder_id._counter = 0
    _next_binder_id._counter += 1
    return _next_binder_id._counter


def _reset_binder_ids():
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
            ET.SubElement(meta, "LabelID").text = str(label_id)
        if status_id is not None:
            ET.SubElement(meta, "StatusID").text = str(status_id)
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

    combined = []
    for cf in folder.children.order_by("order"):
        if not cf.is_trash:
            combined.append(("folder", cf))
    for ct in folder.texts.order_by("order"):
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

    labels = list(Label.objects.filter(project=project).order_by("order"))
    statuses = list(Status.objects.filter(project=project).order_by("order"))
    label_id_map = {lbl.pk: i + 1 for i, lbl in enumerate(labels)}
    status_id_map = {st.pk: i + 1 for i, st in enumerate(statuses)}

    for folder in project.folders.filter(parent__isnull=True).order_by("order"):
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
        elif child_types == {"character"}:
            items = _folder_to_binder(folder, docs, is_draft=False, label_id_map=label_id_map, status_id_map=status_id_map)
            el, _ = _build_binder_item("Folder", folder.title, items)
        elif child_types == {"location"}:
            items = _folder_to_binder(folder, docs, is_draft=False, label_id_map=label_id_map, status_id_map=status_id_map)
            el, _ = _build_binder_item("Folder", folder.title, items)
        else:
            items = _folder_to_binder(folder, docs, is_draft=True, label_id_map=label_id_map, status_id_map=status_id_map)
            el, _ = _build_binder_item("Folder", folder.title, items)
        binder.append(el)

    # <LabelSettings>
    ls_el = ET.SubElement(root_el, "LabelSettings")
    ET.SubElement(ls_el, "Title").text = "Label"
    ET.SubElement(ls_el, "DefaultLabelID").text = "-1"
    labels_list = ET.SubElement(ls_el, "Labels")
    ET.SubElement(labels_list, "Label", ID="-1").text = "No Label"
    for lbl in labels:
        attrs = {"ID": str(label_id_map[lbl.pk])}
        if lbl.colour:
            scriv_colour = hex_to_scriv_colour(lbl.colour)
            if scriv_colour:
                attrs["Color"] = scriv_colour
        ET.SubElement(labels_list, "Label", **attrs).text = lbl.name

    # <StatusSettings>
    ss_el = ET.SubElement(root_el, "StatusSettings")
    ET.SubElement(ss_el, "Title").text = "Status"
    ET.SubElement(ss_el, "DefaultStatusID").text = "-1"
    status_items = ET.SubElement(ss_el, "StatusItems")
    ET.SubElement(status_items, "Status", ID="-1").text = "No Status"
    for st in statuses:
        ET.SubElement(status_items, "Status", ID=str(status_id_map[st.pk])).text = st.name

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root_el, encoding="unicode")

    safe_title = re.sub(r'[^\w\s-]', '', project.title).strip() or "Project"
    scriv_dir = f"{safe_title}.scriv"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{scriv_dir}/{safe_title}.scrivx", xml_str)
        for doc_id, content in docs.items():
            if doc_id.endswith("_synopsis"):
                base_id = doc_id.replace("_synopsis", "")
                zf.writestr(f"{scriv_dir}/Files/Docs/{base_id}_synopsis.txt", content)
            elif doc_id.endswith("_notes"):
                base_id = doc_id.replace("_notes", "")
                zf.writestr(f"{scriv_dir}/Files/Docs/{base_id}_notes.rtf", content)
            else:
                zf.writestr(f"{scriv_dir}/Files/Docs/{doc_id}.md", content)

    return buf.getvalue()

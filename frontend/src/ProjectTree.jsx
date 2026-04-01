import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Tree } from "react-arborist";
import { useI18n } from "./I18nContext";

/* ── Default icons ─────────────────────────────────────────── */

const DEFAULT_FOLDER_ICON = "📁";
const DEFAULT_TEXT_ICON = "📄";

/* ── Transform backend tree → arborist nodes ───────────────── */

/**
 * Transform backend tree → arborist nodes.
 * @param {object} tree - The project tree from the API.
 * @param {string} filter - "manuscript" (folders/texts only), "characters", "locations", "notes", or "all".
 */
function toArboristNodes(tree, filter = "all") {
  if (!tree) return [];

  const mapFolder = (folder) => {
    const items = [];
    for (const child of folder.children || []) {
      items.push({ ...child, _kind: "folder" });
    }
    for (const text of folder.texts || []) {
      items.push({ ...text, _kind: "text" });
    }
    items.sort((a, b) => a.order - b.order);

    const children = items.map((item) =>
      item._kind === "folder"
        ? mapFolder(item)
        : { id: `text-${item.id}`, name: item.title, _type: "text", _dbId: item.id, _icon: item.icon || "", _data: item }
    );

    return {
      id: `folder-${folder.id}`,
      name: folder.title,
      children,
      _type: "folder",
      _dbId: folder.id,
      _icon: folder.icon || "",
      _data: folder,
    };
  };

  // Manuscript folders
  if (filter === "manuscript" || filter === "all") {
    const topItems = [];
    for (const folder of tree.folders || []) {
      topItems.push({ ...folder, _kind: "folder" });
    }
    topItems.sort((a, b) => a.order - b.order);
    const nodes = topItems.map((item) => mapFolder(item));

    if (filter === "manuscript") return nodes;

    // "all" — append world-building groups
    const wb = tree.world_building || {};
    for (const [key, items] of Object.entries(wb)) {
      if (!items?.length) continue;
      nodes.push({
        id: `wb-${key}`,
        name: key.charAt(0).toUpperCase() + key.slice(1),
        _type: "wb-group",
        children: items.slice().sort((a, b) => a.order - b.order).map((f) => ({
          id: `wb-file-${f.id}`,
          name: f.title,
          _type: "wb-file",
          _dbId: f.id,
          _icon: f.icon || "",
          _data: f,
        })),
      });
    }
    return nodes;
  }

  // World-building filter: "characters", "locations", or "notes"
  const wb = tree.world_building || {};
  const items = wb[filter] || [];
  return items.slice().sort((a, b) => a.order - b.order).map((f) => ({
    id: `wb-file-${f.id}`,
    name: f.title,
    _type: "wb-file",
    _dbId: f.id,
    _icon: f.icon || "",
    _data: f,
  }));
}

/* ── Context menu ──────────────────────────────────────────── */

function ContextMenu({ x, y, items, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onClick); document.removeEventListener("keydown", onKey); };
  }, [onClose]);
  const left = Math.min(x, window.innerWidth - 200);
  const top = Math.min(y, window.innerHeight - items.length * 32 - 16);
  return (
    <div ref={ref} style={{ ...menuStyles.menu, left, top, position: "fixed" }} role="menu" aria-label="Context menu">
      {items.map((item, i) =>
        item.separator ? (
          <div key={`sep-${i}`} style={menuStyles.sep} />
        ) : (
          <button key={item.label} role="menuitem"
            style={{ ...menuStyles.item, color: item.danger ? "#c44" : "#222" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "#f0f0f0"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
            onClick={() => { item.action(); onClose(); }}>
            {item.label}
          </button>
        )
      )}
    </div>
  );
}

const menuStyles = {
  menu: { position: "fixed", zIndex: 1000, background: "#fff", border: "1px solid #ccc", borderRadius: 6, boxShadow: "0 4px 16px rgba(0,0,0,.15)", padding: "4px 0", minWidth: 160, fontSize: 13, fontFamily: "system-ui" },
  item: { padding: "6px 14px", cursor: "pointer", display: "block", width: "100%", border: "none", background: "none", textAlign: "left", fontSize: 13, fontFamily: "inherit" },
  sep: { height: 1, background: "#e5e5e5", margin: "4px 0" },
};

/* ── Icon picker ────────────────────────────────────────────── */

const ICON_CHOICES = [
  "📁", "📂", "🗂️", "📄", "📝", "📃", "📜", "📖", "📕", "📗", "📘", "📙",
  "✏️", "🖊️", "🖋️", "📎", "📌", "🔖", "🏷️", "💡", "⭐", "🌟", "❤️", "💎",
  "🔥", "🌈", "🌍", "🏠", "🏰", "⚔️", "🛡️", "👤", "👥", "🐉", "🦅", "🐺",
  "🌲", "🌊", "🗻", "🌙", "☀️", "⚡", "🎭", "🎵", "🔮", "🗝️", "🧭", "🗺️",
];

function IconPicker({ x, y, currentIcon, onSelect, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onClick); document.removeEventListener("keydown", onKey); };
  }, [onClose]);
  const left = Math.min(x, window.innerWidth - 260);
  const top = Math.min(y, window.innerHeight - 300);
  return (
    <div ref={ref} style={{ position: "fixed", left, top, zIndex: 1001, background: "#fff", border: "1px solid #ccc", borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,.18)", padding: 8, width: 240 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 2 }}>
        {ICON_CHOICES.map((emoji) => (
          <button key={emoji} type="button" onClick={() => { onSelect(emoji); onClose(); }}
            style={{ fontSize: 18, padding: 4, border: emoji === currentIcon ? "2px solid #4a90d9" : "2px solid transparent", borderRadius: 6, background: "none", cursor: "pointer", lineHeight: 1 }}
            aria-label={emoji}>
            {emoji}
          </button>
        ))}
      </div>
      {currentIcon && (
        <button type="button" onClick={() => { onSelect(""); onClose(); }}
          style={{ marginTop: 6, width: "100%", padding: "4px 0", fontSize: 12, border: "1px solid #ddd", borderRadius: 4, background: "#f8f8f8", cursor: "pointer", color: "#666" }}>
          ↩ Revert to default
        </button>
      )}
    </div>
  );
}

/* ── Custom node renderer ──────────────────────────────────── */

const iconStyle = { marginRight: 4, fontSize: "0.85rem", flexShrink: 0 };
const nameStyle = { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 };

function Node({ node, style, dragHandle }) {
  const data = node.data;
  const isWbGroup = data._type === "wb-group";
  const isFolder = data._type === "folder";
  const isWbFile = data._type === "wb-file";

  if (isWbGroup) {
    return (
      <div data-row-index={node.rowIndex} style={{ ...style, display: "flex", alignItems: "center", cursor: "pointer", fontWeight: 600, fontSize: "0.9rem", userSelect: "none" }}
        onClick={() => node.toggle()}>
        <span style={{ width: "1em", textAlign: "center", marginRight: 4, fontSize: "0.7rem" }}>
          {node.isOpen ? "▼" : "▶"}
        </span>
        <span style={{ textTransform: "capitalize", ...nameStyle }} title={data.name}>{data.name}</span>
      </div>
    );
  }

  if (isFolder) {
    const icon = data._icon || DEFAULT_FOLDER_ICON;
    return (
      <div ref={dragHandle} data-row-index={node.rowIndex} style={{ ...style, display: "flex", alignItems: "center", cursor: "pointer", fontWeight: 600, fontSize: "0.9rem", userSelect: "none",
        backgroundColor: node.willReceiveDrop ? "#d8e8ff" : node.isSelected ? "#e8e8ff" : "transparent", borderRadius: 4 }}>
        <span style={{ width: "1em", textAlign: "center", marginRight: 4, fontSize: "0.7rem", flexShrink: 0 }}
          onClick={(e) => { e.stopPropagation(); node.toggle(); }}>
          {node.isOpen ? "▼" : "▶"}
        </span>
        <span style={iconStyle} onClick={() => node.activate()}>{icon}</span>
        {node.isEditing ? (
          <input autoFocus type="text" defaultValue={data.name} style={{ flex: 1, fontSize: 13, padding: "1px 4px", border: "1px solid #ccc", borderRadius: 3 }}
            onBlur={(e) => node.submit(e.currentTarget.value)}
            onKeyDown={(e) => { if (e.key === "Enter") node.submit(e.currentTarget.value); if (e.key === "Escape") node.reset(); }} />
        ) : (
          <span style={nameStyle} title={data.name} onClick={() => node.activate()}>{data.name}</span>
        )}
      </div>
    );
  }

  // Text or world-building file
  const icon = data._icon || DEFAULT_TEXT_ICON;
  return (
    <div ref={isWbFile ? undefined : dragHandle} data-row-index={node.rowIndex}
      style={{ ...style, display: "flex", alignItems: "center", cursor: "pointer", borderRadius: 4, fontSize: "0.9rem",
        backgroundColor: node.isSelected ? "#d0e4ff" : "transparent",
        fontWeight: node.isSelected ? 600 : 400 }}>
      <span style={iconStyle}>{icon}</span>
      {node.isEditing ? (
        <input autoFocus type="text" defaultValue={data.name} style={{ flex: 1, fontSize: 13, padding: "1px 4px", border: "1px solid #ccc", borderRadius: 3 }}
          onBlur={(e) => node.submit(e.currentTarget.value)}
          onKeyDown={(e) => { if (e.key === "Enter") node.submit(e.currentTarget.value); if (e.key === "Escape") node.reset(); }} />
      ) : (
        <span style={nameStyle} title={data.name}>{data.name}</span>
      )}
    </div>
  );
}

/* ── Main component ────────────────────────────────────────── */

export default function ProjectTree({ tree, onSelectFile, activeFileId, selectedFolderId, onSelectFolder, onAddFolder, onDeleteFolder, onAddText, onDeleteText, onReorder, onRenameFolder, onRenameText, onChangeFolderIcon, onChangeTextIcon, treeFilter }) {
  const t = useI18n();
  const [menu, setMenu] = useState(null);
  const [iconPicker, setIconPicker] = useState(null);
  const treeRef = useRef(null);
  const containerRef = useRef(null);
  const [treeHeight, setTreeHeight] = useState(600);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      setTreeHeight(entry.contentRect.height);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const arboristData = useMemo(() => toArboristNodes(tree, treeFilter || "all"), [tree, treeFilter]);

  const selection = useMemo(() => {
    if (activeFileId) return `text-${activeFileId}`;
    if (selectedFolderId) return `folder-${selectedFolderId}`;
    return undefined;
  }, [activeFileId, selectedFolderId]);

  const handleActivate = useCallback((node) => {
    const d = node.data;
    if (d._type === "text" || d._type === "wb-file") {
      onSelectFile(d._dbId);
    } else if (d._type === "folder") {
      if (onSelectFolder) onSelectFolder(d._dbId);
    }
  }, [onSelectFile, onSelectFolder]);

  const handleMove = useCallback(({ dragIds, parentId, index }) => {
    if (!onReorder) return;
    let childIds;
    if (parentId && treeRef.current) {
      const parentNode = treeRef.current.get(parentId);
      childIds = parentNode ? parentNode.children.map((c) => c.id) : [];
    } else {
      childIds = arboristData.map((n) => n.id);
    }
    const dragSet = new Set(dragIds);
    const remaining = childIds.filter((id) => !dragSet.has(id));
    remaining.splice(index, 0, ...dragIds);

    const folderUpdates = [];
    const textUpdates = [];
    const parentDbId = parentId && parentId.startsWith("folder-")
      ? parseInt(parentId.split("-").pop(), 10)
      : null;

    remaining.forEach((cid, i) => {
      if (cid.startsWith("folder-")) {
        const dbId = parseInt(cid.split("-").pop(), 10);
        folderUpdates.push({ id: dbId, order: i, parent: parentDbId });
      } else if (cid.startsWith("text-")) {
        const dbId = parseInt(cid.split("-").pop(), 10);
        if (parentDbId != null) {
          textUpdates.push({ id: dbId, order: i, folder: parentDbId });
        }
      }
    });

    if (folderUpdates.length || textUpdates.length) {
      onReorder(folderUpdates, textUpdates);
    }
  }, [onReorder, arboristData]);

  const disableDrop = useCallback(({ parentNode, dragNodes }) => {
    if (!parentNode || parentNode.isRoot) {
      if (dragNodes.some((n) => n.data._type !== "folder")) return true;
      return false;
    }
    const pType = parentNode.data?._type;
    if (pType === "wb-group" || pType === "wb-file") return true;
    if (pType === "text") return true;
    if (dragNodes.some((n) => n.data._type === "wb-file" || n.data._type === "wb-group")) return true;
    return false;
  }, []);

  const disableDrag = useCallback((data) => {
    const dtype = data._type;
    return dtype === "wb-group" || dtype === "wb-file";
  }, []);

  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    let node = null;
    if (treeRef.current) {
      let el = e.target;
      while (el && el !== containerRef.current) {
        const dri = el.getAttribute("data-row-index");
        if (dri != null) {
          node = treeRef.current.at(parseInt(dri, 10));
          break;
        }
        el = el.parentElement;
      }
    }

    const items = [];
    if (node) {
      const d = node.data;
      if (d._type === "folder") {
        if (onAddText) items.push({ label: t("tree.new_text"), action: () => { node.open(); const title = window.prompt(t("tree.text_title_prompt")); if (title?.trim()) onAddText(d._dbId, title.trim()); } });
        if (onAddFolder) items.push({ label: t("tree.new_subfolder"), action: () => { node.open(); const title = window.prompt(t("tree.folder_title_prompt")); if (title?.trim()) onAddFolder(d._dbId, title.trim()); } });
        items.push({ label: t("tree.rename"), action: () => node.edit() });
        if (onChangeFolderIcon) {
          items.push({ separator: true });
          items.push({ label: t("tree.change_icon"), action: () => { setIconPicker({ x: e.clientX, y: e.clientY, currentIcon: d._icon, onSelect: (icon) => onChangeFolderIcon(d._dbId, icon) }); } });
        }
        if (onDeleteFolder) { items.push({ separator: true }); items.push({ label: t("tree.delete_folder"), danger: true, action: () => onDeleteFolder(d._dbId, d.name) }); }
      } else if (d._type === "text") {
        items.push({ label: t("tree.rename"), action: () => node.edit() });
        if (onChangeTextIcon) {
          items.push({ separator: true });
          items.push({ label: t("tree.change_icon"), action: () => { setIconPicker({ x: e.clientX, y: e.clientY, currentIcon: d._icon, onSelect: (icon) => onChangeTextIcon(d._dbId, icon) }); } });
        }
        if (onDeleteText) { items.push({ separator: true }); items.push({ label: t("tree.delete_text"), danger: true, action: () => onDeleteText(d._dbId, d.name) }); }
      }
    } else {
      if (onAddFolder) items.push({ label: t("tree.new_folder"), action: () => onAddFolder(null) });
    }

    if (items.length) setMenu({ x: e.clientX, y: e.clientY, items });
  }, [t, onAddText, onAddFolder, onDeleteFolder, onDeleteText, onChangeFolderIcon, onChangeTextIcon]);

  const handleRename = useCallback(({ id, name }) => {
    if (!name?.trim()) return;
    const isFolder = id.startsWith("folder-");
    const isText = id.startsWith("text-");
    const dbId = parseInt(id.split("-").pop(), 10);
    if (isFolder && onRenameFolder) onRenameFolder(dbId, name.trim());
    if (isText && onRenameText) onRenameText(dbId, name.trim());
  }, [onRenameFolder, onRenameText]);

  if (!tree) return null;

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", fontFamily: "system-ui" }} onContextMenu={handleContextMenu}>
      <div style={{ paddingLeft: "0.75rem", paddingRight: "0.75rem", paddingTop: "0.5rem" }}>
      <Tree
        ref={treeRef}
        data={arboristData}
        selection={selection}
        onActivate={handleActivate}
        onMove={handleMove}
        onRename={handleRename}
        disableDrop={disableDrop}
        disableDrag={disableDrag}
        openByDefault
        width="100%"
        height={treeHeight - 40}
        indent={16}
        rowHeight={28}
        disableMultiSelection
      >
        {Node}
      </Tree>
      </div>
      {menu && <ContextMenu x={menu.x} y={menu.y} items={menu.items} onClose={() => setMenu(null)} />}
      {iconPicker && <IconPicker x={iconPicker.x} y={iconPicker.y} currentIcon={iconPicker.currentIcon} onSelect={iconPicker.onSelect} onClose={() => setIconPicker(null)} />}
    </div>
  );
}

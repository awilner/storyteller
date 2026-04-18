import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Tree } from "react-arborist";
import { useI18n } from "./I18nContext";

/* ── Default icons ─────────────────────────────────────────── */

const DEFAULT_FOLDER_ICON = "📁";
const DEFAULT_TEXT_ICON = "📄";

const FILE_TYPE_ICONS = {
  text: "📄",
  character: "👤",
  location: "📍",
  note: "📝",
  item: "🔧"
};

/* ── Transform backend tree → arborist nodes ───────────────── */

/**
 * Transform backend tree → arborist nodes.
 * Single unified tree: folders contain items (files of any type).
 */
function toArboristNodes(tree) {
  if (!tree) return [];

  const mapFolder = (folder, insideTrash = false) => {
    const isTrash = !!folder.is_trash;
    const isInsideTrash = insideTrash || isTrash;

    const items = [];
    for (const child of folder.children || []) {
      items.push({ ...child, _kind: "folder" });
    }
    for (const item of folder.items || []) {
      items.push({ ...item, _kind: "text" });
    }
    items.sort((a, b) => a.order - b.order);

    const children = items.map((item) =>
      item._kind === "folder"
        ? mapFolder(item, isInsideTrash)
        : { id: `text-${item.id}`, name: item.title, _type: "text", _dbId: item.id, _icon: item.icon || "", _data: item, _isInsideTrash: isInsideTrash }
    );

    return {
      id: `folder-${folder.id}`,
      name: folder.title,
      children,
      _type: "folder",
      _dbId: folder.id,
      _icon: folder.icon || "",
      _data: folder,
      _isTrash: isTrash,
      _isInsideTrash: isInsideTrash,
    };
  };

  const allFolders = (tree.folders || []).slice();
  const nonTrash = allFolders.filter((f) => !f.is_trash).sort((a, b) => a.order - b.order);
  const trash = allFolders.filter((f) => f.is_trash);
  const sorted = [...nonTrash, ...trash];

  return sorted.map((f) => mapFolder(f));
}

/* ── Context menu ──────────────────────────────────────────── */

function ContextMenu({ x, y, items, onClose }) {
  const ref = useRef(null);
  const [hoveredSubmenu, setHoveredSubmenu] = useState(null);
  const [clickedSubmenu, setClickedSubmenu] = useState(null);
  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onClick); document.removeEventListener("keydown", onKey); };
  }, [onClose]);

  const menuWidth = 180;
  const left = Math.min(Math.max(4, x), window.innerWidth - menuWidth - 4);
  const top = Math.min(y, window.innerHeight - items.length * 32 - 16);

  const openSubmenu = clickedSubmenu || hoveredSubmenu;

  return (
    <div ref={ref} style={{ ...menuStyles.menu, left, top, position: "fixed", minWidth: menuWidth }} role="menu" aria-label="Context menu">
      {items.map((item, i) =>
        item.separator ? (
          <div key={`sep-${i}`} style={menuStyles.sep} />
        ) : item.submenu ? (
          <SubmenuItem key={item.label} item={item} parentLeft={left} parentWidth={menuWidth}
            isOpen={openSubmenu === item.label}
            onHover={(label) => setHoveredSubmenu(label)}
            onClick={(label) => setClickedSubmenu((prev) => prev === label ? null : label)}
            onClose={onClose} />
        ) : (
          <button key={item.label} role="menuitem"
            style={{ ...menuStyles.item, color: item.danger ? "#c44" : "#222" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "#f0f0f0"; setHoveredSubmenu(null); }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
            onClick={() => { item.action(); onClose(); }}>
            {item.label}
          </button>
        )
      )}
    </div>
  );
}

function SubmenuItem({ item, parentLeft, parentWidth, isOpen, onHover, onClick, onClose }) {
  const wrapRef = useRef(null);
  const subRef = useRef(null);
  const [subStyle, setSubStyle] = useState(null);

  useEffect(() => {
    if (!isOpen || !wrapRef.current) { setSubStyle(null); return; }
    const rect = wrapRef.current.getBoundingClientRect();
    const subWidth = 180;
    const subHeight = item.submenu.length * 32 + 8;
    // Prefer right, fall back to left, fall back to below
    let sl, st;
    if (rect.right + subWidth <= window.innerWidth - 4) {
      sl = rect.width - 2;
      st = 0;
    } else if (rect.left - subWidth >= 4) {
      sl = -subWidth + 2;
      st = 0;
    } else {
      // Open below, aligned left
      sl = 0;
      st = rect.height;
    }
    // Clamp vertically
    const absTop = rect.top + st;
    if (absTop + subHeight > window.innerHeight - 4) {
      st -= (absTop + subHeight - window.innerHeight + 4);
    }
    setSubStyle({ position: "absolute", left: sl, top: st, minWidth: subWidth });
  }, [isOpen, item.submenu.length]);

  return (
    <div ref={wrapRef} style={{ position: "relative" }}
      onMouseEnter={() => onHover(item.label)}
      onMouseLeave={() => onHover(null)}>
      <button role="menuitem"
        style={{ ...menuStyles.item, display: "flex", justifyContent: "space-between" }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "#f0f0f0"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
        onClick={(e) => { e.stopPropagation(); onClick(item.label); }}>
        {item.label} <span style={{ marginLeft: 8, fontSize: 10 }}>▶</span>
      </button>
      {isOpen && subStyle && (
        <div ref={subRef} style={{ ...menuStyles.menu, ...subStyle }}>
          {item.submenu.map((sub) => (
            <button key={sub.label} role="menuitem" style={menuStyles.item}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#f0f0f0"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
              onClick={() => { sub.action(); onClose(); }}>
              {sub.label}
            </button>
          ))}
        </div>
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

/* ── Contrast utility ───────────────────────────────────────── */

function getContrastColor(hex) {
  if (!hex || hex.length < 7) return "#222";
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
  return luminance < 0.5 ? "#fff" : "#222";
}

/* ── Custom node renderer ──────────────────────────────────── */

const iconStyle = { marginRight: 4, fontSize: "0.85rem", flexShrink: 0 };
const nameStyle = { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 };
const mobileMenuBtnStyle = { background: "none", border: "none", cursor: "pointer", padding: "2px 10px", fontSize: "1.1rem", color: "#888", lineHeight: 1, flexShrink: 0, marginRight: 4 };

// Module-level colour metadata for the Node renderer
let _colourMeta = { labels: [], statuses: [], characters: [], iconBgSource: "", textColourSource: "", textBgSource: "" };
let _isMobile = false;
let _onNodeMenu = null; // (rowIndex, clientX, clientY) => void

function resolveColourForSource(nodeData, source, labels, statuses, characters) {
  if (!source) return null;
  const d = nodeData._data;
  if (!d) return null;
  if (source === "label" && d.label) {
    const found = (labels || []).find((l) => l.id === d.label);
    return found?.colour || null;
  }
  if (source === "status" && d.status) {
    const found = (statuses || []).find((s) => s.id === d.status);
    return found?.colour || null;
  }
  if (source === "pov" && d.pov_character) {
    const found = (characters || []).find((c) => c.id === d.pov_character);
    return found?.colour || null;
  }
  return null;
}

function Node({ node, style, dragHandle }) {
  const data = node.data;
  const isFolder = data._type === "folder";

  const { iconBgSource, textColourSource, textBgSource, labels: metaLabels, statuses: metaStatuses, characters: metaCharacters } = _colourMeta;

  const iconBgColour = resolveColourForSource(data, iconBgSource, metaLabels, metaStatuses, metaCharacters);
  const textColour = resolveColourForSource(data, textColourSource, metaLabels, metaStatuses, metaCharacters);
  const textBgColour = resolveColourForSource(data, textBgSource, metaLabels, metaStatuses, metaCharacters);

  const getIconColourStyle = () => {
    if (!iconBgColour) return {};
    return { backgroundColor: iconBgColour, borderRadius: "3px", padding: "0 2px" };
  };

  const getTitleColourStyle = () => {
    const style = {};
    if (textBgColour) {
      style.backgroundColor = textBgColour;
      style.color = getContrastColor(textBgColour);
      style.borderRadius = 3;
      style.padding = "0 3px";
    }
    if (textColour) {
      style.color = textColour;
    }
    return style;
  };

  if (isFolder) {
    const icon = data._icon || DEFAULT_FOLDER_ICON;
    return (
      <div ref={dragHandle} data-row-index={node.rowIndex} style={{ ...style, display: "flex", alignItems: "center", cursor: "pointer", fontWeight: 600, fontSize: "0.9rem", userSelect: "none",
        backgroundColor: node.willReceiveDrop ? "#d8e8ff" : node.isSelected ? "#e8e8ff" : "transparent", borderRadius: 4 }}>
        <span style={{ width: "1em", textAlign: "center", marginRight: 4, fontSize: "0.7rem", flexShrink: 0 }}
          onClick={(e) => { e.stopPropagation(); node.toggle(); }}>
          {node.isOpen ? "▼" : "▶"}
        </span>
        <span style={{ ...iconStyle, ...getIconColourStyle() }} onClick={() => node.activate()}>{icon}</span>
        {node.isEditing && !data._isTrash ? (
          <input autoFocus type="text" defaultValue={data.name} style={{ flex: 1, fontSize: 13, padding: "1px 4px", border: "1px solid #ccc", borderRadius: 3 }}
            onBlur={(e) => node.submit(e.currentTarget.value)}
            onKeyDown={(e) => { if (e.key === "Enter") node.submit(e.currentTarget.value); if (e.key === "Escape") node.reset(); }} />
        ) : (
          <span style={{ ...nameStyle, ...getTitleColourStyle(), flex: 1 }} title={data.name} onClick={() => node.activate()}>{data.name}</span>
        )}
        {_isMobile && _onNodeMenu && (
          <button type="button" style={mobileMenuBtnStyle}
            onClick={(e) => { e.stopPropagation(); _onNodeMenu(node.rowIndex, e.clientX, e.clientY); }}>⋮</button>
        )}
      </div>
    );
  }

  // Text / file item
  const fileType = data._data?.file_type || "text";
  const icon = data._icon || FILE_TYPE_ICONS[fileType] || DEFAULT_TEXT_ICON;
  return (
    <div ref={dragHandle} data-row-index={node.rowIndex}
      style={{ ...style, display: "flex", alignItems: "center", cursor: "pointer", borderRadius: 4, fontSize: "0.9rem",
        backgroundColor: node.isSelected ? "#d0e4ff" : "transparent",
        fontWeight: node.isSelected ? 600 : 400 }}>
      <span style={{ ...iconStyle, ...getIconColourStyle() }}>{icon}</span>
      {node.isEditing ? (
        <input autoFocus type="text" defaultValue={data.name} style={{ flex: 1, fontSize: 13, padding: "1px 4px", border: "1px solid #ccc", borderRadius: 3 }}
          onBlur={(e) => node.submit(e.currentTarget.value)}
          onKeyDown={(e) => { if (e.key === "Enter") node.submit(e.currentTarget.value); if (e.key === "Escape") node.reset(); }} />
      ) : (
        <span style={{ ...nameStyle, ...getTitleColourStyle(), flex: 1 }} title={data.name}>{data.name}</span>
      )}
      {_isMobile && _onNodeMenu && (
        <button type="button" style={mobileMenuBtnStyle}
          onClick={(e) => { e.stopPropagation(); _onNodeMenu(node.rowIndex, e.clientX, e.clientY); }}>⋮</button>
      )}
    </div>
  );
}

/* ── Main component ────────────────────────────────────────── */

export default function ProjectTree({ tree, onSelectFile, activeFileId, selectedFolderId, onSelectFolder, onAddFolder, onDeleteFolder, onAddText, onDeleteText, onReorder, onRenameFolder, onRenameText, onChangeFolderIcon, onChangeTextIcon, onEmptyTrash, onDuplicateFolder, onDuplicateText, onCopyToProject, otherProjects, labels, statuses, characters, treeSettings, isMobile, role, overrides }) {
  const t = useI18n();
  const [menu, setMenu] = useState(null);
  const [iconPicker, setIconPicker] = useState(null);
  const treeRef = useRef(null);
  const containerRef = useRef(null);
  const [treeHeight, setTreeHeight] = useState(600);

  /**
   * Check if a tree node is read-only due to per-object overrides.
   * Returns true if the node or any of its ancestor folders has a
   * "read-only" or "none" override for the current co-author.
   * Owners are never restricted. Only applies to co-authors.
   */
  const isNodeRestricted = useCallback((node) => {
    if (!overrides || !overrides.length || role !== "co-author") return false;
    // Check the node itself
    const d = node.data;
    const targetKey = d._type === "text" ? "target_file" : "target_folder";
    const directMatch = overrides.find((o) => o[targetKey] === d._dbId);
    if (directMatch && (directMatch.permission === "read-only" || directMatch.permission === "none")) {
      return true;
    }
    // Walk up ancestor folders
    let current = node.parent;
    while (current && !current.isRoot) {
      const folderId = current.data?._dbId;
      if (folderId) {
        const match = overrides.find((o) => o.target_folder === folderId);
        if (match && (match.permission === "read-only" || match.permission === "none")) {
          return true;
        }
      }
      current = current.parent;
    }
    return false;
  }, [overrides, role]);  // Persist tree open/closed state per project
  const projectId = tree?.id;
  const storageKey = projectId ? `storyteller-tree-open-${projectId}` : null;

  const [initialOpenState] = useState(() => {
    if (!storageKey) return {};
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : {};
    } catch { return {}; }
  });

  const handleToggle = useCallback((id) => {
    if (!storageKey) return;
    try {
      const saved = localStorage.getItem(storageKey);
      const openState = saved ? JSON.parse(saved) : {};
      // Toggle: if currently open (or defaulting to open), set to closed, and vice versa
      const wasOpen = openState[id] !== undefined ? openState[id] : true;
      openState[id] = !wasOpen;
      localStorage.setItem(storageKey, JSON.stringify(openState));
    } catch { /* ignore */ }
  }, [storageKey]);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      setTreeHeight(entry.contentRect.height);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const arboristData = useMemo(() => toArboristNodes(tree), [tree]);

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
    // Root level: only folders allowed
    if (!parentNode || parentNode.isRoot) {
      return dragNodes.some((n) => n.data._type !== "folder");
    }
    // Can't drop into a text item
    if (parentNode.data?._type === "text") return true;
    // Can't drop into a folder restricted by per-object overrides
    if (isNodeRestricted(parentNode)) return true;
    return false;
  }, [isNodeRestricted]);

  const disableDrag = useCallback((node) => {
    if (node._isTrash === true) return true;
    // Prevent dragging nodes restricted by per-object overrides
    if (treeRef.current) {
      const arboristNode = treeRef.current.get(node.id);
      if (arboristNode && isNodeRestricted(arboristNode)) return true;
    }
    return false;
  }, [isNodeRestricted]);

  // Shared menu builder — used by both right-click and mobile three-dot
  const buildMenuItems = useCallback((node, x, y) => {
    const items = [];
    if (!node) {
      if (onAddFolder) items.push({ label: t("tree.new_folder"), action: () => onAddFolder(null) });
      return items;
    }
    // Suppress all write actions for nodes restricted by per-object overrides
    if (isNodeRestricted(node)) return items;
    const d = node.data;
    if (d._type === "folder") {
      if (d._isTrash) {
        if (onEmptyTrash) items.push({ label: t("trash.empty_trash"), action: () => onEmptyTrash() });
      } else if (d._isInsideTrash) {
        if (onDeleteFolder) items.push({ label: t("trash.permanently_delete"), danger: true, action: () => onDeleteFolder(d._dbId, d.name) });
      } else {
        const newSubmenu = [];
        if (onAddFolder) newSubmenu.push({ label: t("tree.new_subfolder"), action: () => { node.open(); const title = window.prompt(t("tree.folder_title_prompt")); if (title?.trim()) onAddFolder(d._dbId, title.trim()); } });
        if (onAddText) {
          newSubmenu.push({ label: t("tree.new_text"), action: () => { node.open(); const title = window.prompt(t("tree.text_title_prompt")); if (title?.trim()) onAddText(d._dbId, title.trim(), "text"); } });
          newSubmenu.push({ label: t("tree.new_character"), action: () => { node.open(); const title = window.prompt(t("tree.text_title_prompt")); if (title?.trim()) onAddText(d._dbId, title.trim(), "character"); } });
          newSubmenu.push({ label: t("tree.new_location"), action: () => { node.open(); const title = window.prompt(t("tree.text_title_prompt")); if (title?.trim()) onAddText(d._dbId, title.trim(), "location"); } });
          newSubmenu.push({ label: t("tree.new_note"), action: () => { node.open(); const title = window.prompt(t("tree.text_title_prompt")); if (title?.trim()) onAddText(d._dbId, title.trim(), "note"); } });
        }
        if (newSubmenu.length) items.push({ label: t("tree.new"), submenu: newSubmenu });
        items.push({ label: t("tree.rename"), action: () => node.edit() });
        if (onChangeFolderIcon) { items.push({ separator: true }); items.push({ label: t("tree.change_icon"), action: () => { setIconPicker({ x, y, currentIcon: d._icon, onSelect: (icon) => onChangeFolderIcon(d._dbId, icon) }); } }); }
        if (onDuplicateFolder) items.push({ label: t("tree.duplicate"), action: () => onDuplicateFolder(d._dbId) });
        if (onCopyToProject && otherProjects?.length) {
          items.push({ label: t("tree.copy_to_project"), submenu: otherProjects.map((p) => ({ label: p.title, action: () => onCopyToProject("folder", d._dbId, p.id) })) });
        }
        if (onDeleteFolder) { items.push({ separator: true }); items.push({ label: t("tree.delete_folder"), danger: true, action: () => onDeleteFolder(d._dbId, d.name) }); }
      }
    } else if (d._type === "text") {
      if (d._isInsideTrash) {
        if (onDeleteText) items.push({ label: t("trash.permanently_delete"), danger: true, action: () => onDeleteText(d._dbId, d.name) });
      } else {
        items.push({ label: t("tree.rename"), action: () => node.edit() });
        if (onChangeTextIcon) { items.push({ separator: true }); items.push({ label: t("tree.change_icon"), action: () => { setIconPicker({ x, y, currentIcon: d._icon, onSelect: (icon) => onChangeTextIcon(d._dbId, icon) }); } }); }
        if (onDuplicateText) items.push({ label: t("tree.duplicate"), action: () => onDuplicateText(d._dbId) });
        if (onCopyToProject && otherProjects?.length) {
          items.push({ label: t("tree.copy_to_project"), submenu: otherProjects.map((p) => ({ label: p.title, action: () => onCopyToProject("text", d._dbId, p.id) })) });
        }
        if (onDeleteText) { items.push({ separator: true }); items.push({ label: t("tree.delete_text"), danger: true, action: () => onDeleteText(d._dbId, d.name) }); }
      }
    }
    return items;
  }, [t, onAddText, onAddFolder, onDeleteFolder, onDeleteText, onChangeFolderIcon, onChangeTextIcon, onEmptyTrash, onDuplicateFolder, onDuplicateText, onCopyToProject, isNodeRestricted]);

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
    const items = buildMenuItems(node, e.clientX, e.clientY);
    if (items.length) setMenu({ x: e.clientX, y: e.clientY, items });
  }, [buildMenuItems]);

  const handleRename = useCallback(({ id, name }) => {
    if (!name?.trim()) return;
    const isFolder = id.startsWith("folder-");
    const isText = id.startsWith("text-");
    const dbId = parseInt(id.split("-").pop(), 10);
    if (isFolder && onRenameFolder) onRenameFolder(dbId, name.trim());
    if (isText && onRenameText) onRenameText(dbId, name.trim());
  }, [onRenameFolder, onRenameText]);

  if (!tree) return null;

  // Update module-level colour metadata for the Node renderer
  _colourMeta = {
    labels: labels || [],
    statuses: statuses || [],
    characters: characters || [],
    iconBgSource: treeSettings?.tree_icon_bg_source || "",
    textColourSource: treeSettings?.tree_text_colour_source || "",
    textBgSource: treeSettings?.tree_text_bg_source || "",
  };

  // Mobile three-dot menu support
  const handleNodeMenu = useCallback((rowIndex, clientX, clientY) => {
    if (!treeRef.current) return;
    const node = treeRef.current.at(rowIndex);
    if (!node) return;
    const items = buildMenuItems(node, clientX, clientY);
    if (items.length) setMenu({ x: clientX, y: clientY, items });
  }, [buildMenuItems]);

  _isMobile = !!isMobile;
  _onNodeMenu = handleNodeMenu;

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
        initialOpenState={initialOpenState}
        openByDefault={Object.keys(initialOpenState).length === 0}
        onToggle={handleToggle}
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

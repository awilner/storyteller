import { useState, useEffect, useRef, useCallback } from "react";
import { useI18n } from "./I18nContext";
import { useFont } from "./FontContext";
import useIsMobile from "./useIsMobile";
import useProjectWebSocket from "./useProjectWebSocket";
import TopBar from "./TopBar";
import ProjectTree from "./ProjectTree";
import TipTapEditor from "./TipTapEditor";
import FormattingToolbar from "./FormattingToolbar";
import FolderView from "./FolderView";
import MarkdownRenderer from "./MarkdownRenderer";
import VersionHistoryPanel from "./VersionHistoryPanel";
import PropertiesPanel from "./PropertiesPanel";
import CompileDialog from "./CompileDialog";
import ProjectSettings from "./ProjectSettings";
import ProgressPage from "./ProgressPage";
import VersionBadge from "./VersionBadge";
import ObjectPermissionPanel from "./ObjectPermissionPanel";
import { findFolderById, getAncestorFolderIds } from "./treeUtils";
import { fetchProjectTree, fetchFile, saveDraftCache, createVersion, createFolder, deleteFolder, createText, deleteText, updateFolder, updateText, updateProject, reorderTree, emptyTrash, exportScrivener, exportYWriter, duplicateFolder, duplicateText, copyToProject, fetchProjects, fetchUserSettings, fetchProgress as apiFetchProgress, fetchShares, fetchOverrides } from "./api";
import "./EditorView.css";

const DEBOUNCE_MS = 2000;

/**
 * Generate a deterministic HSL colour from a username string.
 * Produces a saturated, medium-lightness colour suitable for cursor labels.
 */
/**
 * Generate a distinct cursor color from a username.
 * Uses FNV-1a hash with a finalizer mix for strong avalanche — even
 * "fanta" vs "fanta2" vs "fanta3" produce very different hues.
 * Returns a 6-digit hex string.
 */
function generateUserColor(name) {
  if (!name) return "#6B7280";
  // FNV-1a 32-bit hash
  let h = 0x811c9dc5;
  for (let i = 0; i < name.length; i++) {
    h ^= name.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  // Murmur3 finalizer — ensures single-character differences avalanche fully
  h = h >>> 0;
  h ^= h >>> 16;
  h = Math.imul(h, 0x85ebca6b);
  h ^= h >>> 13;
  h = Math.imul(h, 0xc2b2ae35);
  h ^= h >>> 16;
  h = h >>> 0;
  const hue = h % 360;
  const s = 0.7, l = 0.45;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((hue / 60) % 2) - 1));
  const m = l - c / 2;
  let r, g, b;
  if (hue < 60)       { r = c; g = x; b = 0; }
  else if (hue < 120) { r = x; g = c; b = 0; }
  else if (hue < 180) { r = 0; g = c; b = x; }
  else if (hue < 240) { r = 0; g = x; b = c; }
  else if (hue < 300) { r = x; g = 0; b = c; }
  else                { r = c; g = 0; b = x; }
  const toHex = (v) => Math.round((v + m) * 255).toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function getTrashFolderId(tree) {
  if (!tree?.folders) return null;
  const trash = tree.folders.find((f) => f.is_trash);
  return trash ? trash.id : null;
}

function isInsideTrash(tree, folderId) {
  if (!tree?.folders) return false;
  const trashFolder = tree.folders.find((f) => f.is_trash);
  if (!trashFolder) return false;
  if (folderId === trashFolder.id) return true;
  const search = (folders) => {
    for (const f of folders || []) {
      if (f.id === folderId) return true;
      if (search(f.children)) return true;
    }
    return false;
  };
  return search(trashFolder.children);
}

function isTextInsideTrash(tree, fileId) {
  if (!tree?.folders) return false;
  const trashFolder = tree.folders.find((f) => f.is_trash);
  if (!trashFolder) return false;
  const search = (folders) => {
    for (const f of folders || []) {
      if ((f.items || []).some((t) => t.id === fileId)) return true;
      if (search(f.children)) return true;
    }
    return false;
  };
  // Check direct items of trash folder
  if ((trashFolder.items || []).some((t) => t.id === fileId)) return true;
  return search(trashFolder.children);
}

export default function EditorView({ projectId, initialFileId, initialProgressOpen, onLogout, onDashboard, username, role: initialRole, onAccount, onSettings }) {
  const t = useI18n();
  const { setProjectFont } = useFont();
  const isMobile = useIsMobile();
  const [mobilePanel, setMobilePanel] = useState("tree");
  const [tree, setTree] = useState(null);
  const [treeLoading, setTreeLoading] = useState(true);
  const [treeError, setTreeError] = useState(null);

  const [activeFileId, setActiveFileId] = useState(() => {
    if (initialFileId) return initialFileId;
    // Restore last selection from localStorage
    try {
      const saved = localStorage.getItem(`storyteller-selection-${projectId}`);
      if (saved) {
        const { type, id } = JSON.parse(saved);
        if (type === "file") return id;
      }
    } catch { /* ignore */ }
    return null;
  });
  const [fileContent, setFileContent] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState(null);

  const [saving, setSaving] = useState(false);
  const [versionKey, setVersionKey] = useState(0);
  const [cacheWarning, setCacheWarning] = useState(null);
  const [collabStatus, setCollabStatus] = useState("online");

  const [editorInstance, setEditorInstance] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [selectedType, setSelectedType] = useState(null); // "folder" | "text"
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [folderWordCount, setFolderWordCount] = useState(0);
  const [folderCharCount, setFolderCharCount] = useState(0);
  const draftRef = useRef(null);
  const debounceTimer = useRef(null);
  const activeFileRef = useRef(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [propsCollapsed, setPropsCollapsed] = useState(false);
  const [statusExpanded, setStatusExpanded] = useState(false);

  // ── Live role (updated via WebSocket) ──────────────────────
  const [liveRole, setLiveRole] = useState(initialRole);

  // Sync from parent when the projects list loads and provides the role
  useEffect(() => {
    if (initialRole) setLiveRole(initialRole);
  }, [initialRole]);

  const role = liveRole;
  const canWrite = role === "owner" || role === "co-author";
  const isOwner = role === "owner";

  // ── Per-object overrides for the current user (co-authors) ─
  const [myOverrides, setMyOverrides] = useState([]);

  useEffect(() => {
    if (role !== "co-author") {
      setMyOverrides([]);
      return;
    }
    fetchOverrides(projectId)
      .then((data) => setMyOverrides(Array.isArray(data) ? data : []))
      .catch(() => setMyOverrides([]));
  }, [projectId, role]);

  // ── Collaboration state ────────────────────────────────────
  const [hasShares, setHasShares] = useState(false);
  const isCollaborative = role && role !== "owner" || hasShares;
  const userColor = generateUserColor(username);

  // Fetch shares to determine if collaboration mode is needed for owners
  useEffect(() => {
    if (role !== "owner") {
      // Non-owners are always in collaborative mode
      setHasShares(true);
      return;
    }
    fetchShares(projectId)
      .then((shares) => setHasShares(Array.isArray(shares) && shares.length > 0))
      .catch(() => setHasShares(false));
  }, [projectId, role]);

  // ── WebSocket for real-time permission notifications ───────
  const [wsNotification, setWsNotification] = useState(null);

  // Helper: re-fetch the project tree and update local state.
  const _refreshTreeFromWs = useCallback(() => {
    fetchProjectTree(projectId)
      .then((d) => {
        setTree(d);
        if (d.role) setLiveRole(d.role);
      })
      .catch(() => {});
  }, [projectId]);

  const wsHandlers = useCallback(() => ({
    onPermissionChanged: (data) => {
      // If this is a project-level role change targeting the current user,
      // update the live role and show a notification on downgrade.
      if (data.username === username && data.new_role && !data.target_folder && !data.target_file) {
        const prevRole = liveRole;
        setLiveRole(data.new_role);
        if (prevRole === "co-author" && data.new_role === "read-only") {
          setCacheWarning(t("sharing.downgraded_to_read_only") || "Your role has been changed to read-only. Editing is now disabled.");
        }
      }
      // Any permission change (role or override) that affects the current
      // user should refresh the tree (which filters blocked objects) and
      // re-fetch the user's overrides so the UI updates immediately.
      if (data.user_id || data.username === username) {
        _refreshTreeFromWs();
        if (liveRole === "co-author") {
          fetchOverrides(projectId)
            .then((d) => setMyOverrides(Array.isArray(d) ? d : []))
            .catch(() => {});
        }
      }
      // Refresh sharing panels for any permission change event.
      setWsNotification({ type: "permission_changed", data, ts: Date.now() });
    },
    onAccessRevoked: (data) => {
      // The consumer only sends this to the affected user, so if we
      // receive it, our access has been revoked.
      setWsNotification({ type: "access_revoked", data, ts: Date.now() });
      alert(data.message || t("sharing.access_revoked_message") || "Your access to this project has been revoked.");
      onDashboard();
    },
    onPresenceUpdate: (data) => {
      setWsNotification({ type: "presence", data, ts: Date.now() });
    },
    // Tree, settings, labels, and statuses are all part of the tree
    // response, so a single re-fetch covers all of them.
    onTreeChanged: _refreshTreeFromWs,
    onSettingsChanged: _refreshTreeFromWs,
    onLabelsChanged: _refreshTreeFromWs,
    onStatusesChanged: _refreshTreeFromWs,
    onLayoutsChanged: _refreshTreeFromWs,
  }), [t, onDashboard, username, liveRole, projectId, _refreshTreeFromWs]);

  useProjectWebSocket(projectId, wsHandlers());

  // ── URL sync ───────────────────────────────────────────────
  // Keep a ref so the popstate handler always sees the latest without re-registering.
  const treeRef = useRef(null);
  useEffect(() => { treeRef.current = tree; }, [tree]);

  useEffect(() => {
    activeFileRef.current = activeFileId;
  }, [activeFileId]);

  // Push URL when user navigates (skip on first render)
  const isFirstRender = useRef(true);
  useEffect(() => {
    const base = `/projects/${projectId}`;
    let path;
    if (activeFileId) {
      path = `${base}/files/${activeFileId}`;
    } else if (selectedType === "folder" && selectedItem?.id) {
      path = `${base}/folders/${selectedItem.id}`;
    } else {
      path = base;
    }
    if (isFirstRender.current) {
      if (window.location.pathname !== path) {
        window.history.replaceState(null, "", path);
      }
      isFirstRender.current = false;
    } else {
      if (window.location.pathname !== path) {
        window.history.pushState(null, "", path);
      }
    }
  }, [activeFileId, selectedItem, selectedType, projectId]);

  // Persist selection to localStorage
  useEffect(() => {
    try {
      if (activeFileId) {
        localStorage.setItem(`storyteller-selection-${projectId}`, JSON.stringify({ type: "file", id: activeFileId }));
      } else if (selectedType === "folder" && selectedItem?.id) {
        localStorage.setItem(`storyteller-selection-${projectId}`, JSON.stringify({ type: "folder", id: selectedItem.id }));
      }
    } catch { /* ignore */ }
  }, [activeFileId, selectedItem, selectedType, projectId]);

  // Browser back/forward — use refs to avoid dependency churn
  useEffect(() => {
    const onPopState = () => {
      if (!window.location.pathname.startsWith(`/projects/${projectId}`)) return;

      const progressMatch = window.location.pathname.match(/^\/projects\/\d+\/progress\/?$/);
      if (progressMatch) {
        setProgressOpen(true);
        return;
      }
      setProgressOpen(false);

      const fileMatch = window.location.pathname.match(/^\/projects\/\d+\/files\/(\d+)/);
      const folderMatch = window.location.pathname.match(/^\/projects\/\d+\/folders\/(\d+)/);
      if (fileMatch) {
        const newFileId = Number(fileMatch[1]);
        if (newFileId === activeFileRef.current) return;
        if (debounceTimer.current) {
          clearTimeout(debounceTimer.current);
          debounceTimer.current = null;
        }
        draftRef.current = null;
        setActiveFileId(newFileId);
      } else if (folderMatch) {
        const folderId = Number(folderMatch[1]);
        if (debounceTimer.current) {
          clearTimeout(debounceTimer.current);
          debounceTimer.current = null;
        }
        draftRef.current = null;
        setActiveFileId(null);
        const t = treeRef.current;
        if (t) {
          const folder = findFolderById(t?.folders, folderId);
          if (folder) {
            setSelectedItem(folder);
            setSelectedType("folder");
          }
        }
      } else {
        if (debounceTimer.current) {
          clearTimeout(debounceTimer.current);
          debounceTimer.current = null;
        }
        draftRef.current = null;
        setActiveFileId(null);
        setSelectedItem(null);
        setSelectedType(null);
      }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [projectId]);

  // Load file content whenever activeFileId changes (from click or popstate)
  useEffect(() => {
    if (!activeFileId) {
      setFileContent(null);
      return;
    }
    let cancelled = false;
    setFileLoading(true);
    setFileError(null);
    fetchFile(activeFileId)
      .then((data) => { if (!cancelled) setFileContent(data.content); })
      .catch((err) => { if (!cancelled) setFileError(err.message); })
      .finally(() => { if (!cancelled) setFileLoading(false); });
    return () => { cancelled = true; };
  }, [activeFileId]);

  // Update selectedItem when activeFileId or tree changes
  const restoredRef = useRef(false);
  useEffect(() => {
    if (!tree) return;
    if (activeFileId) {
      const textItem = findTextInTree(tree, activeFileId);
      if (textItem) {
        setSelectedItem(textItem);
        setSelectedType("text");
      } else {
        setActiveFileId(null);
        setSelectedItem(null);
        setSelectedType(null);
      }
    } else if (selectedType === "folder" && selectedItem?.id) {
      // Refresh the selected folder from the updated tree so metadata
      // (label, status, etc.) stays current after WebSocket-driven refreshes.
      const folder = findFolderById(tree?.folders, selectedItem.id);
      if (folder) {
        setSelectedItem(folder);
      } else {
        setSelectedItem(null);
        setSelectedType(null);
      }
    } else if (!restoredRef.current) {
      // One-time: restore folder selection from localStorage
      restoredRef.current = true;
      try {
        const saved = localStorage.getItem(`storyteller-selection-${projectId}`);
        if (saved) {
          const { type, id } = JSON.parse(saved);
          if (type === "folder") {
            const folder = findFolderById(tree?.folders, id);
            if (folder) {
              setSelectedItem(folder);
              setSelectedType("folder");
            }
          }
        }
      } catch { /* ignore */ }
    }
  }, [activeFileId, tree]);

  // ── Word/char counts ───────────────────────────────────────

  useEffect(() => {
    if (!editorInstance) {
      // No editor instance — either no file selected or read-only mode.
      // In read-only mode, compute counts from the raw markdown content.
      if (activeFileId && fileContent) {
        const plain = fileContent.replace(/[#*_~`>\[\]()!|\-]/g, "").trim();
        setCharCount(plain.length);
        setWordCount(plain ? plain.split(/\s+/).length : 0);
      } else {
        setWordCount(0);
        setCharCount(0);
      }
      return;
    }
    const updateCounts = () => {
      const text = editorInstance.state.doc.textContent;
      setCharCount(text.length);
      const trimmed = text.trim();
      setWordCount(trimmed ? trimmed.split(/\s+/).length : 0);
    };
    updateCounts();
    editorInstance.on("transaction", updateCounts);
    return () => {
      editorInstance.off("transaction", updateCounts);
    };
  }, [editorInstance, activeFileId, fileContent]);

  useEffect(() => {
    setTreeLoading(true);
    setTreeError(null);
    fetchProjectTree(projectId)
      .then((data) => {
        setTree(data);
        setProjectFont(data.settings?.editor_font || "");
        // The tree response includes the authenticated user's role on this
        // project, derived from the permission engine. Always trust it.
        if (data.role) {
          setLiveRole(data.role);
        }
      })
      .catch((err) => setTreeError(err.message))
      .finally(() => setTreeLoading(false));
  }, [projectId]);

  const flushDraftToCache = useCallback(
    async (fileId, content) => {
      if (!fileId || content == null) return;
      try {
        await saveDraftCache(fileId, content);
      } catch {
        setCacheWarning(t("editor.draft_cache_warning"));
      }
    },
    [],
  );

  const loadFile = useCallback(async (fileId) => {
    setFileLoading(true);
    setFileError(null);
    setFileContent(null);
    try {
      const data = await fetchFile(fileId);
      setFileContent(data.content);
    } catch (err) {
      setFileError(err.message);
    } finally {
      setFileLoading(false);
    }
  }, []);

  // Recursive helpers for nested folder tree
  const findTextInTree = useCallback((treeData, fileId) => {
    const searchFolders = (folders) => {
      for (const f of folders || []) {
        const found = (f.items || []).find((t) => t.id === fileId);
        if (found) return found;
        const nested = searchFolders(f.children);
        if (nested) return nested;
      }
      return null;
    };
    return searchFolders(treeData?.folders);
  }, []);

  const folderContainsFile = useCallback((folder, fileId) => {
    if ((folder.texts || []).some((t) => t.id === fileId)) return true;
    if ((folder.items || []).some((t) => t.id === fileId)) return true;
    for (const child of folder.children || []) {
      if (folderContainsFile(child, fileId)) return true;
    }
    return false;
  }, []);

  const handleSelectFile = useCallback(
    async (fileId) => {
      if (fileId === activeFileId) return;
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
        debounceTimer.current = null;
      }
      if (activeFileId && draftRef.current != null) {
        await flushDraftToCache(activeFileId, draftRef.current);
      }
      draftRef.current = null;
      setActiveFileId(fileId);
      if (isMobile) setMobilePanel("editor");
    },
    [activeFileId, flushDraftToCache, isMobile],
  );

  const handleSelectFolder = useCallback((folderId) => {
    if (!tree) return;
    const folder = findFolderById(tree?.folders, folderId);
    if (folder) {
      // Clear active file — folder selection replaces text editing
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
        debounceTimer.current = null;
      }
      if (activeFileId && draftRef.current != null) {
        flushDraftToCache(activeFileId, draftRef.current);
      }
      draftRef.current = null;
      setActiveFileId(null);
      setSelectedItem(folder);
      setSelectedType("folder");
    }
  }, [tree, findFolderById, activeFileId, flushDraftToCache]);

  const handleEditorUpdate = useCallback(
    (markdown) => {
      draftRef.current = markdown;
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(() => {
        const fid = activeFileRef.current;
        if (fid) flushDraftToCache(fid, markdown);
      }, DEBOUNCE_MS);
    },
    [flushDraftToCache],
  );

  // ── Progress data for status bar ───────────────────────────
  const [progressData, setProgressData] = useState(null);
  const loadProgress = useCallback(() => {
    apiFetchProgress(projectId).then(setProgressData).catch(() => {});
  }, [projectId]);

  // Defer initial load — don't fetch if progress page is already open
  // (ProgressPage will call onDataLoaded instead)
  const progressOpenRef = useRef(!!initialProgressOpen);
  useEffect(() => {
    if (!progressOpenRef.current) loadProgress();
  }, [loadProgress]);

  const handleSave = useCallback(async () => {
    if (!activeFileId || draftRef.current == null) return;
    setSaving(true);
    try {
      await createVersion(activeFileId, draftRef.current);
      draftRef.current = null;
      setVersionKey((k) => k + 1);
      await loadFile(activeFileId);
      loadProgress();
    } catch (err) {
      setFileError(t("editor.save_failed", { error: err.message }));
    } finally {
      setSaving(false);
    }
  }, [activeFileId, loadFile, loadProgress]);

  const handleRevert = useCallback(() => {
    if (activeFileId) {
      draftRef.current = null;
      loadFile(activeFileId);
    }
  }, [activeFileId, loadFile]);

  const refreshTree = useCallback(async () => {
    try {
      const data = await fetchProjectTree(projectId);
      setTree(data);
      if (data.role) setLiveRole(data.role);
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId]);

  const countFolders = useCallback((folders) => {
    let count = 0;
    for (const f of folders || []) {
      count += 1 + countFolders(f.children);
    }
    return count;
  }, []);

  const handleAddFolder = useCallback(async (parentId = null, titleArg = null) => {
    const title = titleArg || window.prompt(t("tree.folder_title_prompt"));
    if (!title?.trim()) return;
    let nextOrder = 0;
    if (parentId) {
      const parent = findFolderById(tree?.folders, parentId);
      nextOrder = (parent?.children?.length ?? 0);
    } else {
      nextOrder = (tree?.folders?.length ?? 0);
    }
    try {
      await createFolder(projectId, title.trim(), nextOrder, parentId);
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, tree, refreshTree, findFolderById]);

  const handleDeleteFolder = useCallback(async (folderId, title) => {
    const inTrash = isInsideTrash(tree, folderId);
    if (inTrash) {
      // Permanent delete — show confirmation (mention contents for folders)
      if (!window.confirm(t("trash.confirm_permanent_delete_folder", { title }))) return;
      try {
        if (activeFileId) {
          const folder = findFolderById(tree?.folders, folderId);
          if (folder && folderContainsFile(folder, activeFileId)) {
            setActiveFileId(null);
            setFileContent(null);
            draftRef.current = null;
          }
        }
        await deleteFolder(projectId, folderId);
        await refreshTree();
      } catch (err) {
        setTreeError(err.message);
      }
    } else {
      // Soft delete — move to trash (with confirmation)
      if (!window.confirm(t("tree.confirm_move_to_trash", { title }))) return;
      const trashId = getTrashFolderId(tree);
      if (!trashId) return;
      try {
        if (activeFileId) {
          const folder = findFolderById(tree?.folders, folderId);
          if (folder && folderContainsFile(folder, activeFileId)) {
            setActiveFileId(null);
            setFileContent(null);
            draftRef.current = null;
          }
        }
        await updateFolder(projectId, folderId, { parent: trashId });
        await refreshTree();
      } catch (err) {
        setTreeError(err.message);
      }
    }
  }, [projectId, activeFileId, tree, refreshTree, findFolderById, folderContainsFile]);

  const handleAddText = useCallback(async (folderId, title, fileType = "text") => {
    const folder = findFolderById(tree?.folders, folderId);
    const nextOrder = (folder?.items?.length ?? 0);
    try {
      await createText(projectId, folderId, title, nextOrder, fileType);
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, tree, refreshTree, findFolderById]);

  const handleDeleteText = useCallback(async (fileId, title) => {
    const inTrash = isTextInsideTrash(tree, fileId);
    if (inTrash) {
      // Permanent delete — show confirmation
      if (!window.confirm(t("trash.confirm_permanent_delete", { title }))) return;
      try {
        if (fileId === activeFileId) {
          setActiveFileId(null);
          setFileContent(null);
          draftRef.current = null;
        }
        await deleteText(projectId, fileId);
        await refreshTree();
      } catch (err) {
        setTreeError(err.message);
      }
    } else {
      // Soft delete — move to trash (with confirmation)
      if (!window.confirm(t("tree.confirm_move_to_trash", { title }))) return;
      const trashId = getTrashFolderId(tree);
      if (!trashId) return;
      try {
        if (fileId === activeFileId) {
          setActiveFileId(null);
          setFileContent(null);
          draftRef.current = null;
        }
        await updateText(projectId, fileId, { folder: trashId });
        await refreshTree();
      } catch (err) {
        setTreeError(err.message);
      }
    }
  }, [projectId, activeFileId, tree, refreshTree]);

  const handleEmptyTrash = useCallback(async () => {
    if (!window.confirm(t("trash.confirm_empty"))) return;
    try {
      // If active file is inside trash, clear editor state
      if (activeFileId && isTextInsideTrash(tree, activeFileId)) {
        setActiveFileId(null);
        setFileContent(null);
        draftRef.current = null;
      }
      await emptyTrash(projectId);
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, activeFileId, tree, refreshTree]);

  const handleExportScrivener = useCallback(() => {
    window.location.href = exportScrivener(projectId);
  }, [projectId]);

  const handleExportYWriter = useCallback(() => {
    window.location.href = exportYWriter(projectId);
  }, [projectId]);

  const [compileOpen, setCompileOpen] = useState(false);
  const [projectSettingsOpen, setProjectSettingsOpen] = useState(false);
  const [progressOpen, setProgressOpen] = useState(!!initialProgressOpen);
  const handleCompile = useCallback(() => setCompileOpen(true), []);
  const handleProjectSettings = useCallback(() => setProjectSettingsOpen(true), []);
  const handleProgressTracking = useCallback(() => {
    setProgressOpen(true);
    window.history.pushState(null, "", `/projects/${projectId}/progress`);
  }, [projectId]);
  const handleCloseProgress = useCallback(() => {
    setProgressOpen(false);
    loadProgress();
    const base = `/projects/${projectId}`;
    if (window.location.pathname !== base) {
      window.history.pushState(null, "", base);
    }
  }, [projectId, loadProgress]);

  const handleCloseProjectSettings = useCallback(async () => {
    setProjectSettingsOpen(false);
    await refreshTree();
  }, [refreshTree]);

  const handleSaveProperties = useCallback(async (data) => {
    if (!selectedItem || !selectedType) return;
    if (selectedType === "folder") {
      await updateFolder(projectId, selectedItem.id, data);
    } else {
      await updateText(projectId, selectedItem.id, data);
    }
    const freshTree = await fetchProjectTree(projectId);
    setTree(freshTree);
    if (selectedType === "folder") {
      const updated = findFolderById(freshTree?.folders, selectedItem.id);
      if (updated) setSelectedItem(updated);
    } else {
      const updated = findTextInTree(freshTree, selectedItem.id);
      if (updated) setSelectedItem(updated);
    }
  }, [projectId, selectedItem, selectedType, findFolderById, findTextInTree]);

  const handleReorder = useCallback(async (folderUpdates, textUpdates) => {
    try {
      await reorderTree(projectId, folderUpdates, textUpdates);
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, refreshTree]);

  const handleRenameFolder = useCallback(async (folderId, newTitle) => {
    try {
      await updateFolder(projectId, folderId, { title: newTitle });
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, refreshTree]);

  const handleRenameText = useCallback(async (textId, newTitle) => {
    try {
      await updateText(projectId, textId, { title: newTitle });
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, refreshTree]);

  const handleChangeFolderIcon = useCallback(async (folderId, icon) => {
    try {
      await updateFolder(projectId, folderId, { icon });
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, refreshTree]);

  const handleChangeTextIcon = useCallback(async (textId, icon) => {
    try {
      await updateText(projectId, textId, { icon });
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, refreshTree]);

  const handleDuplicateFolder = useCallback(async (folderId) => {
    try {
      await duplicateFolder(projectId, folderId);
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, refreshTree]);

  const handleDuplicateText = useCallback(async (fileId) => {
    try {
      await duplicateText(projectId, fileId);
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, refreshTree]);

  const handleCopyToProject = useCallback(async (type, itemId, targetProjectId) => {
    try {
      await copyToProject(projectId, { target_project_id: targetProjectId, type, id: itemId });
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId]);

  // Fetch other projects for "Copy to Project" submenu
  const [otherProjects, setOtherProjects] = useState([]);
  useEffect(() => {
    fetchProjects().then((projects) => {
      setOtherProjects(projects.filter((p) => p.id !== projectId));
    }).catch(() => {});
  }, [projectId]);

  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      setProjectFont("");
    };
  }, []);

  // ── Auto-save ──────────────────────────────────────────────
  const [userAutoSave, setUserAutoSave] = useState(60);
  useEffect(() => {
    fetchUserSettings().then((prefs) => {
      if (prefs.auto_save_interval != null) setUserAutoSave(prefs.auto_save_interval);
    }).catch(() => {});
  }, []);

  const autoSaveInterval = tree?.settings?.auto_save_interval ?? userAutoSave ?? 60;
  const autoSaveRef = useRef(null);

  useEffect(() => {
    if (autoSaveRef.current) clearInterval(autoSaveRef.current);
    if (!autoSaveInterval || autoSaveInterval <= 0) return;

    autoSaveRef.current = setInterval(async () => {
      const fid = activeFileRef.current;
      if (fid && draftRef.current != null) {
        try {
          await createVersion(fid, draftRef.current);
          draftRef.current = null;
          setVersionKey((k) => k + 1);
          loadProgress();
        } catch {
          // silent — don't disrupt the user
        }
      }
    }, autoSaveInterval * 1000);

    return () => { if (autoSaveRef.current) clearInterval(autoSaveRef.current); };
  }, [autoSaveInterval]);

  // Derive a refresh key for sharing panels from WebSocket notifications
  const sharingRefreshKey = wsNotification?.ts || 0;

  // Compute ancestor folder IDs for the selected item (used by ObjectPermissionPanel)
  const selectedAncestorIds = selectedItem && tree
    ? getAncestorFolderIds(tree.folders, selectedType === "text" ? "file" : "folder", selectedItem.id)
    : [];

  // Compute effective permission on the selected object for the current user.
  // Owners always have full access. For co-authors, check per-object overrides.
  const objectEffectivePerm = (() => {
    if (!role || role === "owner") return role;
    if (role !== "co-author" || !selectedItem) return role;

    const RANK = { "co-author": 2, "read-only": 1, "none": 0 };

    const targetKey = selectedType === "text" ? "target_file" : "target_folder";
    const directOverride = myOverrides.find(
      (o) => o[targetKey] === selectedItem.id
    );
    const ownPerm = directOverride ? directOverride.permission : role;

    let parentPerm = role;
    for (let i = selectedAncestorIds.length - 1; i >= 0; i--) {
      const match = myOverrides.find(
        (o) => o.target_folder === selectedAncestorIds[i]
      );
      if (match) { parentPerm = match.permission; break; }
    }

    return (RANK[ownPerm] ?? 2) <= (RANK[parentPerm] ?? 2) ? ownPerm : parentPerm;
  })();

  const canWriteObject = objectEffectivePerm === "owner" || objectEffectivePerm === "co-author";

  const sidebarContent = (
    <div className="editor-sidebar-inner">
      <div className="editor-sidebar-tree">
        {treeLoading && <p className="loading-text" style={{ padding: 12 }}>{t("editor.loading_project")}</p>}
        {treeError && <p className="error-text" style={{ padding: 12 }}>{treeError}</p>}
        {tree && (
          <ProjectTree
            tree={tree}
            activeFileId={activeFileId}
            onSelectFile={handleSelectFile}
            onSelectFolder={handleSelectFolder}
            selectedFolderId={selectedType === "folder" ? selectedItem?.id : null}
            onAddFolder={canWrite ? handleAddFolder : null}
            onDeleteFolder={canWrite ? handleDeleteFolder : null}
            onAddText={canWrite ? handleAddText : null}
            onDeleteText={canWrite ? handleDeleteText : null}
            onReorder={canWrite ? handleReorder : null}
            onRenameFolder={canWrite ? handleRenameFolder : null}
            onRenameText={canWrite ? handleRenameText : null}
            onChangeFolderIcon={canWrite ? handleChangeFolderIcon : null}
            onChangeTextIcon={canWrite ? handleChangeTextIcon : null}
            onEmptyTrash={canWrite ? handleEmptyTrash : null}
            onDuplicateFolder={canWrite ? handleDuplicateFolder : null}
            onDuplicateText={canWrite ? handleDuplicateText : null}
            onCopyToProject={canWrite ? handleCopyToProject : null}
            otherProjects={otherProjects}
            labels={tree?.labels}
            statuses={tree?.statuses}
            characters={tree?.characters}
            treeSettings={tree?.settings}
            isMobile={isMobile}
            role={role}
            overrides={myOverrides}
          />
        )}
      </div>
      <VersionBadge />
    </div>
  );

  const editorContent = (
    <div className="editor-center">
      <div>
        {cacheWarning && (
          <div className="editor-banner" role="alert">
            ⚠ {cacheWarning}
            <button type="button" onClick={() => setCacheWarning(null)} className="editor-banner-dismiss"
              aria-label={t("editor.dismiss_warning")}>✕</button>
          </div>
        )}
        {isCollaborative && collabStatus === "offline" && (
          <div className="editor-banner editor-banner--sync-offline" role="status">
            ⚡ {t("editor.sync_offline") || "Real-time sync is offline — changes are saved locally only"}
          </div>
        )}
        {activeFileId && canWriteObject && (
        <div className="editor-topbar">
          <FormattingToolbar editor={editorInstance} />
          <button type="button" className="editor-save-btn" onClick={handleSave} disabled={saving || !activeFileId}>
            {saving ? t("editor.saving") : t("editor.save")}
          </button>
        </div>
        )}
      </div>

      <div className="editor-area">
        {!activeFileId && selectedType === "folder" && selectedItem && (
          <FolderView folder={selectedItem} onSelectFile={handleSelectFile}
            onCounts={({ wordCount: wc, charCount: cc }) => { setFolderWordCount(wc); setFolderCharCount(cc); }} />
        )}
        {!activeFileId && selectedType !== "folder" && (
          <div className="editor-placeholder">{t("editor.select_file_placeholder")}</div>
        )}
        {fileLoading && <p className="loading-text">{t("editor.loading_file")}</p>}
        {fileError && <p className="error-text">{fileError}</p>}
        {activeFileId && !fileLoading && !fileError && fileContent != null && canWriteObject && (
          <TipTapEditor
            content={fileContent}
            onUpdate={handleEditorUpdate}
            editorRef={setEditorInstance}
            isCollaborative={isCollaborative}
            fileId={activeFileId}
            username={username}
            userColor={userColor}
            permission={role}
            onCollabStatusChange={setCollabStatus}
          />
        )}
        {activeFileId && !fileLoading && !fileError && fileContent != null && !canWriteObject && (
          <div className="editor-readonly-view">
            <MarkdownRenderer content={fileContent} className="editor-readonly-content" />
          </div>
        )}
      </div>

      {(() => {
        const showFile = activeFileId;
        const showFolder = !activeFileId && selectedType === "folder" && selectedItem;
        if (!showFile && !showFolder) return <div className="editor-status-bar" style={{ visibility: "hidden" }} />;
        const wc = showFile ? wordCount : folderWordCount;
        const cc = showFile ? charCount : folderCharCount;
        const target = selectedItem?.target_word_count;
        const hasProgress = progressData?.manuscript_target != null || (canWrite && (progressData?.daily_target != null || progressData?.session_target != null));
        return (
          <div className="editor-status-bar" aria-live="polite">
            <span>{wc.toLocaleString()} {t("editor.words")}</span>
            <span>{cc.toLocaleString()} {t("editor.characters")}</span>
            {target > 0 && (() => {
              const pct = Math.min(Math.round((wc / target) * 100), 100);
              const r = pct < 50 ? 220 : Math.round(220 - (pct - 50) * 4);
              const g = pct < 50 ? Math.round(80 + pct * 3) : 200;
              const barColor = `rgb(${r},${g},60)`;
              return (
                <span className="editor-wc-bar">
                  <span className="editor-wc-track">
                    <span className="editor-wc-fill" style={{ width: `${pct}%`, background: barColor }} />
                  </span>
                  <span>{pct}%</span>
                  <span>{wc.toLocaleString()}/{target.toLocaleString()}</span>
                </span>
              );
            })()}
            {isMobile && hasProgress && (
              <button type="button" className="editor-status-toggle" onClick={() => setStatusExpanded((v) => !v)} aria-label="Toggle progress">
                {statusExpanded ? "▼" : "▲"}
              </button>
            )}
            <div className={`editor-status-progress${isMobile && !statusExpanded ? " editor-status-progress--collapsed" : ""}`}>
              {progressData?.manuscript_target != null && (() => {
                const msPct = Math.min(Math.round((progressData.current_word_count / progressData.manuscript_target) * 100), 100);
                return <span>{t("status.manuscript")}: {progressData.current_word_count.toLocaleString()}/{progressData.manuscript_target.toLocaleString()} ({msPct}%)</span>;
              })()}
              {canWrite && progressData?.daily_target != null && (
                <span>{t("dashboard.daily_progress")}: {progressData.daily_word_count.toLocaleString()}/{progressData.daily_target.toLocaleString()} ({Math.min(Math.round((progressData.daily_word_count / progressData.daily_target) * 100), 100)}%)</span>
              )}
              {canWrite && progressData?.session_target != null && (
                <span>{t("status.session")}: {progressData.session_word_count.toLocaleString()}/{progressData.session_target.toLocaleString()} ({Math.min(Math.round((progressData.session_word_count / progressData.session_target) * 100), 100)}%)</span>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );

  const propertiesContent = (
    <div className={isMobile ? "editor-right-panel--mobile" : "editor-right-panel"}>
      {selectedItem && <PropertiesPanel item={selectedItem} type={selectedType} onSave={canWriteObject ? handleSaveProperties : null} characters={tree?.characters} labels={tree?.labels} statuses={tree?.statuses} />}
      {selectedItem && (selectedType === "folder" || selectedType === "text") && (
        <ObjectPermissionPanel projectId={projectId} role={role} objectType={selectedType === "text" ? "file" : "folder"} objectId={selectedItem.id} ancestorFolderIds={selectedAncestorIds} refreshKey={sharingRefreshKey} username={username} />
      )}
      {activeFileId && <VersionHistoryPanel fileId={activeFileId} onRevert={canWriteObject ? handleRevert : null} refreshKey={versionKey} />}
    </div>
  );

  // ── Mobile layout ──────────────────────────────────────────
  if (isMobile) {
    return (
      <div className="editor-mobile-wrapper">
        <TopBar projectTitle={tree?.title} onHome={onDashboard} username={username} onAccount={onAccount} onSettings={onSettings} onLogout={onLogout} onExportScrivener={handleExportScrivener} onExportYWriter={handleExportYWriter} onCompile={handleCompile} onProjectSettings={handleProjectSettings} onProgressTracking={handleProgressTracking} role={role} />
        <div className="editor-mobile-tabs">
          <button type="button" className={`editor-mobile-tab${mobilePanel === "tree" ? " editor-mobile-tab--active" : ""}`} onClick={() => setMobilePanel("tree")}>📁 Tree</button>
          <button type="button" className={`editor-mobile-tab${mobilePanel === "editor" ? " editor-mobile-tab--active" : ""}`} onClick={() => setMobilePanel("editor")}>✏️ Editor</button>
          <button type="button" className={`editor-mobile-tab${mobilePanel === "properties" ? " editor-mobile-tab--active" : ""}`} onClick={() => setMobilePanel("properties")}>ℹ️ Info</button>
        </div>
        <div className="editor-mobile-body">
          {progressOpen ? (
            <ProgressPage projectId={projectId} onClose={handleCloseProgress} onDataLoaded={setProgressData} initialData={progressData} />
          ) : (
            <>
              {mobilePanel === "tree" && <div className="editor-mobile-tree">{sidebarContent}</div>}
              {mobilePanel === "editor" && editorContent}
              {mobilePanel === "properties" && propertiesContent}
            </>
          )}
        </div>
        {compileOpen && <CompileDialog projectId={projectId} tree={tree} onClose={() => setCompileOpen(false)} />}
        {projectSettingsOpen && <ProjectSettings projectId={projectId} settings={tree?.settings} onClose={handleCloseProjectSettings} onRefresh={refreshTree} role={role} />}
      </div>
    );
  }

  // ── Desktop layout ─────────────────────────────────────────
  return (
    <div className="editor-desktop-wrapper">
      <TopBar projectTitle={tree?.title} onHome={onDashboard} username={username} onAccount={onAccount} onSettings={onSettings} onLogout={onLogout} onExportScrivener={handleExportScrivener} onExportYWriter={handleExportYWriter} onCompile={handleCompile} onProjectSettings={handleProjectSettings} onProgressTracking={handleProgressTracking} role={role} />
      {progressOpen ? (
        <ProgressPage projectId={projectId} onClose={handleCloseProgress} onDataLoaded={setProgressData} initialData={progressData} />
      ) : (
      <div className="editor-desktop-body">
        {!sidebarCollapsed && (
          <div className="editor-sidebar">{sidebarContent}</div>
        )}
        <div className="editor-center-wrapper">
          <button type="button" className="editor-toggle-btn editor-toggle-btn--left" onClick={() => setSidebarCollapsed((v) => !v)} title={sidebarCollapsed ? "Show tree" : "Hide tree"}>
            {sidebarCollapsed ? "▶" : "◀"}
          </button>
          {editorContent}
          {(selectedItem || activeFileId) && (
            <button type="button" className="editor-toggle-btn editor-toggle-btn--right" onClick={() => setPropsCollapsed((v) => !v)} title={propsCollapsed ? "Show properties" : "Hide properties"}>
              {propsCollapsed ? "◀" : "▶"}
            </button>
          )}
        </div>
        {(selectedItem || activeFileId) && !propsCollapsed && (
          <div className="editor-right-panel">
            {selectedItem && <PropertiesPanel item={selectedItem} type={selectedType} onSave={canWriteObject ? handleSaveProperties : null} characters={tree?.characters} labels={tree?.labels} statuses={tree?.statuses} />}
            {selectedItem && (selectedType === "folder" || selectedType === "text") && (
              <ObjectPermissionPanel projectId={projectId} role={role} objectType={selectedType === "text" ? "file" : "folder"} objectId={selectedItem.id} ancestorFolderIds={selectedAncestorIds} refreshKey={sharingRefreshKey} username={username} />
            )}
            {activeFileId && <VersionHistoryPanel fileId={activeFileId} onRevert={canWriteObject ? handleRevert : null} refreshKey={versionKey} />}
          </div>
        )}
      </div>
      )}
      {compileOpen && <CompileDialog projectId={projectId} tree={tree} onClose={() => setCompileOpen(false)} />}
      {projectSettingsOpen && <ProjectSettings projectId={projectId} settings={tree?.settings} onClose={handleCloseProjectSettings} onRefresh={refreshTree} role={role} />}
    </div>
  );
}

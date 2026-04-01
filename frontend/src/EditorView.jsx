import { useState, useEffect, useRef, useCallback } from "react";
import { useI18n } from "./I18nContext";
import useIsMobile from "./useIsMobile";
import NavSidebar, { NavBar } from "./NavSidebar";
import ProjectTree from "./ProjectTree";
import TipTapEditor from "./TipTapEditor";
import FormattingToolbar from "./FormattingToolbar";
import VersionHistoryPanel from "./VersionHistoryPanel";
import PropertiesPanel from "./PropertiesPanel";
import { fetchProjectTree, fetchFile, saveDraftCache, createVersion, createFolder, deleteFolder, createText, deleteText, updateFolder, updateText, reorderTree } from "./api";

const DEBOUNCE_MS = 2000;

const styles = {
  container: {
    display: "flex",
    flex: 1,
    minHeight: 0,
    overflow: "hidden",
    fontFamily: "system-ui",
  },
  sidebar: {
    width: 250,
    minWidth: 250,
    borderRight: "1px solid #ddd",
    overflowY: "auto",
    background: "#fafafa",
  },
  center: {
    flex: 1,
    display: "grid",
    gridTemplateRows: "auto 1fr auto",
    minWidth: 0,
    overflow: "hidden",
  },
  topBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "4px 12px",
    borderBottom: "1px solid #ddd",
    background: "#f9f9f9",
  },
  editorArea: {
    overflowY: "auto",
    minHeight: 0,
    padding: "0 12px 24px",
  },
  banner: {
    background: "#fff3cd",
    color: "#856404",
    padding: "6px 12px",
    fontSize: 13,
    borderBottom: "1px solid #ffc107",
  },
  placeholder: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    color: "#999",
    fontSize: "1.1rem",
  },
  saveBtn: {
    padding: "4px 14px",
    cursor: "pointer",
    border: "1px solid #ccc",
    borderRadius: 4,
    background: "#4a90d9",
    color: "#fff",
    fontWeight: 600,
    fontSize: 13,
  },
  statusBar: {
    display: "flex",
    gap: 16,
    padding: "4px 12px",
    borderTop: "1px solid #ddd",
    background: "#f5f5f5",
    fontSize: 12,
    color: "#666",
  },
};

export default function EditorView({ projectId, initialFileId, onLogout, onDashboard }) {
  const t = useI18n();
  const isMobile = useIsMobile();
  const [mobilePanel, setMobilePanel] = useState("tree"); // "tree" | "editor" | "properties"
  const [navSection, setNavSection] = useState("editor"); // "editor" | "outline" | "characters" | "locations" | "notes"
  const [tree, setTree] = useState(null);
  const [treeLoading, setTreeLoading] = useState(true);
  const [treeError, setTreeError] = useState(null);

  const [activeFileId, setActiveFileId] = useState(initialFileId || null);
  const [fileContent, setFileContent] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState(null);

  const [saving, setSaving] = useState(false);
  const [cacheWarning, setCacheWarning] = useState(null);

  const [editorInstance, setEditorInstance] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [selectedType, setSelectedType] = useState(null); // "folder" | "text"
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const draftRef = useRef(null);
  const debounceTimer = useRef(null);
  const activeFileRef = useRef(null);

  // ── URL sync ───────────────────────────────────────────────
  // Keep a ref so the popstate handler always sees the latest without re-registering.
  const treeRef = useRef(null);
  useEffect(() => { treeRef.current = tree; }, [tree]);

  useEffect(() => {
    activeFileRef.current = activeFileId;
  }, [activeFileId]);

  // Push URL when user clicks a file or folder (skip on first render)
  const isFirstRender = useRef(true);
  useEffect(() => {
    let path;
    if (activeFileId) {
      path = `/projects/${projectId}/files/${activeFileId}`;
    } else if (selectedType === "folder" && selectedItem?.id) {
      path = `/projects/${projectId}/folders/${selectedItem.id}`;
    } else {
      path = `/projects/${projectId}`;
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

  // Browser back/forward — use refs to avoid dependency churn
  useEffect(() => {
    const onPopState = () => {
      if (!window.location.pathname.startsWith(`/projects/${projectId}`)) return;
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
        // selectedItem/type will be set by the [activeFileId, tree] effect
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
          const folder = findFolderById(t.folders, folderId);
          if (folder) {
            setSelectedItem(folder);
            setSelectedType("folder");
          }
        }
      } else {
        // Just /projects/:id — clear everything
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
  useEffect(() => {
    if (!tree) return;
    if (activeFileId) {
      const textItem = findTextInTree(tree.folders, activeFileId);
      if (textItem) {
        setSelectedItem(textItem);
        setSelectedType("text");
      } else {
        // URL points to something that isn't a text — clear it
        setActiveFileId(null);
        setSelectedItem(null);
        setSelectedType(null);
      }
    }
  }, [activeFileId, tree]);

  // ── Word/char counts ───────────────────────────────────────

  useEffect(() => {
    if (!editorInstance) {
      setWordCount(0);
      setCharCount(0);
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
  }, [editorInstance]);

  useEffect(() => {
    setTreeLoading(true);
    setTreeError(null);
    fetchProjectTree(projectId)
      .then(setTree)
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
  const findFolderById = useCallback((folders, id) => {
    for (const f of folders || []) {
      if (f.id === id) return f;
      const found = findFolderById(f.children, id);
      if (found) return found;
    }
    return null;
  }, []);

  const findTextInTree = useCallback((folders, fileId) => {
    for (const f of folders || []) {
      const found = (f.texts || []).find((t) => t.id === fileId);
      if (found) return found;
      const nested = findTextInTree(f.children, fileId);
      if (nested) return nested;
    }
    return null;
  }, []);

  const folderContainsFile = useCallback((folder, fileId) => {
    if ((folder.texts || []).some((t) => t.id === fileId)) return true;
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
    const folder = findFolderById(tree.folders, folderId);
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

  const handleSave = useCallback(async () => {
    if (!activeFileId || draftRef.current == null) return;
    setSaving(true);
    try {
      await createVersion(activeFileId, draftRef.current);
      draftRef.current = null;
      await loadFile(activeFileId);
    } catch (err) {
      setFileError(t("editor.save_failed", { error: err.message }));
    } finally {
      setSaving(false);
    }
  }, [activeFileId, loadFile]);

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
    if (!window.confirm(t("tree.confirm_delete_folder", { title }))) return;
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
  }, [projectId, activeFileId, tree, refreshTree, findFolderById, folderContainsFile]);

  const handleAddText = useCallback(async (folderId, title) => {
    const folder = findFolderById(tree?.folders, folderId);
    const nextOrder = folder?.texts?.length ?? 0;
    try {
      await createText(projectId, folderId, title, nextOrder);
      await refreshTree();
    } catch (err) {
      setTreeError(err.message);
    }
  }, [projectId, tree, refreshTree, findFolderById]);

  const handleDeleteText = useCallback(async (fileId, title) => {
    if (!window.confirm(t("tree.confirm_delete_text", { title }))) return;
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
  }, [projectId, activeFileId, refreshTree]);

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
      const updated = findFolderById(freshTree.folders, selectedItem.id);
      if (updated) setSelectedItem(updated);
    } else {
      const updated = findTextInTree(freshTree.folders, selectedItem.id);
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

  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, []);

  // Map nav section to tree filter
  const treeFilter = navSection === "editor" ? "manuscript"
    : navSection === "outline" ? "all"
    : navSection; // "characters", "locations", "notes"

  const sidebarContent = (
    <>
      {treeLoading && <p style={{ padding: 12, color: "#888" }}>{t("editor.loading_project")}</p>}
      {treeError && <p style={{ padding: 12, color: "red" }}>{treeError}</p>}
      {tree && (
        <ProjectTree
          tree={tree}
          treeFilter={treeFilter}
          activeFileId={activeFileId}
          onSelectFile={handleSelectFile}
          onSelectFolder={handleSelectFolder}
          selectedFolderId={selectedType === "folder" ? selectedItem?.id : null}
          onAddFolder={handleAddFolder}
          onDeleteFolder={handleDeleteFolder}
          onAddText={handleAddText}
          onDeleteText={handleDeleteText}
          onReorder={handleReorder}
          onRenameFolder={handleRenameFolder}
          onRenameText={handleRenameText}
          onChangeFolderIcon={handleChangeFolderIcon}
          onChangeTextIcon={handleChangeTextIcon}
        />
      )}
    </>
  );

  const editorContent = (
    <div style={styles.center}>
      <div>
        {cacheWarning && (
          <div style={styles.banner} role="alert">
            ⚠ {cacheWarning}
            <button
              type="button"
              onClick={() => setCacheWarning(null)}
              style={{ marginLeft: 8, background: "none", border: "none", cursor: "pointer", fontWeight: "bold" }}
              aria-label={t("editor.dismiss_warning")}
            >
              ✕
            </button>
          </div>
        )}
        {activeFileId && (
        <div style={styles.topBar}>
          <FormattingToolbar editor={editorInstance} />
          <button
            type="button"
            style={styles.saveBtn}
            onClick={handleSave}
            disabled={saving || !activeFileId}
          >
            {saving ? t("editor.saving") : t("editor.save")}
          </button>
        </div>
        )}
      </div>

      <div style={styles.editorArea}>
        {!activeFileId && (
          <div style={styles.placeholder}>{t("editor.select_file_placeholder")}</div>
        )}
        {fileLoading && <p style={{ color: "#888" }}>{t("editor.loading_file")}</p>}
        {fileError && <p style={{ color: "red" }}>{fileError}</p>}
        {activeFileId && !fileLoading && !fileError && fileContent != null && (
          <TipTapEditor
            content={fileContent}
            onUpdate={handleEditorUpdate}
            editorRef={setEditorInstance}
          />
        )}
      </div>

      <div style={{ ...styles.statusBar, visibility: activeFileId ? "visible" : "hidden" }} aria-live="polite">
        <span>{wordCount.toLocaleString()} {t("editor.words")}</span>
        <span>{charCount.toLocaleString()} {t("editor.characters")}</span>
        {selectedType === "text" && selectedItem?.target_word_count > 0 && (() => {
          const target = selectedItem.target_word_count;
          const pct = Math.min(Math.round((wordCount / target) * 100), 100);
          const r = pct < 50 ? 220 : Math.round(220 - (pct - 50) * 4);
          const g = pct < 50 ? Math.round(80 + pct * 3) : 200;
          const barColor = `rgb(${r},${g},60)`;
          return (
            <span style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
              <span style={{ width: 100, height: 8, background: "#ddd", borderRadius: 4, overflow: "hidden" }}>
                <span style={{ display: "block", width: `${pct}%`, height: "100%", background: barColor, borderRadius: 4, transition: "width 0.3s" }} />
              </span>
              <span>{pct}%</span>
              <span>{wordCount.toLocaleString()}/{target.toLocaleString()}</span>
            </span>
          );
        })()}
      </div>
    </div>
  );

  const propertiesContent = (
    <div style={{ overflowY: "auto", background: "#fafafa", ...(isMobile ? { flex: 1 } : { width: 260, minWidth: 260, borderLeft: "1px solid #ddd" }) }}>
      {selectedItem && (
        <PropertiesPanel
          item={selectedItem}
          type={selectedType}
          onSave={handleSaveProperties}
        />
      )}
      {activeFileId && (
        <VersionHistoryPanel fileId={activeFileId} onRevert={handleRevert} />
      )}
    </div>
  );

  // ── Mobile layout: one panel at a time with tab bar ────────
  if (isMobile) {
    const tabBtn = (panel, label) => ({
      flex: 1,
      padding: "8px 0",
      border: "none",
      borderBottom: mobilePanel === panel ? "2px solid #4a90d9" : "2px solid transparent",
      background: mobilePanel === panel ? "#fff" : "#f5f5f5",
      color: mobilePanel === panel ? "#4a90d9" : "#666",
      fontWeight: mobilePanel === panel ? 600 : 400,
      fontSize: 13,
      cursor: "pointer",
    });

    return (
      <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, overflow: "hidden" }}>
        <NavBar active={navSection} onChange={setNavSection} onDashboard={onDashboard} onSettings={() => {}} onLogout={onLogout} />
        <div style={{ display: "flex", borderBottom: "1px solid #ddd", flexShrink: 0 }}>
          <button type="button" style={tabBtn("tree", "Tree")} onClick={() => setMobilePanel("tree")}>
            📁 Tree
          </button>
          <button type="button" style={tabBtn("editor", "Editor")} onClick={() => setMobilePanel("editor")}>
            ✏️ Editor
          </button>
          <button type="button" style={tabBtn("properties", "Info")} onClick={() => setMobilePanel("properties")}>
            ℹ️ Info
          </button>
        </div>
        <div style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {mobilePanel === "tree" && <div style={{ flex: 1, overflowY: "auto" }}>{sidebarContent}</div>}
          {mobilePanel === "editor" && editorContent}
          {mobilePanel === "properties" && propertiesContent}
        </div>
      </div>
    );
  }

  // ── Desktop layout: nav sidebar + three columns ────────────
  return (
    <div style={styles.container}>
      <NavSidebar active={navSection} onChange={setNavSection} onDashboard={onDashboard} onSettings={() => {}} onLogout={onLogout} />
      <div style={styles.sidebar}>{sidebarContent}</div>
      {editorContent}
      {(selectedItem || activeFileId) && propertiesContent}
    </div>
  );
}

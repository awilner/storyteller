import { useState, useEffect, useRef, useCallback } from "react";
import { useI18n } from "./I18nContext";
import { useFont } from "./FontContext";
import useIsMobile from "./useIsMobile";
import TopBar from "./TopBar";
import ProjectTree from "./ProjectTree";
import TipTapEditor from "./TipTapEditor";
import FormattingToolbar from "./FormattingToolbar";
import FolderView from "./FolderView";
import VersionHistoryPanel from "./VersionHistoryPanel";
import PropertiesPanel from "./PropertiesPanel";
import CompileDialog from "./CompileDialog";
import ProjectSettings from "./ProjectSettings";
import VersionBadge from "./VersionBadge";
import { findFolderById } from "./treeUtils";
import { fetchProjectTree, fetchFile, saveDraftCache, createVersion, createFolder, deleteFolder, createText, deleteText, updateFolder, updateText, updateProject, reorderTree, emptyTrash, exportScrivener, exportYWriter, duplicateFolder, duplicateText, copyToProject, fetchProjects, fetchUserSettings } from "./api";
import "./EditorView.css";

const DEBOUNCE_MS = 2000;

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

export default function EditorView({ projectId, initialFileId, onLogout, onDashboard, username, onAccount, onSettings }) {
  const t = useI18n();
  const { setProjectFont } = useFont();
  const isMobile = useIsMobile();
  const [mobilePanel, setMobilePanel] = useState("tree");
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
  const [folderWordCount, setFolderWordCount] = useState(0);
  const [folderCharCount, setFolderCharCount] = useState(0);
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
  useEffect(() => {
    if (!tree) return;
    if (activeFileId) {
      const textItem = findTextInTree(tree, activeFileId);
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
      .then((data) => {
        setTree(data);
        setProjectFont(data.settings?.editor_font || "");
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
  const handleCompile = useCallback(() => setCompileOpen(true), []);
  const handleProjectSettings = useCallback(() => setProjectSettingsOpen(true), []);

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
        } catch {
          // silent — don't disrupt the user
        }
      }
    }, autoSaveInterval * 1000);

    return () => { if (autoSaveRef.current) clearInterval(autoSaveRef.current); };
  }, [autoSaveInterval]);

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
            onAddFolder={handleAddFolder}
            onDeleteFolder={handleDeleteFolder}
            onAddText={handleAddText}
            onDeleteText={handleDeleteText}
            onReorder={handleReorder}
            onRenameFolder={handleRenameFolder}
            onRenameText={handleRenameText}
            onChangeFolderIcon={handleChangeFolderIcon}
            onChangeTextIcon={handleChangeTextIcon}
            onEmptyTrash={handleEmptyTrash}
            onDuplicateFolder={handleDuplicateFolder}
            onDuplicateText={handleDuplicateText}
            onCopyToProject={handleCopyToProject}
            otherProjects={otherProjects}
            labels={tree?.labels}
            statuses={tree?.statuses}
            characters={tree?.characters}
            treeSettings={tree?.settings}
            isMobile={isMobile}
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
        {activeFileId && (
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
        {activeFileId && !fileLoading && !fileError && fileContent != null && (
          <TipTapEditor content={fileContent} onUpdate={handleEditorUpdate} editorRef={setEditorInstance} />
        )}
      </div>

      {(() => {
        const showFile = activeFileId;
        const showFolder = !activeFileId && selectedType === "folder" && selectedItem;
        if (!showFile && !showFolder) return <div className="editor-status-bar" style={{ visibility: "hidden" }} />;
        const wc = showFile ? wordCount : folderWordCount;
        const cc = showFile ? charCount : folderCharCount;
        const target = selectedItem?.target_word_count;
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
          </div>
        );
      })()}
    </div>
  );

  const propertiesContent = (
    <div className={isMobile ? "editor-right-panel--mobile" : "editor-right-panel"}>
      {selectedItem && <PropertiesPanel item={selectedItem} type={selectedType} onSave={handleSaveProperties} characters={tree?.characters} labels={tree?.labels} statuses={tree?.statuses} />}
      {activeFileId && <VersionHistoryPanel fileId={activeFileId} onRevert={handleRevert} />}
    </div>
  );

  // ── Mobile layout ──────────────────────────────────────────
  if (isMobile) {
    return (
      <div className="editor-mobile-wrapper">
        <TopBar projectTitle={tree?.title} onHome={onDashboard} username={username} onAccount={onAccount} onSettings={onSettings} onLogout={onLogout} onExportScrivener={handleExportScrivener} onExportYWriter={handleExportYWriter} onCompile={handleCompile} onProjectSettings={handleProjectSettings} />
        <div className="editor-mobile-tabs">
          <button type="button" className={`editor-mobile-tab${mobilePanel === "tree" ? " editor-mobile-tab--active" : ""}`} onClick={() => setMobilePanel("tree")}>📁 Tree</button>
          <button type="button" className={`editor-mobile-tab${mobilePanel === "editor" ? " editor-mobile-tab--active" : ""}`} onClick={() => setMobilePanel("editor")}>✏️ Editor</button>
          <button type="button" className={`editor-mobile-tab${mobilePanel === "properties" ? " editor-mobile-tab--active" : ""}`} onClick={() => setMobilePanel("properties")}>ℹ️ Info</button>
        </div>
        <div className="editor-mobile-body">
          {mobilePanel === "tree" && <div className="editor-mobile-tree">{sidebarContent}</div>}
          {mobilePanel === "editor" && editorContent}
          {mobilePanel === "properties" && propertiesContent}
        </div>
        {compileOpen && <CompileDialog projectId={projectId} tree={tree} onClose={() => setCompileOpen(false)} />}
        {projectSettingsOpen && <ProjectSettings projectId={projectId} settings={tree?.settings} onClose={handleCloseProjectSettings} onRefresh={refreshTree} />}
      </div>
    );
  }

  // ── Desktop layout ─────────────────────────────────────────
  return (
    <div className="editor-desktop-wrapper">
      <TopBar projectTitle={tree?.title} onHome={onDashboard} username={username} onAccount={onAccount} onSettings={onSettings} onLogout={onLogout} onExportScrivener={handleExportScrivener} onExportYWriter={handleExportYWriter} onCompile={handleCompile} onProjectSettings={handleProjectSettings} />
      <div className="editor-desktop-body">
        <div className="editor-sidebar">{sidebarContent}</div>
        {editorContent}
        {(selectedItem || activeFileId) && propertiesContent}
      </div>
      {compileOpen && <CompileDialog projectId={projectId} tree={tree} onClose={() => setCompileOpen(false)} />}
      {projectSettingsOpen && <ProjectSettings projectId={projectId} settings={tree?.settings} onClose={handleCloseProjectSettings} onRefresh={refreshTree} />}
    </div>
  );
}

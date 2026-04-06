import { useState, useEffect, useCallback } from "react";
import { useI18n } from "./I18nContext";
import LayoutEditor, { DEFAULT_LAYOUT_SETTINGS } from "./LayoutEditor";
import { findFolderById, getRootFolders, getAllNonTrashFolders, findDefaultRoot } from "./treeUtils";
import {
  fetchCompileLayouts,
  compileManuscript,
  updateFolder,
  updateText,
} from "./api";
import "./CompileDialog.css";

const FORMATS = [
  { value: "docx", key: "compile.format_docx" },
  { value: "rtf", key: "compile.format_rtf" },
  { value: "markdown", key: "compile.format_markdown" },
  { value: "pdf", key: "compile.format_pdf" },
  { value: "latex", key: "compile.format_latex" },
  { value: "epub", key: "compile.format_epub" },
  { value: "mobi", key: "compile.format_mobi" },
];

function CompileTreeNode({ folder, projectId, onToggle, parentIncluded }) {
  const included = folder.include_in_compile;
  const effectivelyIncluded = parentIncluded && included;
  const textItems = (folder.items || []).filter((item) => item.file_type === "text").map((item) => ({ ...item, _kind: "text" }));
  const childFolders = (folder.children || []).filter((c) => !c.is_trash).map((c) => ({ ...c, _kind: "folder" }));
  const combined = [...textItems, ...childFolders].sort((a, b) => a.order - b.order);

  return (
    <div className="compile-tree-node">
      <div className={`compile-tree-item compile-tree-item--folder${!parentIncluded ? " compile-tree-item--dimmed" : ""}`}>
        <input type="checkbox" checked={included} onChange={() => onToggle("folder", folder.id, !included)} disabled={!parentIncluded} />
        <span>📁 {folder.title}</span>
      </div>
      {combined.map((item) =>
        item._kind === "folder" ? (
          <CompileTreeNode key={`f-${item.id}`} folder={item} projectId={projectId} onToggle={onToggle} parentIncluded={effectivelyIncluded} />
        ) : (
          <div key={`t-${item.id}`} className={`compile-tree-item${!effectivelyIncluded ? " compile-tree-item--dimmed" : ""}`} style={{ paddingLeft: 16 }}>
            <input type="checkbox" checked={item.include_in_compile} onChange={() => onToggle("text", item.id, !item.include_in_compile)} disabled={!effectivelyIncluded} />
            <span>📄 {item.title}</span>
          </div>
        )
      )}
    </div>
  );
}

export default function CompileDialog({ projectId, tree, onClose }) {
  const t = useI18n();
  const rootFolders = getRootFolders(tree);
  const allFolders = getAllNonTrashFolders(tree?.folders || []);
  const defaultRoot = findDefaultRoot(tree);
  const [rootFolderId, setRootFolderId] = useState(defaultRoot?.id || null);
  const [frontMatterEnabled, setFrontMatterEnabled] = useState(false);
  const [frontMatterFolderId, setFrontMatterFolderId] = useState(null);
  const [backMatterEnabled, setBackMatterEnabled] = useState(false);
  const [backMatterFolderId, setBackMatterFolderId] = useState(null);
  const [format, setFormat] = useState("docx");
  const [layouts, setLayouts] = useState([]);
  const [selectedLayoutId, setSelectedLayoutId] = useState(null);
  // Local-only layout overrides (not persisted)
  const [localSettings, setLocalSettings] = useState(null);
  const [localTree, setLocalTree] = useState(tree);
  const [compiling, setCompiling] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => { fetchCompileLayouts(projectId).then(setLayouts).catch(() => setLayouts([])); }, [projectId]);
  useEffect(() => { setLocalTree(tree); }, [tree]);

  // When layout selection changes, reset local overrides to the layout's saved settings
  useEffect(() => {
    if (selectedLayoutId) {
      const layout = layouts.find((l) => l.id === selectedLayoutId);
      setLocalSettings(layout ? { ...DEFAULT_LAYOUT_SETTINGS, ...layout.settings } : { ...DEFAULT_LAYOUT_SETTINGS });
    } else {
      setLocalSettings({ ...DEFAULT_LAYOUT_SETTINGS });
    }
  }, [selectedLayoutId, layouts]);

  const updateLocalTree = useCallback((type, id, value) => {
    setLocalTree((prev) => {
      if (!prev) return prev;
      const clone = JSON.parse(JSON.stringify(prev));
      if (type === "folder") {
        const folder = findFolderById(clone.folders, id);
        if (folder) folder.include_in_compile = value;
      } else {
        const updateInFolders = (folders) => {
          for (const f of folders || []) {
            for (const item of f.items || []) { if (item.id === id) { item.include_in_compile = value; return true; } }
            if (updateInFolders(f.children)) return true;
          }
          return false;
        };
        updateInFolders(clone.folders);
      }
      return clone;
    });
  }, []);

  const handleToggle = useCallback((type, id, value) => {
    updateLocalTree(type, id, value);
    const fn = type === "folder" ? updateFolder : updateText;
    fn(projectId, id, { include_in_compile: value }).catch(() => updateLocalTree(type, id, !value));
  }, [projectId, updateLocalTree]);

  // Local-only layout change (no persistence)
  const handleLayoutFieldChange = useCallback((key, value) => {
    setLocalSettings((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleCompile = useCallback(async () => {
    setCompiling(true);
    setError(null);
    try {
      const params = { format, root_folder_id: rootFolderId };
      if (selectedLayoutId) params.layout_id = selectedLayoutId;
      if (frontMatterEnabled && frontMatterFolderId) params.front_matter_folder_id = frontMatterFolderId;
      if (backMatterEnabled && backMatterFolderId) params.back_matter_folder_id = backMatterFolderId;
      const res = await compileManuscript(projectId, params);
      const disposition = res.headers.get("Content-Disposition");
      const filename = disposition?.match(/filename="(.+)"/)?.[1] || `manuscript.${format}`;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      onClose();
    } catch (err) {
      setError(t("compile.error", { error: err.message }));
    } finally {
      setCompiling(false);
    }
  }, [format, rootFolderId, selectedLayoutId, frontMatterEnabled, frontMatterFolderId, backMatterEnabled, backMatterFolderId, projectId, t, onClose]);

  const compileRoot = rootFolderId ? findFolderById(localTree?.folders, rootFolderId) : null;

  return (
    <div className="compile-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="compile-modal" role="dialog" aria-modal="true">
        <h3>{t("compile.title")}</h3>
        <div className="compile-body">
          <div className="compile-left">
            <div className="compile-section">
              <span className="compile-section-label">{t("compile.root_folder")}</span>
              <select className="compile-select" value={rootFolderId || ""} onChange={(e) => setRootFolderId(Number(e.target.value))}>
                {rootFolders.map((f) => <option key={f.id} value={f.id}>{f.title}</option>)}
              </select>
            </div>
            {compileRoot && <CompileTreeNode folder={compileRoot} projectId={projectId} onToggle={handleToggle} parentIncluded={true} />}
          </div>
          <div className="compile-right">
            <div className="compile-section">
              <span className="compile-section-label">{t("compile.format")}</span>
              <select className="compile-select" value={format} onChange={(e) => setFormat(e.target.value)}>
                {FORMATS.map((f) => <option key={f.value} value={f.value}>{t(f.key)}</option>)}
              </select>
            </div>
            <div className="compile-section">
              <div className="compile-toggle-row">
                <label><input type="checkbox" checked={frontMatterEnabled} onChange={(e) => setFrontMatterEnabled(e.target.checked)} /> {t("compile.enable_front_matter")}</label>
              </div>
              {frontMatterEnabled && (
                <select className="compile-select" value={frontMatterFolderId || ""} onChange={(e) => setFrontMatterFolderId(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">—</option>
                  {allFolders.map((f) => <option key={f.id} value={f.id}>{f.title}</option>)}
                </select>
              )}
            </div>
            <div className="compile-section">
              <div className="compile-toggle-row">
                <label><input type="checkbox" checked={backMatterEnabled} onChange={(e) => setBackMatterEnabled(e.target.checked)} /> {t("compile.enable_back_matter")}</label>
              </div>
              {backMatterEnabled && (
                <select className="compile-select" value={backMatterFolderId || ""} onChange={(e) => setBackMatterFolderId(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">—</option>
                  {allFolders.map((f) => <option key={f.id} value={f.id}>{f.title}</option>)}
                </select>
              )}
            </div>
            <div className="compile-section">
              <span className="compile-section-label">{t("compile.layout")}</span>
              <select className="compile-select" value={selectedLayoutId || ""} onChange={(e) => setSelectedLayoutId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">{t("compile.default_layout")}</option>
                {layouts.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
            {localSettings && (
              <LayoutEditor settings={localSettings} onChange={handleLayoutFieldChange} t={t} />
            )}
          </div>
        </div>
        <div className="compile-footer">
          {error && <span className="compile-error">{error}</span>}
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={compiling}>{t("dashboard.cancel")}</button>
          <button type="button" className="btn btn-primary" onClick={handleCompile} disabled={compiling || !rootFolderId}>
            {compiling ? t("compile.compiling") : t("compile.compile_btn")}
          </button>
        </div>
      </div>
    </div>
  );
}

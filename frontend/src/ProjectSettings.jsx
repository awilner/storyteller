import { useState, useEffect, useCallback, useRef } from "react";
import { useI18n } from "./I18nContext";
import LabelManager from "./LabelManager";
import StatusManager from "./StatusManager";
import LayoutEditor, { DEFAULT_LAYOUT_SETTINGS } from "./LayoutEditor";
import { updateProject, fetchCompileLayouts, createCompileLayout, updateCompileLayout, deleteCompileLayout } from "./api";
import "./ProjectSettings.css";

function LayoutManager({ projectId, t }) {
  const [layouts, setLayouts] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [error, setError] = useState(null);
  const debounceRef = useRef(null);

  const load = useCallback(async () => {
    try { setLayouts(await fetchCompileLayouts(projectId)); } catch (e) { setError(e.message); }
  }, [projectId]);
  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    try {
      const created = await createCompileLayout(projectId, { name: "New Layout", settings: { ...DEFAULT_LAYOUT_SETTINGS } });
      setLayouts((prev) => [...prev, created]);
      setSelectedId(created.id);
    } catch (e) { setError(e.message); }
  };

  const handleDelete = async (id) => {
    try {
      await deleteCompileLayout(projectId, id);
      setLayouts((prev) => prev.filter((l) => l.id !== id));
      if (selectedId === id) setSelectedId(null);
    } catch (e) { setError(e.message); }
  };

  const persistField = useCallback((id, payload) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      updateCompileLayout(projectId, id, payload).catch(() => {});
    }, 600);
  }, [projectId]);

  const handleNameChange = (id, name) => {
    setLayouts((prev) => prev.map((l) => l.id === id ? { ...l, name } : l));
    persistField(id, { name });
  };

  const handleSettingsChange = (id, key, value) => {
    setLayouts((prev) => prev.map((l) => {
      if (l.id !== id) return l;
      const next = { ...DEFAULT_LAYOUT_SETTINGS, ...l.settings, [key]: value };
      return { ...l, settings: next };
    }));
    const layout = layouts.find((l) => l.id === id);
    const nextSettings = { ...DEFAULT_LAYOUT_SETTINGS, ...(layout?.settings || {}), [key]: value };
    persistField(id, { settings: nextSettings });
  };

  const selected = layouts.find((l) => l.id === selectedId);

  return (
    <div className="layout-manager">
      <div className="layout-manager-sidebar">
        {layouts.map((l) => (
          <div key={l.id} className={`layout-manager-item${selectedId === l.id ? " layout-manager-item--active" : ""}`} onClick={() => setSelectedId(l.id)}>
            <span className="layout-manager-item-name">{l.name}</span>
            <button type="button" className="label-manager-btn label-manager-btn--danger" onClick={(e) => { e.stopPropagation(); handleDelete(l.id); }} aria-label="Delete">✕</button>
          </div>
        ))}
        <button type="button" className="label-manager-btn" style={{ marginTop: 8 }} onClick={handleAdd}>{t("compile.new_layout")}</button>
      </div>
      <div className="layout-manager-content">
        {selected ? (
          <>
            <div className="psettings-field" style={{ marginBottom: 12 }}>
              <label>{t("compile.layout_name")}</label>
              <input type="text" value={selected.name} onChange={(e) => handleNameChange(selected.id, e.target.value)}
                style={{ flex: 1, padding: "4px 8px", border: "1px solid #ccc", borderRadius: 4, fontSize: 13 }} />
            </div>
            <LayoutEditor settings={{ ...DEFAULT_LAYOUT_SETTINGS, ...selected.settings }} onChange={(key, value) => handleSettingsChange(selected.id, key, value)} t={t} />
          </>
        ) : (
          <div style={{ color: "#999", fontSize: 13, padding: 12 }}>Select a layout or create a new one.</div>
        )}
      </div>
      {error && <div style={{ color: "#c44", fontSize: 12, marginTop: 4 }}>{error}</div>}
    </div>
  );
}

export default function ProjectSettings({ projectId, settings, onClose, onRefresh }) {
  const t = useI18n();
  const [tab, setTab] = useState("labels");
  const [iconBgSource, setIconBgSource] = useState(settings?.tree_icon_bg_source || "");
  const [textColourSource, setTextColourSource] = useState(settings?.tree_text_colour_source || "");
  const [textBgSource, setTextBgSource] = useState(settings?.tree_text_bg_source || "");

  const handleTreeSetting = useCallback(async (key, value) => {
    const setters = { tree_icon_bg_source: setIconBgSource, tree_text_colour_source: setTextColourSource, tree_text_bg_source: setTextBgSource };
    setters[key](value);
    try {
      await updateProject(projectId, { settings: { ...settings, [key]: value } });
      if (onRefresh) onRefresh();
    } catch { /* ignore */ }
  }, [projectId, settings, onRefresh]);

  const sourceOptions = (
    <>
      <option value="">{t("settings.source_nothing")}</option>
      <option value="pov">{t("settings.colour_source_pov")}</option>
      <option value="label">{t("settings.colour_source_label")}</option>
      <option value="status">{t("settings.colour_source_status")}</option>
    </>
  );

  return (
    <div className="psettings-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="psettings-modal">
        <h3>{t("topbar.project_settings")}</h3>
        <div className="psettings-tabs">
          <button type="button" className={`psettings-tab${tab === "labels" ? " psettings-tab--active" : ""}`} onClick={() => setTab("labels")}>{t("labels.title")}</button>
          <button type="button" className={`psettings-tab${tab === "statuses" ? " psettings-tab--active" : ""}`} onClick={() => setTab("statuses")}>{t("statuses.title")}</button>
          <button type="button" className={`psettings-tab${tab === "tree" ? " psettings-tab--active" : ""}`} onClick={() => setTab("tree")}>{t("settings.tree_tab")}</button>
          <button type="button" className={`psettings-tab${tab === "layouts" ? " psettings-tab--active" : ""}`} onClick={() => setTab("layouts")}>{t("settings.layouts_tab")}</button>
        </div>
        <div className="psettings-body">
          {tab === "labels" && <LabelManager projectId={projectId} onClose={() => {}} embedded />}
          {tab === "statuses" && <StatusManager projectId={projectId} onClose={() => {}} embedded />}
          {tab === "tree" && (
            <div className="psettings-colour-section">
              <div className="psettings-field"><label>{t("settings.tree_icon_bg")}</label><select value={iconBgSource} onChange={(e) => handleTreeSetting("tree_icon_bg_source", e.target.value)}>{sourceOptions}</select></div>
              <div className="psettings-field"><label>{t("settings.tree_text_colour")}</label><select value={textColourSource} onChange={(e) => handleTreeSetting("tree_text_colour_source", e.target.value)}>{sourceOptions}</select></div>
              <div className="psettings-field"><label>{t("settings.tree_text_bg")}</label><select value={textBgSource} onChange={(e) => handleTreeSetting("tree_text_bg_source", e.target.value)}>{sourceOptions}</select></div>
            </div>
          )}
          {tab === "layouts" && <LayoutManager projectId={projectId} t={t} />}
        </div>
        <div className="psettings-footer">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

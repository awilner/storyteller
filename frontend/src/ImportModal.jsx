import { useState, useRef } from "react";
import { useI18n } from "./I18nContext";
import "./ImportModal.css";

const FORMATS = [
  { value: "scrivener", label: "Scrivener (.scriv.zip)" },
  { value: "ywriter", label: "yWriter7 (.yw7)" },
];

export default function ImportModal({ onClose, onImported }) {
  const t = useI18n();
  const [format, setFormat] = useState("scrivener");
  const [file, setFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef();

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const { importScrivener, importYWriter } = await import("./api");
      let project;
      if (format === "scrivener") {
        project = await importScrivener(file);
      } else if (format === "ywriter") {
        project = await importYWriter(file);
      }
      onImported(project);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setImporting(false);
    }
  };

  const acceptMap = { scrivener: ".zip", ywriter: ".yw7" };

  return (
    <div className="import-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="import-modal" role="dialog" aria-modal="true">
        <h3>{t("import.title") || "Import Project"}</h3>
        <label className="import-label">
          <span className="import-label-text">{t("import.format") || "Format"}</span>
          <select className="import-select" value={format}
            onChange={(e) => { setFormat(e.target.value); setFile(null); if (fileRef.current) fileRef.current.value = ""; }}>
            {FORMATS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </label>
        <label className="import-label" style={{ marginBottom: 16 }}>
          <span className="import-label-text">{t("import.file") || "File"}</span>
          <input ref={fileRef} type="file" accept={acceptMap[format] || "*"}
            onChange={(e) => setFile(e.target.files?.[0] || null)} className="import-file-input" />
        </label>
        {error && <p className="error-text mb-12">{error}</p>}
        <div className="import-actions">
          <button type="button" onClick={onClose} disabled={importing} className="btn btn-ghost">
            {t("dashboard.cancel") || "Cancel"}
          </button>
          <button type="button" onClick={handleImport} disabled={importing || !file} className="btn btn-primary">
            {importing ? (t("dashboard.importing") || "Importing…") : (t("import.import_btn") || "Import")}
          </button>
        </div>
      </div>
    </div>
  );
}

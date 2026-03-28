import { useState, useRef } from "react";
import { useI18n } from "./I18nContext";

const FORMATS = [
  { value: "scrivener", label: "Scrivener (.scriv.zip)" },
  { value: "ywriter", label: "yWriter7 (.yw7.zip)" },
];

const overlayStyle = {
  position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
};
const modalStyle = {
  background: "#fff", borderRadius: 8, padding: 24, width: 400,
  maxWidth: "90vw", boxShadow: "0 4px 24px rgba(0,0,0,0.2)",
};
const btnBase = {
  borderRadius: 4, padding: "8px 18px", fontWeight: 600, fontSize: 13, cursor: "pointer",
};

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

  const acceptMap = { scrivener: ".zip", ywriter: ".zip" };

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={modalStyle} role="dialog" aria-modal="true">
        <h3 style={{ margin: "0 0 16px" }}>{t("import.title") || "Import Project"}</h3>

        <label style={{ display: "block", marginBottom: 12 }}>
          <span style={{ display: "block", marginBottom: 4, fontSize: 13, color: "#555" }}>
            {t("import.format") || "Format"}
          </span>
          <select
            value={format}
            onChange={(e) => { setFormat(e.target.value); setFile(null); if (fileRef.current) fileRef.current.value = ""; }}
            style={{ width: "100%", padding: "8px 10px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14, boxSizing: "border-box" }}
          >
            {FORMATS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </label>

        <label style={{ display: "block", marginBottom: 16 }}>
          <span style={{ display: "block", marginBottom: 4, fontSize: 13, color: "#555" }}>
            {t("import.file") || "File"}
          </span>
          <input
            ref={fileRef}
            type="file"
            accept={acceptMap[format] || "*"}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            style={{ width: "100%", fontSize: 14, boxSizing: "border-box" }}
          />
        </label>

        {error && <p style={{ color: "red", fontSize: 13, margin: "0 0 12px" }}>{error}</p>}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" onClick={onClose} disabled={importing}
            style={{ ...btnBase, border: "1px solid #ccc", background: "#fff", color: "#333" }}>
            {t("dashboard.cancel") || "Cancel"}
          </button>
          <button type="button" onClick={handleImport} disabled={importing || !file}
            style={{ ...btnBase, border: "1px solid #28a745", background: importing ? "#6c9" : "#28a745", color: "#fff", opacity: (!file || importing) ? 0.6 : 1, cursor: (!file || importing) ? "not-allowed" : "pointer" }}>
            {importing ? (t("dashboard.importing") || "Importing…") : (t("import.import_btn") || "Import")}
          </button>
        </div>
      </div>
    </div>
  );
}

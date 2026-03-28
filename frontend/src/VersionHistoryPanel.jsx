import { useState, useEffect } from "react";
import { fetchVersions, fetchVersion, revertVersion } from "./api";
import { useI18n } from "./I18nContext";

export default function VersionHistoryPanel({ fileId, onRevert }) {
  const t = useI18n();
  const [open, setOpen] = useState(false);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [previewContent, setPreviewContent] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [reverting, setReverting] = useState(false);

  useEffect(() => {
    if (!open || !fileId) return;
    setLoading(true);
    setError(null);
    fetchVersions(fileId)
      .then((data) => setVersions(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [fileId, open]);

  const handleSelectVersion = async (version) => {
    if (selectedVersion?.id === version.id) {
      setSelectedVersion(null);
      setPreviewContent(null);
      return;
    }
    setSelectedVersion(version);
    setPreviewLoading(true);
    try {
      const data = await fetchVersion(fileId, version.id);
      setPreviewContent(data.content);
    } catch (err) {
      setPreviewContent(t("versions.error_loading", { error: err.message }));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleRevert = async () => {
    if (!selectedVersion) return;
    if (!window.confirm(t("versions.confirm_revert"))) return;
    setReverting(true);
    try {
      await revertVersion(fileId, selectedVersion.id);
      setSelectedVersion(null);
      setPreviewContent(null);
      onRevert?.();
    } catch (err) {
      setError(t("versions.revert_failed", { error: err.message }));
    } finally {
      setReverting(false);
    }
  };

  return (
    <div style={{ borderBottom: "1px solid #ddd" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%",
          padding: "8px 12px",
          background: "#f5f5f5",
          border: "none",
          borderBottom: "1px solid #ddd",
          cursor: "pointer",
          textAlign: "left",
          fontWeight: "bold",
        }}
      >
        {open ? "▾" : "▸"} {t("versions.title")}
      </button>

      {open && (
        <div style={{ padding: 8 }}>
          {loading && <p style={{ color: "#888" }}>{t("versions.loading")}</p>}
          {error && <p style={{ color: "red" }}>{error}</p>}
          {!loading && !error && versions.length === 0 && (
            <p style={{ color: "#888" }}>{t("versions.no_versions")}</p>
          )}
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {versions.map((v) => (
              <li
                key={v.id}
                onClick={() => handleSelectVersion(v)}
                style={{
                  padding: "6px 8px",
                  cursor: "pointer",
                  background: selectedVersion?.id === v.id ? "#e0edff" : "transparent",
                  borderRadius: 4,
                  marginBottom: 2,
                  fontSize: 13,
                }}
              >
                <div>{new Date(v.created_at).toLocaleString()}</div>
                <div style={{ color: "#888", fontSize: 12 }}>{v.content_length} {t("versions.chars")}</div>
              </li>
            ))}
          </ul>

          {selectedVersion && (
            <div style={{ marginTop: 8 }}>
              <button
                onClick={handleRevert}
                disabled={reverting}
                style={{
                  padding: "4px 10px",
                  cursor: reverting ? "not-allowed" : "pointer",
                  marginBottom: 8,
                }}
              >
                {reverting ? t("versions.reverting") : t("versions.revert")}
              </button>
              {previewLoading ? (
                <p style={{ color: "#888" }}>{t("versions.loading_preview")}</p>
              ) : (
                <pre
                  style={{
                    background: "#f9f9f9",
                    border: "1px solid #ddd",
                    padding: 8,
                    borderRadius: 4,
                    maxHeight: 300,
                    overflow: "auto",
                    fontSize: 12,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {previewContent}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

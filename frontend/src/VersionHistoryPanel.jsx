import { useState, useEffect } from "react";
import { fetchVersions, fetchVersion, revertVersion } from "./api";
import { useI18n } from "./I18nContext";
import "./VersionHistoryPanel.css";

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
    <div className="versions-wrapper">
      <button className="versions-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} {t("versions.title")}
      </button>
      {open && (
        <div className="versions-body">
          {loading && <p className="loading-text">{t("versions.loading")}</p>}
          {error && <p className="error-text">{error}</p>}
          {!loading && !error && versions.length === 0 && (
            <p className="muted-text">{t("versions.no_versions")}</p>
          )}
          <ul className="versions-list">
            {versions.map((v) => (
              <li key={v.id} onClick={() => handleSelectVersion(v)}
                className={`versions-item${selectedVersion?.id === v.id ? " versions-item--selected" : ""}`}>
                <div>{new Date(v.created_at).toLocaleString()}</div>
                <div className="versions-meta">{v.content_length} {t("versions.chars")}</div>
              </li>
            ))}
          </ul>
          {selectedVersion && (
            <div className="mt-8">
              <button onClick={handleRevert} disabled={reverting} className="btn btn-small mb-8">
                {reverting ? t("versions.reverting") : t("versions.revert")}
              </button>
              {previewLoading ? (
                <p className="loading-text">{t("versions.loading_preview")}</p>
              ) : (
                <pre className="versions-preview">{previewContent}</pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect, useCallback } from "react";
import { useI18n } from "./I18nContext";
import "./PropertiesPanel.css";

const DEBOUNCE_MS = 800;

export default function PropertiesPanel({ item, type, onSave }) {
  const t = useI18n();
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!item) return;
    setForm({
      title: item.title || "",
      description: item.description || "",
      notes: item.notes || "",
      tags: Array.isArray(item.tags) ? item.tags.join(", ") : "",
      target_word_count: item.target_word_count ?? "",
    });
    setDirty(false);
    setError(null);
  }, [item?.id]);

  const handleChange = useCallback((field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setDirty(true);
  }, []);

  const handleSave = useCallback(async () => {
    if (!onSave || !dirty) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        title: form.title,
        description: form.description,
        notes: form.notes,
        tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
        target_word_count: form.target_word_count === "" ? null : Number(form.target_word_count),
      };
      await onSave(payload);
      setDirty(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }, [form, dirty, onSave]);

  if (!item) return null;
  const label = type === "folder" ? t("properties.folder_properties") : t("properties.text_properties");

  return (
    <div className="props-panel">
      <h3 className="props-heading">{label}</h3>
      <div className="props-field">
        <label className="props-label" htmlFor="prop-title">{t("properties.title")}</label>
        <input id="prop-title" className="props-input" value={form.title} onChange={(e) => handleChange("title", e.target.value)} />
      </div>
      <div className="props-field">
        <label className="props-label" htmlFor="prop-desc">{t("properties.description")}</label>
        <textarea id="prop-desc" className="props-textarea" value={form.description} onChange={(e) => handleChange("description", e.target.value)} />
      </div>
      <div className="props-field">
        <label className="props-label" htmlFor="prop-notes">{t("properties.notes")}</label>
        <textarea id="prop-notes" className="props-textarea" value={form.notes} onChange={(e) => handleChange("notes", e.target.value)} />
      </div>
      <div className="props-field">
        <label className="props-label" htmlFor="prop-tags">{t("properties.tags")}</label>
        <input id="prop-tags" className="props-input" value={form.tags} onChange={(e) => handleChange("tags", e.target.value)} />
      </div>
      <div className="props-field">
        <label className="props-label" htmlFor="prop-wc">{t("properties.target_word_count")}</label>
        <input id="prop-wc" type="number" min="0" className="props-input" value={form.target_word_count} onChange={(e) => handleChange("target_word_count", e.target.value)} />
      </div>
      <button type="button" disabled={!dirty || saving} onClick={handleSave}
        className={`props-save-btn ${dirty ? "props-save-btn--active" : "props-save-btn--inactive"}`}>
        {saving ? t("properties.saving") : t("properties.update")}
      </button>
      {error && <div className="props-error">{error}</div>}
      {!dirty && !error && <div className="props-status">{t("properties.all_saved")}</div>}
    </div>
  );
}

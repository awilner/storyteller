import { useState, useEffect, useCallback } from "react";
import { useI18n } from "./I18nContext";

const styles = {
  panel: {
    padding: "12px",
    fontFamily: "system-ui",
    fontSize: 13,
  },
  heading: { fontSize: 14, fontWeight: 700, margin: "0 0 12px" },
  field: { marginBottom: 10 },
  label: { display: "block", fontWeight: 600, marginBottom: 3, fontSize: 12, color: "#555" },
  input: {
    width: "100%",
    padding: "4px 6px",
    fontSize: 13,
    border: "1px solid #ccc",
    borderRadius: 4,
    boxSizing: "border-box",
  },
  textarea: {
    width: "100%",
    padding: "4px 6px",
    fontSize: 13,
    border: "1px solid #ccc",
    borderRadius: 4,
    boxSizing: "border-box",
    minHeight: 60,
    resize: "vertical",
    fontFamily: "system-ui",
  },
  status: { fontSize: 11, color: "#888", marginTop: 4 },
  error: { fontSize: 11, color: "#c44", marginTop: 4 },
};

const DEBOUNCE_MS = 800;

export default function PropertiesPanel({ item, type, onSave }) {
  const t = useI18n();
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [dirty, setDirty] = useState(false);

  // Reset form when item changes
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
        tags: form.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
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
    <div style={styles.panel}>
      <h3 style={styles.heading}>{label}</h3>

      <div style={styles.field}>
        <label style={styles.label} htmlFor="prop-title">{t("properties.title")}</label>
        <input
          id="prop-title"
          style={styles.input}
          value={form.title}
          onChange={(e) => handleChange("title", e.target.value)}
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label} htmlFor="prop-desc">{t("properties.description")}</label>
        <textarea
          id="prop-desc"
          style={styles.textarea}
          value={form.description}
          onChange={(e) => handleChange("description", e.target.value)}
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label} htmlFor="prop-notes">{t("properties.notes")}</label>
        <textarea
          id="prop-notes"
          style={styles.textarea}
          value={form.notes}
          onChange={(e) => handleChange("notes", e.target.value)}
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label} htmlFor="prop-tags">{t("properties.tags")}</label>
        <input
          id="prop-tags"
          style={styles.input}
          value={form.tags}
          onChange={(e) => handleChange("tags", e.target.value)}
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label} htmlFor="prop-wc">{t("properties.target_word_count")}</label>
        <input
          id="prop-wc"
          type="number"
          min="0"
          style={styles.input}
          value={form.target_word_count}
          onChange={(e) => handleChange("target_word_count", e.target.value)}
        />
      </div>

      <button
        type="button"
        disabled={!dirty || saving}
        onClick={handleSave}
        style={{
          padding: "5px 16px",
          cursor: dirty && !saving ? "pointer" : "default",
          border: "1px solid #ccc",
          borderRadius: 4,
          background: dirty ? "#4a90d9" : "#e0e0e0",
          color: dirty ? "#fff" : "#888",
          fontWeight: 600,
          fontSize: 13,
          width: "100%",
        }}
      >
        {saving ? t("properties.saving") : t("properties.update")}
      </button>

      {error && <div style={styles.error}>{error}</div>}
      {!dirty && !error && <div style={styles.status}>{t("properties.all_saved")}</div>}
    </div>
  );
}

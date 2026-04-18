import { useState, useEffect, useCallback } from "react";
import { useI18n } from "./I18nContext";
import "./PropertiesPanel.css";

const DEBOUNCE_MS = 800;

function ColourDot({ colour }) {
  if (!colour) return null;
  return (
    <span style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%", backgroundColor: colour, marginRight: 6, verticalAlign: "middle" }} />
  );
}

export default function PropertiesPanel({ item, type, onSave, characters, labels, statuses }) {
  const t = useI18n();
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [dirty, setDirty] = useState(false);

  // Reset form when the item changes or when its metadata is updated
  // externally (e.g. a collaborator deletes a label, causing the tree
  // to refresh with label: null).
  const itemFingerprint = item
    ? `${item.id}|${item.title}|${item.label ?? ""}|${item.status ?? ""}|${item.pov_character ?? ""}|${item.description ?? ""}|${item.colour ?? ""}`
    : "";

  useEffect(() => {
    if (!item) return;
    setForm({
      title: item.title || "",
      description: item.description || "",
      notes: item.notes || "",
      tags: Array.isArray(item.tags) ? item.tags.join(", ") : "",
      target_word_count: item.target_word_count ?? "",
      pov_character: item.pov_character ?? "",
      label: item.label ?? "",
      status: item.status ?? "",
      colour: item.colour || "",
    });
    setDirty(false);
    setError(null);
  }, [itemFingerprint]);

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
        pov_character: form.pov_character === "" ? null : Number(form.pov_character),
        label: form.label === "" ? null : Number(form.label),
        status: form.status === "" ? null : Number(form.status),
      };
      if (item?.file_type === "character" || item?._data?.file_type === "character") {
        payload.colour = form.colour;
      }
      await onSave(payload);
      setDirty(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }, [form, dirty, onSave, item]);

  if (!item) return null;
  const label = type === "folder" ? t("properties.folder_properties") : t("properties.text_properties");
  const isCharacter = item?.file_type === "character" || item?._data?.file_type === "character";
  const fileType = item?.file_type || item?._data?.file_type || "text";
  const isTextType = type === "folder" || fileType === "text";
  const readOnly = !onSave;

  return (
    <div className="props-panel">
      <h3 className="props-heading">{label}</h3>
      <div className="props-field">
        <label className="props-label" htmlFor="prop-title">{t("properties.title")}</label>
        <input id="prop-title" className="props-input" value={form.title} onChange={(e) => handleChange("title", e.target.value)} disabled={readOnly} />
      </div>
      <div className="props-field">
        <label className="props-label" htmlFor="prop-desc">{t("properties.description")}</label>
        <textarea id="prop-desc" className="props-textarea" value={form.description} onChange={(e) => handleChange("description", e.target.value)} disabled={readOnly} />
      </div>
      <div className="props-field">
        <label className="props-label" htmlFor="prop-notes">{t("properties.notes")}</label>
        <textarea id="prop-notes" className="props-textarea" value={form.notes} onChange={(e) => handleChange("notes", e.target.value)} disabled={readOnly} />
      </div>
      <div className="props-field">
        <label className="props-label" htmlFor="prop-tags">{t("properties.tags")}</label>
        <input id="prop-tags" className="props-input" value={form.tags} onChange={(e) => handleChange("tags", e.target.value)} disabled={readOnly} />
      </div>
      {isTextType && (
        <div className="props-field">
          <label className="props-label" htmlFor="prop-wc">{t("properties.target_word_count")}</label>
          <input id="prop-wc" type="number" min="0" className="props-input" value={form.target_word_count} onChange={(e) => handleChange("target_word_count", e.target.value)} disabled={readOnly} />
        </div>
      )}

      {/* POV Character — only for folders and text files */}
      {isTextType && (
        <div className="props-field">
          <label className="props-label" htmlFor="prop-pov">{t("properties.pov")}</label>
          <select id="prop-pov" className="props-input" value={form.pov_character} onChange={(e) => handleChange("pov_character", e.target.value)} disabled={readOnly}>
            <option value="">{t("properties.none_option")}</option>
            {(characters || []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Label — only for folders and text files */}
      {isTextType && (
        <div className="props-field">
          <label className="props-label" htmlFor="prop-label">{t("properties.label")}</label>
          <select id="prop-label" className="props-input" value={form.label} onChange={(e) => handleChange("label", e.target.value)} disabled={readOnly}>
            <option value="">{t("properties.none_option")}</option>
            {(labels || []).map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Status — only for folders and text files */}
      {isTextType && (
        <div className="props-field">
          <label className="props-label" htmlFor="prop-status">{t("properties.status")}</label>
          <select id="prop-status" className="props-input" value={form.status} onChange={(e) => handleChange("status", e.target.value)} disabled={readOnly}>
            <option value="">{t("properties.none_option")}</option>
            {(statuses || []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Colour for character items */}
      {isCharacter && (
        <div className="props-field">
          <label className="props-label" htmlFor="prop-colour">{t("properties.colour")}</label>
          <input id="prop-colour" type="color" className="props-input props-colour-input" value={form.colour || "#000000"} onChange={(e) => handleChange("colour", e.target.value)} disabled={readOnly} />
        </div>
      )}

      {!readOnly && (
        <button type="button" disabled={!dirty || saving} onClick={handleSave}
          className={`props-save-btn ${dirty ? "props-save-btn--active" : "props-save-btn--inactive"}`}>
          {saving ? t("properties.saving") : t("properties.update")}
        </button>
      )}
      {!readOnly && error && <div className="props-error">{error}</div>}
      {!readOnly && !dirty && !error && <div className="props-status">{t("properties.all_saved")}</div>}
    </div>
  );
}

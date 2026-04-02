import { useState, useEffect } from "react";
import { useI18n } from "./I18nContext";
import { useFont, FONT_OPTIONS } from "./FontContext";
import { updateProject } from "./api";

export default function ProjectSettingsPage({ projectId, projectSettings, onSettingsChange }) {
  const t = useI18n();
  const { setProjectFont, userFont } = useFont();
  const [font, setFont] = useState(projectSettings?.editor_font || "");

  useEffect(() => {
    setFont(projectSettings?.editor_font || "");
  }, [projectSettings]);

  const handleFontChange = async (value) => {
    setFont(value);
    setProjectFont(value);
    const newSettings = { ...projectSettings, editor_font: value };
    try {
      await updateProject(projectId, { settings: newSettings });
      if (onSettingsChange) onSettingsChange(newSettings);
    } catch { /* ignore */ }
  };

  const previewFont = font || userFont || "system-ui";

  return (
    <div className="narrow-container">
      <h2>{t("nav.project_settings") || "Project Settings"}</h2>

      <div className="mb-12">
        <label className="form-label">{t("settings.project_font") || "Editor Font"}</label>
        <select className="input" value={font} onChange={(e) => handleFontChange(e.target.value)}>
          <option value="">{t("settings.use_default") || "Use default (from user settings)"}</option>
          {FONT_OPTIONS.filter((f) => f.value).map((f) => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>
      </div>

      <div style={{ padding: 16, border: "1px solid #ddd", borderRadius: 6, fontFamily: previewFont }}>
        <p style={{ margin: 0 }}>{t("settings.font_preview") || "The quick brown fox jumps over the lazy dog."}</p>
      </div>
    </div>
  );
}

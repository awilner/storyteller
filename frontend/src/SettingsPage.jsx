import { useI18n } from "./I18nContext";
import { useFont, FONT_OPTIONS } from "./FontContext";
import TopBar from "./TopBar";

export default function SettingsPage({ user, onBack, onLogout, onAccount }) {
  const t = useI18n();
  const { userFont, setUserFont } = useFont();

  return (
    <div>
      <TopBar username={user.username} onHome={onBack} onAccount={onAccount} onSettings={onBack} onLogout={onLogout} />
      <div className="narrow-container">
        <h2>{t("settings.title") || "Settings"}</h2>

        <div className="mb-12">
          <label className="form-label">{t("settings.default_font") || "Default Editor Font"}</label>
          <select className="input" value={userFont} onChange={(e) => setUserFont(e.target.value)}>
            {FONT_OPTIONS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <p className="muted-text" style={{ marginTop: 4 }}>
            {t("settings.font_hint") || "This font is used in the text editor across all projects unless overridden in project settings."}
          </p>
        </div>

        <div style={{ padding: 16, border: "1px solid #ddd", borderRadius: 6, fontFamily: userFont || "system-ui" }}>
          <p style={{ margin: 0 }}>{t("settings.font_preview") || "The quick brown fox jumps over the lazy dog."}</p>
        </div>
      </div>
    </div>
  );
}

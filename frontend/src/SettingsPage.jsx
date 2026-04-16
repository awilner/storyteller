import { useState, useEffect } from "react";
import { useI18n } from "./I18nContext";
import { useFont, FONT_OPTIONS } from "./FontContext";
import { fetchUserSettings, updateUserSettings, fetchTimezones } from "./api";
import TopBar from "./TopBar";

export default function SettingsPage({ user, onBack, onLogout, onAccount }) {
  const t = useI18n();
  const { userFont, setUserFont } = useFont();
  const [autoSave, setAutoSave] = useState(60);
  const [timezone, setTimezone] = useState("");
  const [timezones, setTimezones] = useState([]);
  const [tzFilter, setTzFilter] = useState("");

  useEffect(() => {
    fetchUserSettings().then((prefs) => {
      if (prefs.auto_save_interval != null) setAutoSave(prefs.auto_save_interval);
      if (prefs.timezone != null) setTimezone(prefs.timezone);
    }).catch(() => {});
    fetchTimezones().then(setTimezones).catch(() => {});
  }, []);

  const handleAutoSaveChange = (val) => {
    const num = val === "" ? 0 : Math.max(0, parseInt(val, 10) || 0);
    setAutoSave(num);
    updateUserSettings({ auto_save_interval: num }).catch(() => {});
  };

  const handleTimezoneChange = (val) => {
    setTimezone(val);
    setTzFilter("");
    updateUserSettings({ timezone: val }).catch(() => {});
  };

  const filteredTimezones = tzFilter
    ? timezones.filter((tz) => tz.toLowerCase().includes(tzFilter.toLowerCase()))
    : timezones;

  return (
    <div>
      <TopBar username={user.username} onHome={onBack} onAccount={onAccount} onSettings={onBack} onLogout={onLogout} />
      <div className="narrow-container">
        <h2>{t("settings.title")}</h2>

        <div className="mb-12">
          <label className="form-label">{t("settings.default_font")}</label>
          <select className="input" value={userFont} onChange={(e) => setUserFont(e.target.value)}>
            {FONT_OPTIONS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <p className="muted-text" style={{ marginTop: 4 }}>{t("settings.font_hint")}</p>
        </div>

        <div style={{ padding: 16, border: "1px solid #ddd", borderRadius: 6, fontFamily: userFont || "system-ui", marginBottom: 16 }}>
          <p style={{ margin: 0 }}>{t("settings.font_preview")}</p>
        </div>

        <div className="mb-12">
          <label className="form-label">{t("settings.auto_save_interval")}</label>
          <input type="number" className="input" min="0" step="10" style={{ width: 120 }}
            value={autoSave} onChange={(e) => handleAutoSaveChange(e.target.value)} />
          <p className="muted-text" style={{ marginTop: 4 }}>{t("settings.auto_save_hint")}</p>
        </div>

        <div className="mb-12">
          <label className="form-label">{t("settings.timezone")}</label>
          <input
            type="text"
            className="input"
            placeholder={t("settings.timezone")}
            value={tzFilter}
            onChange={(e) => setTzFilter(e.target.value)}
            style={{ marginBottom: 4 }}
          />
          <select
            className="input"
            value={timezone}
            onChange={(e) => handleTimezoneChange(e.target.value)}
            size={tzFilter ? Math.min(8, filteredTimezones.length + 1) : 1}
          >
            <option value="">Server default</option>
            {filteredTimezones.map((tz) => (
              <option key={tz} value={tz}>{tz}</option>
            ))}
          </select>
          <p className="muted-text" style={{ marginTop: 4 }}>{t("settings.timezone_hint")}</p>
        </div>

      </div>
    </div>
  );
}

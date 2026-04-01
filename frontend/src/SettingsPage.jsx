import { useI18n } from "./I18nContext";
import TopBar from "./TopBar";

export default function SettingsPage({ user, onBack, onLogout, onAccount }) {
  const t = useI18n();

  return (
    <div>
      <TopBar username={user.username} onHome={onBack} onAccount={onAccount} onSettings={onBack} onLogout={onLogout} />
      <div style={{ maxWidth: 500, margin: "2rem auto", padding: "0 16px", fontFamily: "system-ui" }}>
        <h2>{t("settings.title") || "Settings"}</h2>
        <p style={{ color: "#888" }}>{t("settings.placeholder") || "Settings will be available here in a future update."}</p>
      </div>
    </div>
  );
}

import { useI18n } from "./I18nContext";
import TopBar from "./TopBar";

export default function SettingsPage({ user, onBack, onLogout, onAccount }) {
  const t = useI18n();

  return (
    <div>
      <TopBar username={user.username} onHome={onBack} onAccount={onAccount} onSettings={onBack} onLogout={onLogout} />
      <div className="narrow-container">
        <h2>{t("settings.title") || "Settings"}</h2>
        <p className="muted-text">{t("settings.placeholder") || "Settings will be available here in a future update."}</p>
      </div>
    </div>
  );
}

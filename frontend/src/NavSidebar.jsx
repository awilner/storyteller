import { useI18n } from "./I18nContext";

const sections = [
  { key: "editor",     icon: "✏️", labelKey: "nav.editor" },
  { key: "outline",    icon: "🗂️", labelKey: "nav.outline" },
  { key: "characters", icon: "👤", labelKey: "nav.characters" },
  { key: "locations",  icon: "📍", labelKey: "nav.locations" },
  { key: "notes",      icon: "📝", labelKey: "nav.notes" },
];

const sidebarStyle = {
  display: "flex",
  flexDirection: "column",
  width: 44,
  minWidth: 44,
  background: "#fafafa",
  borderRight: "1px solid #ddd",
  paddingTop: 6,
  gap: 2,
};

const btnStyle = (active) => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: 40,
  height: 40,
  margin: "0 auto",
  border: "none",
  borderRadius: 6,
  background: active ? "#4a90d9" : "transparent",
  color: active ? "#fff" : "#555",
  fontSize: 18,
  cursor: "pointer",
});

const bottomBtnStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: 40,
  height: 40,
  margin: "0 auto",
  border: "none",
  borderRadius: 6,
  background: "transparent",
  color: "#666",
  fontSize: 18,
  cursor: "pointer",
};

export default function NavSidebar({ active, onChange, onDashboard, onSettings, onLogout }) {
  const t = useI18n();

  return (
    <nav style={sidebarStyle} aria-label="Project sections">
      {sections.map((s) => (
        <button
          key={s.key}
          type="button"
          style={btnStyle(active === s.key)}
          onClick={() => onChange(s.key)}
          title={t(s.labelKey) || s.key}
          aria-label={t(s.labelKey) || s.key}
          aria-current={active === s.key ? "page" : undefined}
        >
          {s.icon}
        </button>
      ))}
      <div style={{ flex: 1 }} />
      {onDashboard && (
        <button type="button" style={bottomBtnStyle} onClick={onDashboard}
          title={t("nav.dashboard") || "Dashboard"} aria-label={t("nav.dashboard") || "Dashboard"}>
          🏠
        </button>
      )}
      {onSettings && (
        <button type="button" style={bottomBtnStyle} onClick={onSettings}
          title={t("nav.settings") || "Settings"} aria-label={t("nav.settings") || "Settings"}>
          ⚙️
        </button>
      )}
      {onLogout && (
        <button type="button" style={{ ...bottomBtnStyle, marginBottom: 6 }} onClick={onLogout}
          title={t("nav.logout") || "Log out"} aria-label={t("nav.logout") || "Log out"}>
          🚪
        </button>
      )}
    </nav>
  );
}

export function NavBar({ active, onChange, onDashboard, onSettings, onLogout }) {
  const t = useI18n();

  const tabStyle = (key) => ({
    flex: 1,
    padding: "8px 0",
    border: "none",
    borderBottom: active === key ? "2px solid #4a90d9" : "2px solid transparent",
    background: active === key ? "#e8e8ff" : "transparent",
    color: active === key ? "#4a90d9" : "#555",
    fontSize: 16,
    cursor: "pointer",
  });

  const actionStyle = {
    padding: "8px 10px",
    border: "none",
    borderBottom: "2px solid transparent",
    background: "transparent",
    color: "#666",
    fontSize: 16,
    cursor: "pointer",
  };

  return (
    <nav style={{ display: "flex", borderBottom: "1px solid #ddd", background: "#fafafa", flexShrink: 0 }} aria-label="Project sections">
      {sections.map((s) => (
        <button key={s.key} type="button" style={tabStyle(s.key)}
          onClick={() => onChange(s.key)} title={t(s.labelKey) || s.key} aria-label={t(s.labelKey) || s.key}>
          {s.icon}
        </button>
      ))}
      {onDashboard && (
        <button type="button" style={actionStyle} onClick={onDashboard}
          title={t("nav.dashboard") || "Dashboard"} aria-label={t("nav.dashboard") || "Dashboard"}>
          🏠
        </button>
      )}
      {onSettings && (
        <button type="button" style={actionStyle} onClick={onSettings}
          title={t("nav.settings") || "Settings"} aria-label={t("nav.settings") || "Settings"}>
          ⚙️
        </button>
      )}
      {onLogout && (
        <button type="button" style={actionStyle} onClick={onLogout}
          title={t("nav.logout") || "Log out"} aria-label={t("nav.logout") || "Log out"}>
          🚪
        </button>
      )}
    </nav>
  );
}

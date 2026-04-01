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


export function MobileDrawer({ open, active, onChange, onDashboard, onSettings, onLogout, onClose }) {
  const t = useI18n();

  if (!open) return null;

  const overlayStyle = {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", zIndex: 1000,
  };

  const drawerStyle = {
    position: "fixed", top: 0, left: 0, bottom: 0, width: 240,
    background: "#fff", zIndex: 1001, display: "flex", flexDirection: "column",
    boxShadow: "2px 0 12px rgba(0,0,0,0.15)",
    animation: "slideIn 0.2s ease-out",
  };

  const itemStyle = (isActive) => ({
    display: "flex", alignItems: "center", gap: 12,
    padding: "12px 16px", border: "none", width: "100%",
    background: isActive ? "#e8e8ff" : "transparent",
    color: isActive ? "#4a90d9" : "#333",
    fontWeight: isActive ? 600 : 400,
    fontSize: 15, cursor: "pointer", textAlign: "left",
  });

  const bottomItemStyle = {
    display: "flex", alignItems: "center", gap: 12,
    padding: "12px 16px", border: "none", width: "100%",
    background: "transparent", color: "#666",
    fontSize: 15, cursor: "pointer", textAlign: "left",
  };

  const handleSelect = (key) => { onChange(key); onClose(); };

  return (
    <>
      <style>{`@keyframes slideIn { from { transform: translateX(-100%); } to { transform: translateX(0); } }`}</style>
      <div style={overlayStyle} onClick={onClose} />
      <nav style={drawerStyle} aria-label="Navigation">
        <div style={{ padding: "14px 16px", borderBottom: "1px solid #eee", fontWeight: 700, fontSize: 16, color: "#4a90d9" }}>
          Storyteller
        </div>
        {sections.map((s) => (
          <button key={s.key} type="button" style={itemStyle(active === s.key)}
            onClick={() => handleSelect(s.key)}>
            <span style={{ fontSize: 18 }}>{s.icon}</span>
            {t(s.labelKey) || s.key}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        {onDashboard && (
          <button type="button" style={bottomItemStyle} onClick={() => { onDashboard(); onClose(); }}>
            <span style={{ fontSize: 18 }}>🏠</span> {t("nav.dashboard") || "Dashboard"}
          </button>
        )}
        {onSettings && (
          <button type="button" style={bottomItemStyle} onClick={() => { onSettings(); onClose(); }}>
            <span style={{ fontSize: 18 }}>⚙️</span> {t("nav.settings") || "Settings"}
          </button>
        )}
        {onLogout && (
          <button type="button" style={{ ...bottomItemStyle, marginBottom: 8 }} onClick={() => { onLogout(); onClose(); }}>
            <span style={{ fontSize: 18 }}>🚪</span> {t("nav.logout") || "Log out"}
          </button>
        )}
      </nav>
    </>
  );
}

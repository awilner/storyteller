import { useI18n } from "./I18nContext";
import "./NavSidebar.css";

const sections = [
  { key: "editor",           icon: "✏️", labelKey: "nav.editor" },
  { key: "outline",          icon: "🗂️", labelKey: "nav.outline" },
  { key: "characters",       icon: "👤", labelKey: "nav.characters" },
  { key: "locations",        icon: "📍", labelKey: "nav.locations" },
  { key: "notes",            icon: "📝", labelKey: "nav.notes" },
  { key: "project-settings", icon: "⚙️", labelKey: "nav.project_settings" },
];

export default function NavSidebar({ active, onChange }) {
  const t = useI18n();

  return (
    <nav className="nav-sidebar" aria-label="Project sections">
      {sections.map((s) => (
        <button
          key={s.key}
          type="button"
          className={`nav-sidebar-btn${active === s.key ? " nav-sidebar-btn--active" : ""}`}
          onClick={() => onChange(s.key)}
          title={t(s.labelKey) || s.key}
          aria-label={t(s.labelKey) || s.key}
          aria-current={active === s.key ? "page" : undefined}
        >
          {s.icon}
        </button>
      ))}
    </nav>
  );
}

export function MobileDrawer({ open, active, onChange, onClose }) {
  const t = useI18n();
  if (!open) return null;

  const handleSelect = (key) => { onChange(key); onClose(); };

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <nav className="drawer" aria-label="Navigation">
        <div className="drawer-header">Storyteller</div>
        {sections.map((s) => (
          <button key={s.key} type="button"
            className={`drawer-item${active === s.key ? " drawer-item--active" : ""}`}
            onClick={() => handleSelect(s.key)}>
            <span className="drawer-item-icon">{s.icon}</span>
            {t(s.labelKey) || s.key}
          </button>
        ))}
      </nav>
    </>
  );
}

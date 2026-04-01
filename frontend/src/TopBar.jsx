import { useI18n } from "./I18nContext";
import logoSrc from "../resources/Storyteller.svg";

const navLabelKeys = {
  editor: "nav.editor",
  outline: "nav.outline",
  characters: "nav.characters",
  locations: "nav.locations",
  notes: "nav.notes",
};

const barStyle = {
  display: "flex",
  alignItems: "center",
  padding: "0 12px",
  height: 40,
  minHeight: 40,
  borderBottom: "1px solid #ddd",
  background: "#fff",
  fontFamily: "system-ui",
  gap: 10,
  flexShrink: 0,
};

const logoStyle = {
  fontSize: 15,
  fontWeight: 700,
  color: "#4a90d9",
  whiteSpace: "nowrap",
};

const separatorStyle = {
  color: "#ccc",
  fontSize: 14,
  userSelect: "none",
};

const contextStyle = {
  fontSize: 13,
  color: "#555",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  minWidth: 0,
};

export default function TopBar({ projectTitle, navSection }) {
  const t = useI18n();

  const sectionLabel = navSection && navLabelKeys[navSection]
    ? t(navLabelKeys[navSection]) || navSection
    : null;

  return (
    <div style={barStyle}>
      <img src={logoSrc} alt="" style={{ height: 24 }} />
      <span style={logoStyle}>Storyteller</span>
      {projectTitle && (
        <>
          <span style={separatorStyle}>/</span>
          <span style={contextStyle}>{projectTitle}</span>
        </>
      )}
      {sectionLabel && (
        <>
          <span style={separatorStyle}>/</span>
          <span style={contextStyle}>{sectionLabel}</span>
        </>
      )}
    </div>
  );
}

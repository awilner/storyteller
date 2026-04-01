import { useState, useRef, useEffect } from "react";
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

const userBtnStyle = {
  background: "none",
  border: "none",
  fontSize: 13,
  color: "#555",
  cursor: "pointer",
  padding: "4px 8px",
  borderRadius: 4,
};

const dropdownStyle = {
  position: "absolute",
  top: "100%",
  right: 0,
  marginTop: 4,
  background: "#fff",
  border: "1px solid #ddd",
  borderRadius: 6,
  boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
  minWidth: 150,
  zIndex: 100,
  overflow: "hidden",
};

const dropdownItemStyle = {
  display: "block",
  width: "100%",
  padding: "10px 14px",
  border: "none",
  background: "none",
  textAlign: "left",
  fontSize: 13,
  color: "#333",
  cursor: "pointer",
};

export default function TopBar({ projectTitle, navSection, onMenuToggle, onHome, username, onAccount, onSettings, onLogout }) {
  const t = useI18n();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [dropdownOpen]);

  const sectionLabel = navSection && navLabelKeys[navSection]
    ? t(navLabelKeys[navSection]) || navSection
    : null;

  return (
    <div style={barStyle}>
      {onMenuToggle && (
        <button
          type="button"
          onClick={onMenuToggle}
          style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", padding: "2px 4px", lineHeight: 1, color: "#555" }}
          aria-label="Menu"
        >
          ☰
        </button>
      )}
      <img src={logoSrc} alt="" style={{ height: 24, cursor: onHome ? "pointer" : "default" }} onClick={onHome || undefined} />
      <span style={{ ...logoStyle, cursor: onHome ? "pointer" : "default" }} onClick={onHome || undefined}>Storyteller</span>
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

      {username && (
        <>
          <div style={{ flex: 1 }} />
          <div ref={dropdownRef} style={{ position: "relative" }}>
            <button
              type="button"
              style={userBtnStyle}
              onClick={() => setDropdownOpen((v) => !v)}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#f0f0f0"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
            >
              {username} ▾
            </button>
            {dropdownOpen && (
              <div style={dropdownStyle}>
                {onAccount && (
                  <button type="button" style={dropdownItemStyle}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#f5f5f5"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
                    onClick={() => { setDropdownOpen(false); onAccount(); }}>
                    {t("topbar.account") || "Account"}
                  </button>
                )}
                {onSettings && (
                  <button type="button" style={dropdownItemStyle}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#f5f5f5"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
                    onClick={() => { setDropdownOpen(false); onSettings(); }}>
                    {t("topbar.settings") || "Settings"}
                  </button>
                )}
                {onLogout && (
                  <>
                    <div style={{ borderTop: "1px solid #eee" }} />
                    <button type="button" style={{ ...dropdownItemStyle, color: "#c44" }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "#f5f5f5"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
                      onClick={() => { setDropdownOpen(false); onLogout(); }}>
                      {t("topbar.logout") || "Log out"}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

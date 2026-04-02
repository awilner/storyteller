import { useState, useRef, useEffect } from "react";
import { useI18n } from "./I18nContext";
import logoSrc from "../resources/Storyteller.svg";
import "./TopBar.css";

export default function TopBar({ projectTitle, onHome, username, onAccount, onSettings, onLogout }) {
  const t = useI18n();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

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

  const logoClass = `topbar-logo${onHome ? " topbar-logo-clickable" : ""}`;

  return (
    <div className="topbar">
      <img src={logoSrc} alt="" style={{ height: 24 }} className={onHome ? "topbar-logo-clickable" : ""} onClick={onHome || undefined} />
      <span className={logoClass} onClick={onHome || undefined}>Storyteller</span>
      {projectTitle && (
        <>
          <span className="topbar-separator">/</span>
          <span className="topbar-context">{projectTitle}</span>
        </>
      )}
      {username && (
        <>
          <div className="topbar-spacer" />
          <div ref={dropdownRef} className="topbar-user-wrapper">
            <button type="button" className="topbar-user-btn" onClick={() => setDropdownOpen((v) => !v)}>
              {username} ▾
            </button>
            {dropdownOpen && (
              <div className="topbar-dropdown">
                {onAccount && (
                  <button type="button" className="topbar-dropdown-item"
                    onClick={() => { setDropdownOpen(false); onAccount(); }}>
                    {t("topbar.account") || "Account"}
                  </button>
                )}
                {onSettings && (
                  <button type="button" className="topbar-dropdown-item"
                    onClick={() => { setDropdownOpen(false); onSettings(); }}>
                    {t("topbar.settings") || "Settings"}
                  </button>
                )}
                {onLogout && (
                  <>
                    <div className="section-divider" />
                    <button type="button" className="topbar-dropdown-item topbar-dropdown-item--danger"
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

import { useState, useRef, useEffect } from "react";
import { useI18n } from "./I18nContext";
import logoSrc from "../resources/Storyteller.svg";
import "./TopBar.css";

export default function TopBar({ projectTitle, onHome, username, onAccount, onSettings, onLogout, onExportScrivener, onExportYWriter, onCompile, onProjectSettings, onProgressTracking, role }) {
  const t = useI18n();
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const userRef = useRef(null);
  const projectRef = useRef(null);

  useEffect(() => {
    if (!userDropdownOpen && !projectDropdownOpen) return;
    const handler = (e) => {
      if (userDropdownOpen && userRef.current && !userRef.current.contains(e.target)) {
        setUserDropdownOpen(false);
      }
      if (projectDropdownOpen && projectRef.current && !projectRef.current.contains(e.target)) {
        setProjectDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [userDropdownOpen, projectDropdownOpen]);

  const logoClass = `topbar-logo${onHome ? " topbar-logo-clickable" : ""}`;

  const hasProjectMenu = onExportScrivener || onExportYWriter || onCompile || onProjectSettings || onProgressTracking;

  return (
    <div className="topbar">
      <img src={logoSrc} alt="" style={{ height: 24 }} className={onHome ? "topbar-logo-clickable" : ""} onClick={onHome || undefined} />
      <span className={logoClass} onClick={onHome || undefined}>Storyteller</span>
      {projectTitle && (
        <>
          <span className="topbar-separator">/</span>
          {hasProjectMenu ? (
            <div ref={projectRef} className="topbar-project-wrapper">
              <button type="button" className="topbar-project-btn" onClick={() => setProjectDropdownOpen((v) => !v)}>
                {projectTitle} ▾
              </button>
              {projectDropdownOpen && (
                <div className="topbar-dropdown">
                  {onCompile && (
                    <button type="button" className="topbar-dropdown-item"
                      onClick={() => { setProjectDropdownOpen(false); onCompile(); }}>
                      {t("topbar.compile_manuscript")}
                    </button>
                  )}
                  {onProjectSettings && (
                    <button type="button" className="topbar-dropdown-item"
                      onClick={() => { setProjectDropdownOpen(false); onProjectSettings(); }}>
                      {t("topbar.project_settings")}
                    </button>
                  )}
                  {onProgressTracking && (
                    <button type="button" className="topbar-dropdown-item"
                      onClick={() => { setProjectDropdownOpen(false); onProgressTracking(); }}>
                      {t("topbar.progress_tracking")}
                    </button>
                  )}
                  {(onCompile || onProjectSettings || onProgressTracking) && (onExportScrivener || onExportYWriter) && (
                    <div className="section-divider" />
                  )}
                  {onExportScrivener && (
                    <button type="button" className="topbar-dropdown-item"
                      onClick={() => { setProjectDropdownOpen(false); onExportScrivener(); }}>
                      {t("topbar.export_scrivener")}
                    </button>
                  )}
                  {onExportYWriter && (
                    <button type="button" className="topbar-dropdown-item"
                      onClick={() => { setProjectDropdownOpen(false); onExportYWriter(); }}>
                      {t("topbar.export_ywriter")}
                    </button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <span className="topbar-context">{projectTitle}</span>
          )}
          {role && role !== "owner" && (
            <span className={`topbar-role-tag topbar-role-tag--${role}`}>
              {role === "co-author" ? "Co-Author" : "Read Only"}
            </span>
          )}
        </>
      )}
      {username && (
        <>
          <div className="topbar-spacer" />
          <div ref={userRef} className="topbar-user-wrapper">
            <button type="button" className="topbar-user-btn" onClick={() => setUserDropdownOpen((v) => !v)}>
              {username} ▾
            </button>
            {userDropdownOpen && (
              <div className="topbar-dropdown">
                {onAccount && (
                  <button type="button" className="topbar-dropdown-item"
                    onClick={() => { setUserDropdownOpen(false); onAccount(); }}>
                    {t("topbar.account") || "Account"}
                  </button>
                )}
                {onSettings && (
                  <button type="button" className="topbar-dropdown-item"
                    onClick={() => { setUserDropdownOpen(false); onSettings(); }}>
                    {t("topbar.settings") || "Settings"}
                  </button>
                )}
                {onLogout && (
                  <>
                    <div className="section-divider" />
                    <button type="button" className="topbar-dropdown-item topbar-dropdown-item--danger"
                      onClick={() => { setUserDropdownOpen(false); onLogout(); }}>
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

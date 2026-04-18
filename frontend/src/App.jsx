import { useState, useEffect, useRef } from "react";
import { fetchMe, fetchProjects, createProject, deleteProject, updateProject, logout, fetchConfig, exportScrivener, exportYWriter, fetchProgress } from "./api";
import { useI18n } from "./I18nContext";
import AuthForm from "./AuthForm";
import EditorView from "./EditorView";
import ImportModal from "./ImportModal";
import TopBar from "./TopBar";
import AccountPage from "./AccountPage";
import SettingsPage from "./SettingsPage";
import OIDCCallback from "./OIDCCallback";
import VersionBadge from "./VersionBadge";
import "./App.css";

function ProjectProgress({ projectId }) {
  const t = useI18n();
  const [data, setData] = useState(null);
  useEffect(() => {
    fetchProgress(projectId).then(setData).catch(() => {});
  }, [projectId]);
  if (!data) return null;
  const hasMs = data.manuscript_target != null;
  const hasDaily = data.daily_target != null;
  if (!hasMs && !hasDaily) return null;
  const msPct = hasMs ? Math.min(Math.round((data.current_word_count / data.manuscript_target) * 100), 100) : 0;
  const dailyPct = hasDaily ? Math.min(Math.round((data.daily_word_count / data.daily_target) * 100), 100) : 0;
  return (
    <div style={{ marginTop: 6, fontSize: 12, color: "#666", display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
      {hasMs && (
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span>{t("dashboard.manuscript_progress")}:</span>
          <span style={{ display: "inline-block", width: 60, height: 6, background: "#e0e0e0", borderRadius: 3, overflow: "hidden" }}>
            <span style={{ display: "block", height: "100%", width: `${msPct}%`, background: "#4a90d9", borderRadius: 3 }} />
          </span>
          <span>{msPct}%</span>
        </span>
      )}
      {hasDaily && (
        <span>{t("dashboard.daily_progress")}: {data.daily_word_count}/{data.daily_target} ({dailyPct}%)</span>
      )}
    </div>
  );
}

export default function App() {
  // Handle OIDC callback route — must be before any conditional logic
  const [isOidcCallback, setIsOidcCallback] = useState(() => window.location.pathname === "/oidc/callback");

  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [oidcEnabled, setOidcEnabled] = useState(false);

  const [selectedProjectId, setSelectedProjectId] = useState(() => {
    const m = window.location.pathname.match(/^\/projects\/(\d+)/);
    return m ? Number(m[1]) : null;
  });
  const [initialFileId] = useState(() => {
    const m = window.location.pathname.match(/^\/projects\/\d+\/files\/(\d+)/);
    return m ? Number(m[1]) : null;
  });
  const [initialFolderId] = useState(() => {
    const m = window.location.pathname.match(/^\/projects\/\d+\/folders\/(\d+)/);
    return m ? Number(m[1]) : null;
  });
  const [projects, setProjects] = useState([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [projectsError, setProjectsError] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [editingProjectId, setEditingProjectId] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [menuProjectId, setMenuProjectId] = useState(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (menuProjectId === null) return;
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuProjectId(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuProjectId]);

  const [page, setPage] = useState(() => {
    const p = window.location.pathname;
    if (p === "/account") return "account";
    if (p === "/settings") return "settings";
    return "dashboard";
  });

  useEffect(() => {
    if (isOidcCallback) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
    fetchConfig()
      .then((cfg) => setOidcEnabled(cfg.oidc_enabled))
      .catch(() => {});
  }, []);

  // Sync URL with navigation state
  useEffect(() => {
    if (isOidcCallback) return;
    let target;
    if (selectedProjectId) {
      target = `/projects/${selectedProjectId}`;
      // Don't overwrite file/folder sub-paths set by EditorView
      if (window.location.pathname.startsWith(target)) return;
    } else if (page === "account") {
      target = "/account";
    } else if (page === "settings") {
      target = "/settings";
    } else {
      target = "/";
    }
    if (window.location.pathname !== target) {
      window.history.pushState(null, "", target);
    }
  }, [selectedProjectId, page, isOidcCallback]);

  // Handle browser back/forward
  useEffect(() => {
    const onPopState = () => {
      const p = window.location.pathname;
      const m = p.match(/^\/projects\/(\d+)/);
      if (m) {
        setSelectedProjectId(Number(m[1]));
        setPage("dashboard");
      } else {
        setSelectedProjectId(null);
        if (p === "/account") setPage("account");
        else if (p === "/settings") setPage("settings");
        else setPage("dashboard");
      }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  // Fetch projects when user is logged in
  useEffect(() => {
    if (!user) return;
    setProjectsLoading(true);
    setProjectsError(null);
    fetchProjects()
      .then(setProjects)
      .catch((err) => setProjectsError(err.message))
      .finally(() => setProjectsLoading(false));
  }, [user]);

  const handleLogout = async () => {
    try { await logout(); } catch { /* ignore */ }
    setUser(null);
    setSelectedProjectId(null);
    setProjects([]);
    window.history.pushState(null, "", "/");
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      const project = await createProject(newTitle.trim(), newDescription.trim());
      setProjects((prev) => [project, ...prev]);
      setNewTitle("");
      setNewDescription("");
      setShowCreateForm(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteProject = async (projectId, title) => {
    if (!window.confirm(`Delete "${title}"? This will permanently remove the project and all its content.`)) return;
    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
    } catch (err) {
      setError(err.message);
    }
  };

  const startEditing = (p) => {
    setEditingProjectId(p.id);
    setEditTitle(p.title);
    setEditDescription(p.description || "");
  };

  const cancelEditing = () => {
    setEditingProjectId(null);
  };

  const handleUpdateProject = async (projectId) => {
    if (!editTitle.trim()) return;
    try {
      const updated = await updateProject(projectId, { title: editTitle.trim(), description: editDescription.trim() });
      setProjects((prev) => prev.map((p) => (p.id === projectId ? updated : p)));
      setEditingProjectId(null);
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) return <p style={{ textAlign: "center", marginTop: "2rem" }}>Loading…</p>;

  if (isOidcCallback) return <OIDCCallback onAuth={(u) => { setUser(u); setIsOidcCallback(false); }} />;

  if (!user) return <><AuthForm onAuth={setUser} oidcEnabled={oidcEnabled} /><VersionBadge /></>;

  // Editor view when a project is selected
  if (selectedProjectId) {
    const selectedProject = projects.find((p) => p.id === selectedProjectId);
    const projectRole = selectedProject?.role || null;
    return (
      <div className="app-editor-wrapper">
        <EditorView
          projectId={selectedProjectId}
          initialFileId={initialFileId}
          initialFolderId={initialFolderId}
          initialProgressOpen={/^\/projects\/\d+\/progress\/?$/.test(window.location.pathname)}
          onLogout={handleLogout}
          onDashboard={() => setSelectedProjectId(null)}
          username={user.username}
          role={projectRole}
          onAccount={() => { setSelectedProjectId(null); setPage("account"); }}
          onSettings={() => { setSelectedProjectId(null); setPage("settings"); }}
        />
      </div>
    );
  }

  // Account / Settings pages
  if (page === "account") {
    return (
      <AccountPage
        user={user}
        oidcEnabled={oidcEnabled}
        onUserUpdate={setUser}
        onBack={() => setPage("dashboard")}
        onLogout={handleLogout}
        onSettings={() => setPage("settings")}
      />
    );
  }
  if (page === "settings") {
    return (
      <SettingsPage
        user={user}
        onBack={() => setPage("dashboard")}
        onLogout={handleLogout}
        onAccount={() => setPage("account")}
      />
    );
  }

  // Dashboard view
  return (
    <div>
      <TopBar username={user.username} onAccount={() => setPage("account")} onSettings={() => setPage("settings")} onLogout={handleLogout} />
      <div className="page-container">
        {error && <p className="error-text">{error}</p>}

      <div className="flex-between">
        <h2>Your Projects</h2>
        <div className="dashboard-actions">
          <button type="button" onClick={() => setShowImportModal(true)} className="btn btn-success">Import</button>
          <button type="button" onClick={() => setShowCreateForm((v) => !v)} className="btn btn-primary">
            {showCreateForm ? "Cancel" : "+ New Project"}
          </button>
        </div>
      </div>

      {showCreateForm && (
        <form onSubmit={handleCreateProject} className="form-card">
          <div className="mb-8">
            <input type="text" placeholder="Project title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} required className="input" />
          </div>
          <div className="mb-8">
            <textarea placeholder="Description (optional)" value={newDescription} onChange={(e) => setNewDescription(e.target.value)} rows={2} className="textarea" />
          </div>
          <button type="submit" disabled={creating || !newTitle.trim()} className="btn btn-primary">
            {creating ? "Creating…" : "Create"}
          </button>
        </form>
      )}

      {projectsLoading && <p className="loading-text">Loading projects…</p>}
      {projectsError && <p className="error-text">{projectsError}</p>}
      {!projectsLoading && !projectsError && projects.length === 0 && (
        <p className="muted-text">No projects yet. Create one to get started.</p>
      )}
      {projects.length > 0 && (
        <ul className="project-list">
          {projects.map((p) => (
            <li key={p.id} className="card">
              {editingProjectId === p.id ? (
                <div>
                  <input type="text" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className="input-edit mb-6" />
                  <textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} placeholder="Description (optional)" rows={2} className="textarea-small mb-6" />
                  <div className="project-edit-actions">
                    <button type="button" onClick={() => handleUpdateProject(p.id)} disabled={!editTitle.trim()} className="btn btn-primary btn-small">Save</button>
                    <button type="button" onClick={cancelEditing} className="btn btn-ghost btn-small">Cancel</button>
                  </div>
                </div>
              ) : (
                <div className="project-card-row">
                  <div>
                    <strong>{p.title}</strong>
                    {p.owner_name && (
                      <span className="project-owner-badge">Shared by {p.owner_name}</span>
                    )}
                    {p.role && p.role !== "owner" && (
                      <span className={`project-role-badge project-role-badge--${p.role}`}>
                        {p.role === "co-author" ? "Co-Author" : "Read Only"}
                      </span>
                    )}
                    {p.description && <p className="project-description">{p.description}</p>}
                    <ProjectProgress projectId={p.id} />
                  </div>
                  <div className="project-card-buttons">
                    <button type="button" onClick={() => setSelectedProjectId(p.id)} className="btn btn-primary">Open</button>
                    <button type="button" onClick={() => startEditing(p)} className="btn btn-secondary">Edit</button>
                    {(!p.role || p.role === "owner") && (
                      <button type="button" onClick={() => handleDeleteProject(p.id, p.title)} className="btn btn-danger">Delete</button>
                    )}
                    <div className="project-menu-wrapper" ref={menuProjectId === p.id ? menuRef : undefined}>
                      <button type="button" className="btn btn-ghost project-menu-btn" onClick={() => setMenuProjectId(menuProjectId === p.id ? null : p.id)} aria-label="More actions">⋯</button>
                      {menuProjectId === p.id && (
                        <div className="project-menu-dropdown">
                          <button type="button" className="topbar-dropdown-item" onClick={() => { setMenuProjectId(null); window.location.href = exportScrivener(p.id); }}>Export as Scrivener</button>
                          <button type="button" className="topbar-dropdown-item" onClick={() => { setMenuProjectId(null); window.location.href = exportYWriter(p.id); }}>Export as yWriter</button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {showImportModal && (
        <ImportModal
          onClose={() => setShowImportModal(false)}
          onImported={(project) => setProjects((prev) => [project, ...prev])}
        />
      )}
      <VersionBadge />
      </div>
    </div>
  );
}

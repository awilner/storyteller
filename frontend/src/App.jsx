import { useState, useEffect } from "react";
import { fetchMe, fetchProjects, createProject, deleteProject, updateProject, logout, oidcLogin, oidcUnlink, fetchConfig } from "./api";
import AuthForm from "./AuthForm";
import EditorView from "./EditorView";
import ImportModal from "./ImportModal";
import OIDCCallback from "./OIDCCallback";

export default function App() {
  // Handle OIDC callback route — must be before any conditional logic
  const [isOidcCallback] = useState(() => window.location.pathname === "/oidc/callback");

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

  useEffect(() => {
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
    if (selectedProjectId) {
      if (!window.location.pathname.startsWith(`/projects/${selectedProjectId}`)) {
        window.history.pushState(null, "", `/projects/${selectedProjectId}`);
      }
    } else if (!isOidcCallback) {
      if (window.location.pathname !== "/") {
        window.history.pushState(null, "", "/");
      }
    }
  }, [selectedProjectId, isOidcCallback]);

  // Handle browser back/forward
  useEffect(() => {
    const onPopState = () => {
      const m = window.location.pathname.match(/^\/projects\/(\d+)/);
      setSelectedProjectId(m ? Number(m[1]) : null);
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

  const handleLinkOIDC = async () => {
    try {
      sessionStorage.setItem("oidc_mode", "link");
      const { authorization_url } = await oidcLogin();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUnlinkOIDC = async (identityId) => {
    try {
      await oidcUnlink(identityId);
      const updated = await fetchMe();
      setUser(updated);
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) return <p style={{ textAlign: "center", marginTop: "2rem" }}>Loading…</p>;

  if (isOidcCallback) return <OIDCCallback onAuth={(u) => { setUser(u); setLoading(false); }} />;

  if (!user) return <AuthForm onAuth={setUser} oidcEnabled={oidcEnabled} />;

  // Editor view when a project is selected
  if (selectedProjectId) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
        <div style={{ flexShrink: 0, padding: "4px 12px", borderBottom: "1px solid #ddd", background: "#f9f9f9", display: "flex", alignItems: "center", gap: 12 }}>
          <button
            type="button"
            onClick={() => setSelectedProjectId(null)}
            style={{ cursor: "pointer", border: "1px solid #ccc", borderRadius: 4, padding: "4px 10px", background: "#fff" }}
          >
            ← Back to Dashboard
          </button>
          <span style={{ color: "#666", fontSize: 13 }}>{user.username}</span>
        </div>
        <EditorView projectId={selectedProjectId} initialFileId={initialFileId} initialFolderId={initialFolderId} />
      </div>
    );
  }

  // Dashboard view
  return (
    <div style={{ maxWidth: 600, margin: "2rem auto", padding: "0 16px", fontFamily: "system-ui" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Dashboard</h1>
        <span>
          {user.username}{" "}
          <button type="button" onClick={handleLogout}>Log out</button>
        </span>
      </div>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Your Projects</h2>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            type="button"
            onClick={() => setShowImportModal(true)}
            style={{ cursor: "pointer", border: "1px solid #28a745", borderRadius: 4, padding: "6px 14px", background: "#28a745", color: "#fff", fontWeight: 600, fontSize: 13 }}
          >
            Import
          </button>
          <button
            type="button"
            onClick={() => setShowCreateForm((v) => !v)}
            style={{ cursor: "pointer", border: "1px solid #4a90d9", borderRadius: 4, padding: "6px 14px", background: "#4a90d9", color: "#fff", fontWeight: 600, fontSize: 13 }}
          >
            {showCreateForm ? "Cancel" : "+ New Project"}
          </button>
        </div>
      </div>

      {showCreateForm && (
        <form onSubmit={handleCreateProject} style={{ border: "1px solid #ddd", borderRadius: 6, padding: 16, marginBottom: 12 }}>
          <div style={{ marginBottom: 8 }}>
            <input
              type="text"
              placeholder="Project title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              required
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14, boxSizing: "border-box" }}
            />
          </div>
          <div style={{ marginBottom: 8 }}>
            <textarea
              placeholder="Description (optional)"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              rows={2}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14, boxSizing: "border-box", resize: "vertical" }}
            />
          </div>
          <button
            type="submit"
            disabled={creating || !newTitle.trim()}
            style={{ cursor: creating ? "not-allowed" : "pointer", border: "1px solid #4a90d9", borderRadius: 4, padding: "6px 14px", background: "#4a90d9", color: "#fff", fontWeight: 600, fontSize: 13 }}
          >
            {creating ? "Creating…" : "Create"}
          </button>
        </form>
      )}

      {projectsLoading && <p style={{ color: "#888" }}>Loading projects…</p>}
      {projectsError && <p style={{ color: "red" }}>{projectsError}</p>}
      {!projectsLoading && !projectsError && projects.length === 0 && (
        <p style={{ color: "#888" }}>No projects yet. Create one to get started.</p>
      )}
      {projects.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {projects.map((p) => (
            <li
              key={p.id}
              style={{
                border: "1px solid #ddd",
                borderRadius: 6,
                padding: "12px 16px",
                marginBottom: 8,
              }}
            >
              {editingProjectId === p.id ? (
                <div>
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    style={{ width: "100%", padding: "6px 8px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14, boxSizing: "border-box", marginBottom: 6 }}
                  />
                  <textarea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="Description (optional)"
                    rows={2}
                    style={{ width: "100%", padding: "6px 8px", border: "1px solid #ccc", borderRadius: 4, fontSize: 13, boxSizing: "border-box", resize: "vertical", marginBottom: 6 }}
                  />
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => handleUpdateProject(p.id)}
                      disabled={!editTitle.trim()}
                      style={{ cursor: "pointer", border: "1px solid #4a90d9", borderRadius: 4, padding: "4px 12px", background: "#4a90d9", color: "#fff", fontWeight: 600, fontSize: 13 }}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={cancelEditing}
                      style={{ cursor: "pointer", border: "1px solid #ccc", borderRadius: 4, padding: "4px 12px", background: "#fff", color: "#333", fontSize: 13 }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <strong>{p.title}</strong>
                    {p.description && (
                      <p style={{ margin: "4px 0 0", color: "#666", fontSize: 14 }}>{p.description}</p>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                    <button
                      type="button"
                      onClick={() => setSelectedProjectId(p.id)}
                      style={{ cursor: "pointer", border: "1px solid #4a90d9", borderRadius: 4, padding: "6px 14px", background: "#4a90d9", color: "#fff", fontWeight: 600, fontSize: 13 }}
                    >
                      Open
                    </button>
                    <button
                      type="button"
                      onClick={() => startEditing(p)}
                      style={{ cursor: "pointer", border: "1px solid #6c757d", borderRadius: 4, padding: "6px 14px", background: "#fff", color: "#6c757d", fontWeight: 600, fontSize: 13 }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteProject(p.id, p.title)}
                      style={{ cursor: "pointer", border: "1px solid #dc3545", borderRadius: 4, padding: "6px 14px", background: "#fff", color: "#dc3545", fontWeight: 600, fontSize: 13 }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {oidcEnabled && (
        <div style={{ marginTop: "2rem", borderTop: "1px solid #ccc", paddingTop: "1rem" }}>
          <h3>Linked OIDC Identities</h3>
          {user.oidc_identities?.length > 0 ? (
            <ul>
              {user.oidc_identities.map((id) => (
                <li key={id.id}>
                  {id.provider} ({id.email || "no email"})
                  <button
                    onClick={() => handleUnlinkOIDC(id.id)}
                    style={{ marginLeft: "0.5rem" }}
                    aria-label={`Unlink ${id.provider}`}
                  >
                    Unlink
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p>No OIDC identities linked.</p>
          )}
          <button type="button" onClick={handleLinkOIDC}>Link OIDC Account</button>
        </div>
      )}

      {showImportModal && (
        <ImportModal
          onClose={() => setShowImportModal(false)}
          onImported={(project) => setProjects((prev) => [project, ...prev])}
        />
      )}
    </div>
  );
}

import { useState, useEffect, useCallback, useRef } from "react";
import { fetchShares, createShare, updateShare, deleteShare, searchUsers } from "./api";
import "./SharingPanel.css";

const SEARCH_DEBOUNCE_MS = 300;

export default function SharingPanel({ projectId, role, onSharesChanged, refreshKey }) {
  const [shares, setShares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedRole, setSelectedRole] = useState("read-only");
  const searchTimer = useRef(null);

  const isOwner = role === "owner";

  const loadShares = useCallback(async () => {
    try {
      const data = await fetchShares(projectId);
      setShares(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadShares();
  }, [loadShares, refreshKey]);

  // Debounced user search
  useEffect(() => {
    if (!searchQuery.trim() || !isOwner) {
      setSearchResults([]);
      return;
    }
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      setSearching(true);
      try {
        const results = await searchUsers(projectId, searchQuery.trim());
        setSearchResults(results);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, [searchQuery, projectId, isOwner]);

  const handleAddCollaborator = useCallback(async (username) => {
    setError(null);
    try {
      await createShare(projectId, username, selectedRole);
      setSearchQuery("");
      setSearchResults([]);
      await loadShares();
      onSharesChanged?.();
    } catch (err) {
      setError(err.message);
    }
  }, [projectId, selectedRole, loadShares, onSharesChanged]);

  const handleRoleChange = useCallback(async (shareId, newRole) => {
    setError(null);
    try {
      await updateShare(projectId, shareId, newRole);
      await loadShares();
      onSharesChanged?.();
    } catch (err) {
      setError(err.message);
    }
  }, [projectId, loadShares, onSharesChanged]);

  const handleRevoke = useCallback(async (shareId, username) => {
    if (!window.confirm(`Revoke access for "${username}"?`)) return;
    setError(null);
    try {
      await deleteShare(projectId, shareId);
      await loadShares();
      onSharesChanged?.();
    } catch (err) {
      setError(err.message);
    }
  }, [projectId, loadShares, onSharesChanged]);

  if (loading) return <div className="sharing-panel"><p className="sharing-loading">Loading collaborators…</p></div>;

  return (
    <div className="sharing-panel">
      <h4 className="sharing-heading">Sharing</h4>

      {error && <div className="sharing-error">{error}</div>}

      {/* Add collaborator — owner only */}
      {isOwner && (
        <div className="sharing-add">
          <div className="sharing-search-row">
            <input
              type="text"
              className="sharing-search-input"
              placeholder="Search users…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <select
              className="sharing-role-select"
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
            >
              <option value="read-only">Read Only</option>
              <option value="co-author">Co-Author</option>
            </select>
          </div>
          {searching && <p className="sharing-searching">Searching…</p>}
          {searchResults.length > 0 && (
            <ul className="sharing-search-results">
              {searchResults.map((u) => (
                <li key={u.id} className="sharing-search-result">
                  <span className="sharing-search-username">{u.username}</span>
                  <button
                    type="button"
                    className="sharing-add-btn"
                    onClick={() => handleAddCollaborator(u.username)}
                  >
                    Add
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Collaborator list */}
      {shares.length === 0 ? (
        <p className="sharing-empty">No collaborators yet.</p>
      ) : (
        <ul className="sharing-list">
          {shares.map((share) => (
            <li key={share.id} className="sharing-item">
              <div className="sharing-item-info">
                <span className="sharing-username">{share.username}</span>
                <span className={`sharing-role-badge sharing-role-badge--${share.role}`}>
                  {share.role === "co-author" ? "Co-Author" : "Read Only"}
                </span>
              </div>
              {isOwner && (
                <div className="sharing-item-actions">
                  <select
                    className="sharing-role-select sharing-role-select--small"
                    value={share.role}
                    onChange={(e) => handleRoleChange(share.id, e.target.value)}
                  >
                    <option value="read-only">Read Only</option>
                    <option value="co-author">Co-Author</option>
                  </select>
                  <button
                    type="button"
                    className="sharing-revoke-btn"
                    onClick={() => handleRevoke(share.id, share.username)}
                  >
                    Revoke
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

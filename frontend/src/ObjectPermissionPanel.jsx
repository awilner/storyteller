import { useState, useEffect, useCallback } from "react";
import { fetchShares, fetchOverrides, createOverride, updateOverride, deleteOverride } from "./api";
import "./ObjectPermissionPanel.css";

const PERM_RANK = { "co-author": 2, "read-only": 1, "none": 0 };

function permLabel(perm) {
  if (perm === "none") return "No Access";
  if (perm === "co-author") return "Co-Author";
  return "Read Only";
}

/** Return the more restrictive of two permissions. */
function moreRestrictive(a, b) {
  return (PERM_RANK[a] ?? 2) <= (PERM_RANK[b] ?? 2) ? a : b;
}

export default function ObjectPermissionPanel({ projectId, role, objectType, objectId, ancestorFolderIds = [], refreshKey, username }) {
  const [shares, setShares] = useState([]);
  const [overrides, setOverrides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const isOwner = role === "owner";

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sharesData, overridesData] = await Promise.all([
        fetchShares(projectId),
        fetchOverrides(projectId),
      ]);
      setShares(sharesData);
      setOverrides(overridesData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData, refreshKey]);

  // For non-owners, only show their own share entry (they only have
  // override data for themselves, so showing others would be misleading).
  const visibleShares = isOwner
    ? shares
    : shares.filter((s) => s.username === username);

  // Direct override on the current object
  const getOverrideForUser = useCallback((userId) => {
    const targetKey = objectType === "folder" ? "target_folder" : "target_file";
    return overrides.find(
      (o) => o.user === userId && o[targetKey] === objectId
    );
  }, [overrides, objectType, objectId]);

  // Nearest ancestor folder override (closest parent first)
  const getAncestorOverrideForUser = useCallback((userId) => {
    for (let i = ancestorFolderIds.length - 1; i >= 0; i--) {
      const match = overrides.find(
        (o) => o.user === userId && o.target_folder === ancestorFolderIds[i]
      );
      if (match) return match;
    }
    return null;
  }, [overrides, ancestorFolderIds]);

  const handleOverrideChange = useCallback(async (userId, value) => {
    setError(null);
    try {
      const existing = getOverrideForUser(userId);
      if (value === "inherit") {
        if (existing) {
          await deleteOverride(projectId, existing.id);
        }
      } else if (existing) {
        await updateOverride(projectId, existing.id, { permission: value });
      } else {
        const data = {
          user: userId,
          permission: value,
          ...(objectType === "folder"
            ? { target_folder: objectId }
            : { target_file: objectId }),
        };
        await createOverride(projectId, data);
      }
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }, [projectId, objectType, objectId, getOverrideForUser, loadData]);

  if (loading) return <div className="objperm-panel"><p className="objperm-loading">Loading permissions…</p></div>;
  if (visibleShares.length === 0) return null;

  return (
    <div className="objperm-panel">
      <h4 className="objperm-heading">Permissions</h4>

      {error && <div className="objperm-error">{error}</div>}

      <ul className="objperm-list">
        {visibleShares.map((share) => {
          const directOverride = getOverrideForUser(share.user);
          const ancestorOverride = getAncestorOverrideForUser(share.user);

          // Object's own level: direct override if set, otherwise project role
          const ownPerm = directOverride ? directOverride.permission : share.role;
          // Parent's effective level: ancestor override if set, otherwise project role
          const parentPerm = ancestorOverride ? ancestorOverride.permission : share.role;
          // Effective = most restrictive of own and parent
          const effective = moreRestrictive(ownPerm, parentPerm);

          // Strikethrough: shown when own level differs from effective
          // (meaning the parent is forcing something more restrictive)
          const showStrikethrough = ownPerm !== effective;

          // Annotation logic:
          // - "inherited from parent" when parent override exists and object
          //   has no direct override, OR parent is overriding the object's own level
          // - "inherited from project" when no parent override and no direct override
          const hasParent = !!ancestorOverride;
          const hasDirect = !!directOverride;
          let annotation = null;
          if (!hasDirect && !hasParent) {
            annotation = "(inherited from project)";
          } else if (!hasDirect && hasParent) {
            annotation = "(inherited from parent folder)";
          } else if (showStrikethrough) {
            annotation = "(inherited from parent folder)";
          }

          const overrideValue = directOverride ? directOverride.permission : "inherit";

          return (
            <li key={share.id} className="objperm-item">
              <div className="objperm-item-info">
                <span className="objperm-username">{share.username}</span>
                {showStrikethrough && (
                  <span className="objperm-effective objperm-effective--overridden">
                    {permLabel(ownPerm)}
                  </span>
                )}
                <span className={`objperm-effective${showStrikethrough ? " objperm-effective--actual" : ""}`}>
                  {permLabel(effective)}
                </span>
                {annotation && (
                  <span className="objperm-ancestor-note">{annotation}</span>
                )}
              </div>
              {isOwner && (
                <div className="objperm-controls">
                  <select
                    className="objperm-select"
                    value={overrideValue}
                    onChange={(e) => handleOverrideChange(share.user, e.target.value)}
                  >
                    <option value="inherit">Inherit ({share.role})</option>
                    {share.role === "co-author" && (
                      <option value="read-only">Read Only</option>
                    )}
                    <option value="none">No Access</option>
                  </select>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

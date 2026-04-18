/**
 * Shared tree utility functions used by EditorView, CompileDialog, etc.
 */

export function findFolderById(folders, id) {
  for (const f of folders || []) {
    if (f.id === id) return f;
    const found = findFolderById(f.children, id);
    if (found) return found;
  }
  return null;
}

export function getRootFolders(tree) {
  if (!tree?.folders) return [];
  return tree.folders.filter((f) => !f.is_trash);
}

export function getAllNonTrashFolders(folders) {
  const result = [];
  for (const f of folders || []) {
    if (f.is_trash) continue;
    result.push(f);
    result.push(...getAllNonTrashFolders(f.children));
  }
  return result;
}

export function findDefaultRoot(tree) {
  const roots = getRootFolders(tree);
  return roots.find((f) => f.title.toLowerCase() === "manuscript") || roots[0] || null;
}

/**
 * Return an array of ancestor folder IDs for a given object in the tree.
 * For a folder, this is [parent, grandparent, ...] (not including itself).
 * For a file, this is [containing folder, its parent, ...].
 */
export function getAncestorFolderIds(folders, objectType, objectId) {
  const path = [];
  if (_findPath(folders, objectType, objectId, path)) {
    // path is [root, ..., parent] — the chain of folders leading to the object
    return path.map((f) => f.id);
  }
  return [];
}

function _findPath(folders, objectType, objectId, path) {
  for (const f of folders || []) {
    if (objectType === "folder" && f.id === objectId) {
      return true;
    }
    if (objectType === "file") {
      const found = (f.items || []).some((item) => item.id === objectId);
      if (found) {
        path.push(f);
        return true;
      }
    }
    path.push(f);
    if (_findPath(f.children, objectType, objectId, path)) {
      return true;
    }
    path.pop();
  }
  return false;
}

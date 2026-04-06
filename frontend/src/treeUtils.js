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

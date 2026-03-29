const API_BASE = "/api";

function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? match[2] : null;
}

async function request(url, options = {}) {
  const res = await fetch(url, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken") || "",
      ...options.headers,
    },
  });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) {
    const msg = data.detail || data.username?.[0] || JSON.stringify(data);
    throw new Error(msg);
  }
  return data;
}

// Config
export const fetchConfig = () =>
  request(`${API_BASE}/config/`);

// Translations
export const fetchTranslations = () =>
  request(`${API_BASE}/i18n/strings/`);

// Auth
export const register = (username, password) =>
  request(`${API_BASE}/auth/register/`, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const login = (username, password) =>
  request(`${API_BASE}/auth/login/`, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const logout = () =>
  request(`${API_BASE}/auth/logout/`, { method: "POST" });

export const fetchMe = () => request(`${API_BASE}/auth/me/`);

// OIDC
const OIDC_REDIRECT_URI = `${window.location.origin}/oidc/callback`;

export const oidcLogin = () =>
  request(
    `${API_BASE}/auth/oidc/login/?redirect_uri=${encodeURIComponent(OIDC_REDIRECT_URI)}`
  );

export const oidcCallback = (code, state) =>
  request(`${API_BASE}/auth/oidc/callback/`, {
    method: "POST",
    body: JSON.stringify({ code, state, redirect_uri: OIDC_REDIRECT_URI }),
  });

export const oidcLink = (code, state) =>
  request(`${API_BASE}/auth/oidc/link/`, {
    method: "POST",
    body: JSON.stringify({ code, state, redirect_uri: OIDC_REDIRECT_URI }),
  });

export const oidcUnlink = (identityId) =>
  request(`${API_BASE}/auth/oidc/unlink/${identityId}/`, {
    method: "DELETE",
  });

// Project Editor
export const fetchProjects = () =>
  request(`${API_BASE}/projects/`);

export const createProject = (title, description = "") =>
  request(`${API_BASE}/projects/`, {
    method: "POST",
    body: JSON.stringify({ title, description }),
  });

export const deleteProject = (projectId) =>
  request(`${API_BASE}/projects/${projectId}/`, { method: "DELETE" });

export const updateProject = (projectId, data) =>
  request(`${API_BASE}/projects/${projectId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const createFolder = (projectId, title, order = 0, parentId = null) =>
  request(`${API_BASE}/projects/${projectId}/folders/`, {
    method: "POST",
    body: JSON.stringify({ title, order, ...(parentId ? { parent: parentId } : {}) }),
  });

export const deleteFolder = (projectId, folderId) =>
  request(`${API_BASE}/projects/${projectId}/folders/${folderId}/`, { method: "DELETE" });

export const updateFolder = (projectId, folderId, data) =>
  request(`${API_BASE}/projects/${projectId}/folders/${folderId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const createText = (projectId, folderId, title, order = 0) =>
  request(`${API_BASE}/projects/${projectId}/folders/${folderId}/texts/`, {
    method: "POST",
    body: JSON.stringify({ title, order }),
  });

export const deleteText = (projectId, fileId) =>
  request(`${API_BASE}/projects/${projectId}/texts/${fileId}/`, { method: "DELETE" });

export const updateText = (projectId, fileId, data) =>
  request(`${API_BASE}/projects/${projectId}/texts/${fileId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const fetchProjectTree = (projectId) =>
  request(`${API_BASE}/projects/${projectId}/tree/`);

export const reorderTree = (projectId, folders, texts) =>
  request(`${API_BASE}/projects/${projectId}/reorder/`, {
    method: "POST",
    body: JSON.stringify({ folders, texts }),
  });

export const fetchFile = (fileId) =>
  request(`${API_BASE}/files/${fileId}/`);

export const saveDraftCache = (fileId, content) =>
  request(`${API_BASE}/files/${fileId}/cache/`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });

export const fetchVersions = (fileId) =>
  request(`${API_BASE}/files/${fileId}/versions/`);

export const createVersion = (fileId, content) =>
  request(`${API_BASE}/files/${fileId}/versions/`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });

export const fetchVersion = (fileId, versionId) =>
  request(`${API_BASE}/files/${fileId}/versions/${versionId}/`);

export const revertVersion = (fileId, versionId) =>
  request(`${API_BASE}/files/${fileId}/versions/${versionId}/revert/`, {
    method: "POST",
  });


// Import helpers (multipart file upload)
export const importScrivener = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/projects/import/scrivener/`, {
    method: "POST",
    credentials: "include",
    headers: {
      "X-CSRFToken": getCookie("csrftoken") || "",
    },
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || JSON.stringify(data));
  }
  return data;
};


export const importYWriter = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/projects/import/ywriter/`, {
    method: "POST",
    credentials: "include",
    headers: {
      "X-CSRFToken": getCookie("csrftoken") || "",
    },
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || JSON.stringify(data));
  }
  return data;
};

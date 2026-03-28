# Storyteller Frontend

React single-page application for the Storyteller writing tool, built with Vite.

## Prerequisites

- Node.js 18+
- npm

## Quick Start

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The app will be available at `http://localhost:5173`.

The Vite dev server proxies all `/api` requests to the Django backend at `http://127.0.0.1:8000`, so make sure the backend is running first.

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the Vite dev server with HMR |
| `npm run build` | Build for production into `dist/` |
| `npm run preview` | Preview the production build locally |

## Key Dependencies

| Package | Purpose |
|---|---|
| `react` / `react-dom` | UI framework |
| `@tiptap/react` + `@tiptap/starter-kit` | Rich text editor (ProseMirror-based) |
| `tiptap-markdown` | Markdown serialization for TipTap |
| `@tiptap/extension-link` | Link support in the editor |
| `react-arborist` | Drag-and-drop project tree |

## Project Structure

```
frontend/
├── index.html           # HTML entry point
├── vite.config.js       # Vite config (dev server, proxy, plugins)
├── package.json
└── src/
    ├── main.jsx         # React entry point, I18nProvider wrapper
    ├── App.jsx          # Root component: auth, dashboard, routing
    ├── AuthForm.jsx     # Login / register form
    ├── OIDCCallback.jsx # OIDC redirect handler
    ├── I18nContext.jsx   # Internationalization context provider
    ├── EditorView.jsx   # Main editor layout (tree + editor + panels)
    ├── ProjectTree.jsx  # File/folder tree (react-arborist)
    ├── TipTapEditor.jsx # TipTap rich text editor wrapper
    ├── FormattingToolbar.jsx  # Bold, italic, headings, etc.
    ├── PropertiesPanel.jsx    # Folder/text metadata editor
    ├── VersionHistoryPanel.jsx # Version snapshots and revert
    ├── ImportModal.jsx  # Project import dialog (Scrivener, yWriter7)
    └── api.js           # All backend API helper functions
```

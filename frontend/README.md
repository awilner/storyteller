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

The Vite dev server proxies:
- `/api` → Django backend at `http://127.0.0.1:8000`
- `/ws` → Django Channels WebSocket at `ws://127.0.0.1:8000`
- `/yjs` → HocusPocus WebSocket at `ws://127.0.0.1:1234`

Make sure the backend is running first. For collaborative editing, also start the [HocusPocus server](../hocuspocus/README.md).

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
| `@tiptap/extension-collaboration` | Yjs document sync for collaborative editing |
| `@tiptap/extension-collaboration-cursor` | Remote cursor rendering |
| `yjs` | CRDT library for conflict-free collaborative editing |
| `y-websocket` | WebSocket provider connecting to HocusPocus |
| `react-arborist` | Drag-and-drop project tree |

## Project Structure

```
frontend/
├── index.html
├── vite.config.js           # Dev server config with API/WS/Yjs proxies
├── package.json
└── src/
    ├── main.jsx              # React entry point, I18nProvider + FontContext
    ├── App.jsx               # Root: auth, dashboard, routing, project list
    ├── api.js                # All backend API helpers
    ├── treeUtils.js          # Shared tree utility functions
    │
    ├── AuthForm.jsx          # Login / register form
    ├── OIDCCallback.jsx      # OIDC redirect handler
    ├── I18nContext.jsx        # Internationalization context provider
    ├── FontContext.jsx        # Editor font context provider
    ├── useIsMobile.jsx       # Mobile breakpoint hook
    ├── useProjectWebSocket.js # WebSocket hook for real-time project events
    │
    ├── EditorView.jsx        # Main editor layout (tree + editor + panels)
    ├── TopBar.jsx            # App header with project/user dropdowns
    ├── ProjectTree.jsx       # File/folder tree with context menus
    ├── TipTapEditor.jsx      # TipTap rich text editor with collaboration
    ├── FormattingToolbar.jsx # Bold, italic, headings toolbar
    ├── FolderView.jsx        # Rendered folder contents view
    ├── MarkdownRenderer.jsx  # Markdown-to-rendered-text via TipTap
    │
    ├── PropertiesPanel.jsx   # Folder/text metadata (POV, label, status)
    ├── VersionHistoryPanel.jsx # Version snapshots and revert
    ├── VersionBadge.jsx      # Version indicator badge
    │
    ├── SharingPanel.jsx      # Project sharing management UI
    ├── ObjectPermissionPanel.jsx # Per-object permission overrides
    ├── ProgressPage.jsx      # Progress tracking, targets, charts, ranking
    │
    ├── CompileDialog.jsx     # Compile manuscript dialog
    ├── LayoutEditor.jsx      # Shared compile layout settings editor
    ├── ProjectSettings.jsx   # Project settings (labels, statuses, tree, layouts)
    ├── MetadataListManager.jsx # Reusable drag-and-drop list (labels/statuses)
    ├── LabelManager.jsx      # Label manager (thin wrapper)
    ├── StatusManager.jsx     # Status manager (thin wrapper)
    │
    ├── ImportModal.jsx       # Project import dialog
    ├── AccountPage.jsx       # User account (password, OIDC)
    ├── SettingsPage.jsx      # User settings (default font)
    │
    ├── *.css                 # Per-component stylesheets
    └── common.css            # Shared utility styles
```

## Real-Time Project Events

The `useProjectWebSocket` hook connects to `/ws/projects/<id>/` and dispatches incoming events to named handler callbacks. EditorView registers handlers that refresh the relevant UI state.

### Handled Event Types

| Event | Handler | Action |
|---|---|---|
| `tree_changed` | `onTreeChanged` | Re-fetches the project tree |
| `settings_changed` | `onSettingsChanged` | Re-fetches the project tree (includes settings) |
| `labels_changed` | `onLabelsChanged` | Re-fetches the project tree (includes labels) |
| `statuses_changed` | `onStatusesChanged` | Re-fetches the project tree (includes statuses) |
| `layouts_changed` | `onLayoutsChanged` | Re-fetches the project tree |
| `permission_changed` | `onPermissionChanged` | Updates role, re-fetches tree and overrides |
| `access_revoked` | `onAccessRevoked` | Shows alert and redirects to dashboard |

### Adding a Handler for a New Event Type

The hook uses a `HANDLER_MAP` to map event type strings to handler names. To handle a new backend event:

1. Add the mapping to `HANDLER_MAP` in `useProjectWebSocket.js`:
   ```js
   const HANDLER_MAP = {
     // ...existing entries...
     my_new_event: "onMyNewEvent",
   };
   ```
2. Add the handler in EditorView's `wsHandlers`:
   ```js
   onMyNewEvent: (data) => { /* refresh relevant state */ },
   ```

Alternatively, any unrecognised event type is passed to `onProjectEvent` if provided — useful for logging or generic handling without modifying the hook.

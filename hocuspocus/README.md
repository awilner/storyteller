# Storyteller HocusPocus Server

Node.js [HocusPocus](https://tiptap.dev/hocuspocus) server that provides real-time collaborative editing for Storyteller via Yjs CRDTs.

## How It Works

When a user opens a document in the editor, the frontend connects to HocusPocus over a WebSocket (`/yjs/file-<id>/`). HocusPocus authenticates the connection by calling back to the Django backend's internal auth endpoint, which validates the user's session cookie and returns their permission level. Co-authors get read-write access; read-only users get a live-updating read-only view.

Multiple users editing the same document see each other's cursors and changes in real time. Conflict resolution is handled by Yjs CRDTs — no operational transform server logic is needed.

## Prerequisites

- Node.js 18+
- npm

## Quick Start

```bash
cd hocuspocus
npm install

# Start with defaults (no Redis, in-memory document storage)
HOCUSPOCUS_AUTH_URL=http://127.0.0.1:8000/api/internal/yjs-auth/ npm start
```

The server will listen on `ws://localhost:1234`.

Make sure the Django backend is running at `http://127.0.0.1:8000` so the auth callback works.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HOCUSPOCUS_AUTH_URL` | `http://backend:8000/api/internal/yjs-auth/` | Django endpoint for authenticating WebSocket connections |
| `HOCUSPOCUS_SECRET` | — | Shared secret sent in the `X-Hocuspocus-Secret` header to the auth endpoint |
| `HOCUSPOCUS_PORT` | `1234` | Port to listen on |
| `REDIS_URL` | — | Redis URL for document sync across instances. If not set, documents are stored in memory (fine for local dev). |

## Running Without Redis

For local development, Redis is not required. Without `REDIS_URL`, HocusPocus stores documents in memory. This means:
- Document state is lost when the server restarts
- Only a single HocusPocus instance can run (no cross-instance sync)

This is fine for local testing. Set `REDIS_URL` in production for persistence and multi-instance scaling.

## Running With Redis

```bash
HOCUSPOCUS_AUTH_URL=http://127.0.0.1:8000/api/internal/yjs-auth/ \
REDIS_URL=redis://127.0.0.1:6379 \
npm start
```

## Authentication Flow

1. Frontend opens a WebSocket to `/yjs/file-<id>/`, passing the session cookie
2. HocusPocus extracts the file ID from the document name and forwards the cookie to the Django auth endpoint
3. Django validates the session, checks the user's permission on the file's project, and returns `{user_id, username, colour, permission}`
4. HocusPocus accepts or rejects the connection based on the response
5. Read-only users have their connection set to `readOnly` mode

## Dependencies

| Package | Purpose |
|---|---|
| `@hocuspocus/server` | Yjs WebSocket server with lifecycle hooks |
| `@hocuspocus/extension-redis` | Redis extension for document persistence and cross-instance sync |
| `node-fetch` | HTTP client for the auth callback to Django |

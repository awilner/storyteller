<div align="center" width="100%">
  <img src="frontend/resources/Storyteller.svg" alt="Storyteller" height="100" />
</div>

---

[![Build and Publish](https://github.com/awilner/storyteller/actions/workflows/docker-image-ci-build.yml/badge.svg)](https://github.com/awilner/storyteller/actions/workflows/docker-image-ci-build.yml)
![GitHub Release](https://img.shields.io/github/v/release/awilner/storyteller)

# Storyteller

A web-based writing application for novelists and authors. Organize your manuscript into chapters and scenes, manage characters, locations, and notes, track progress with labels and statuses, and compile your work into multiple output formats.

## About The Project
I created this after looking for a self-hosted version of apps like Scrivener or Manuskript, mainly because I couldn't install them on a company-issued laptop and remote connection tools like VNC are also not allowed.

## Features

- Hierarchical project tree with drag-and-drop reordering
- Rich text editor (TipTap/ProseMirror) with markdown storage
- Characters, locations, items, and notes alongside your manuscript
- POV character, label, and status metadata per folder/text
- Configurable colour coding in the project tree
- Compile to DOCX, PDF, EPUB, RTF, LaTeX, Markdown, and MOBI (via Pandoc)
- Customizable compile layouts (fonts, margins, chapter headings, scene separators)
- Front matter and back matter support
- Version history with revert
- Trash folder with soft-delete and permanent delete
- Import from Scrivener (.scriv.zip) and yWriter7 (.yw7)
- Export to Scrivener and yWriter formats
- Duplicate items and copy between projects
- OIDC single sign-on (optional)
- Internationalization support
- Mobile-responsive layout

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Frontend │────▶│ Backend  │────▶│ MariaDB  │
│  nginx   │:80  │ gunicorn │:8000│          │:3306
│          │     │  Pandoc  │────▶│  Redis   │:6379
└──────────┘     └──────────┘     └──────────┘
```

- Frontend: React SPA served by nginx, proxies `/api/` to the backend
- Backend: Django + Django REST Framework with Pandoc for document compilation
- MariaDB: persistent storage for projects, folders, files, metadata
- Redis: draft caching layer

## Deployment with Docker

Pre-built images are available from GitHub Container Registry.

### 1. Get the configuration files

Copy [`docker/docker-compose.yml`](docker/docker-compose.yml) and [`docker/.env.example`](docker/.env.example) to your deployment directory:

```bash
mkdir storyteller && cd storyteller
curl -O https://raw.githubusercontent.com/awilner/storyteller/main/docker/docker-compose.yml
curl -O https://raw.githubusercontent.com/awilner/storyteller/main/docker/.env.example
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set real values for at least:
- `DJANGO_SECRET_KEY` — a long random string
- `DB_PASSWORD` and `MARIADB_ROOT_PASSWORD` — database credentials
- `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` — your domain (e.g. `https://my.domain.com`)
- `COOKIE_SECURE=True` — when serving over HTTPS

See [`docker/.env.example`](docker/.env.example) for all available options.

### 3. Start the stack

```bash
docker compose up -d
```

The application is now available at `http://localhost` (or your configured domain behind a reverse proxy).

### HTTPS

Storyteller expects to run behind a reverse proxy (e.g. Caddy, Traefik, or nginx) that terminates TLS. The frontend nginx container listens on port 80 and forwards the `X-Forwarded-Proto` header to the backend. Set `COOKIE_SECURE=True` in `.env` when serving over HTTPS.

### Updating

```bash
docker compose pull
docker compose up -d
```

Migrations run automatically on backend startup.

## Local Development

See the individual READMEs for development setup:

- [Backend](backend/README.md) — Django API, Python 3.10+
- [Frontend](frontend/README.md) — React SPA, Node.js 18+
- [Docker](docker/README.md) — Building images locally

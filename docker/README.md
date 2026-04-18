# Docker Setup

Run the full Storyteller stack with five containers: frontend (nginx), backend (Django/Daphne), HocusPocus (Yjs collaborative editing), MariaDB, and Redis.

## Quick Start

```bash
cd docker

# Create your .env from the example
cp .env.example .env
# Edit .env — at minimum set DJANGO_SECRET_KEY, DB_PASSWORD,
# MARIADB_ROOT_PASSWORD, HOCUSPOCUS_SECRET

# Start the stack (pulls images from ghcr.io)
docker compose up -d

# Create a superuser (first time only)
docker compose exec backend python manage.py createsuperuser
```

The app will be available at `http://localhost`.

## Building Images Locally

If you want to build the images yourself instead of pulling from the registry:

```bash
# From the project root
docker build -t ghcr.io/awilner/storyteller/backend:latest ./backend
docker build -t ghcr.io/awilner/storyteller/frontend:latest ./frontend
docker build -t ghcr.io/awilner/storyteller/hocuspocus:latest ./hocuspocus

# Then start the stack as usual
cd docker
docker compose up -d
```

## Architecture

```
┌──────────┐     ┌──────────────┐     ┌──────────┐
│ Frontend │────▶│   Backend    │────▶│ MariaDB  │
│  nginx   │:80  │ Daphne/ASGI  │:8000│          │:3306
│          │     └──────────────┘     │          │
│          │            │             └──────────┘
│          │     ┌──────────────┐     ┌──────────┐
│          │────▶│ HocusPocus   │────▶│  Redis   │:6379
│          │     │  Yjs server  │:1234│          │
└──────────┘     └──────────────┘     └──────────┘
```

- **nginx** serves the React SPA and proxies `/api/` to the backend, `/ws/` to Django Channels, `/yjs/` to HocusPocus
- **Backend** runs Django with Daphne (ASGI) for HTTP and WebSocket support, plus Pandoc and LaTeX for document compilation
- **HocusPocus** is a Node.js Yjs WebSocket server for real-time collaborative editing, authenticating via callback to the Django backend
- **MariaDB** stores all application data
- **Redis** serves as the Django Channels channel layer, HocusPocus document sync backend, and draft cache

## Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | Service definitions and orchestration |
| `.env.example` | Template for environment variables |

Each service's `Dockerfile`, `entrypoint.sh`, and `nginx.conf` live in their own directory (`backend/`, `frontend/`, `hocuspocus/`).

## Environment Variables

See [backend README](../backend/README.md) for the full list. Key variables:

| Variable | Required | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Random secret for production |
| `DB_PASSWORD` | Yes | MariaDB user password |
| `MARIADB_ROOT_PASSWORD` | Yes | MariaDB root password |
| `HOCUSPOCUS_SECRET` | Yes | Shared secret between HocusPocus and backend |
| `CORS_ALLOWED_ORIGINS` | Yes | Your domain (e.g. `https://my.domain.com`) |
| `CSRF_TRUSTED_ORIGINS` | Yes | Same as CORS origins |
| `COOKIE_SECURE` | Recommended | `True` when behind HTTPS |

## Useful Commands

```bash
# View logs
docker compose logs -f backend
docker compose logs -f hocuspocus

# Run Django management commands
docker compose exec backend python manage.py shell

# Run tests
docker compose exec backend python manage.py test api

# Stop everything
docker compose down

# Stop and remove volumes (deletes database)
docker compose down -v

# Update to latest images
docker compose pull
docker compose up -d
```

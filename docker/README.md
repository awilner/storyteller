# Docker Setup

Run the full Storyteller stack with four containers: frontend (nginx), backend (Django/gunicorn/Pandoc), MariaDB, and Redis.

## Quick Start

```bash
cd docker

# Create your .env from the example
cp .env.example .env
# Edit .env — at minimum set DJANGO_SECRET_KEY, DB_PASSWORD, MARIADB_ROOT_PASSWORD

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
docker build -f docker/backend.Dockerfile -t ghcr.io/awilner/storyteller/backend:latest .
docker build -f docker/frontend.Dockerfile -t ghcr.io/awilner/storyteller/frontend:latest .

# Then start the stack as usual
cd docker
docker compose up -d
```

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Frontend │────▶│ Backend  │────▶│ MariaDB  │
│  nginx   │:80  │ gunicorn │:8000│          │:3306
│          │     │  Pandoc  │────▶│  Redis   │:6379
└──────────┘     └──────────┘     └──────────┘
```

- nginx serves the React SPA and proxies `/api/` to the backend
- The backend runs Django with gunicorn, plus Pandoc and LaTeX for document compilation
- MariaDB stores all application data
- Redis provides persistent draft caching

## Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | Service definitions and orchestration |
| `backend.Dockerfile` | Python 3.12 + Pandoc + LaTeX + Calibre |
| `frontend.Dockerfile` | Multi-stage: Node (build) → nginx (serve) |
| `nginx.conf` | nginx config with API proxy and SPA fallback |
| `entrypoint.sh` | Runs migrations before starting gunicorn |
| `.env.example` | Template for environment variables |

## Environment Variables

See [backend README](../backend/README.md) for the full list. Key variables:

| Variable | Required | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Random secret for production |
| `DB_PASSWORD` | Yes | MariaDB user password |
| `MARIADB_ROOT_PASSWORD` | Yes | MariaDB root password |
| `CORS_ALLOWED_ORIGINS` | Yes | Your domain (e.g. `https://my.domain.com`) |
| `CSRF_TRUSTED_ORIGINS` | Yes | Same as CORS origins |
| `COOKIE_SECURE` | Recommended | `True` when behind HTTPS |

## Useful Commands

```bash
# View logs
docker compose logs -f backend

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

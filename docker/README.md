# Docker Setup

Run the full Storyteller stack with four containers: frontend (nginx), backend (Django/gunicorn), MariaDB, and Redis.

## Quick Start

```bash
cd docker

# Create your .env from the example and edit it
cp .env.example .env
# At minimum, change DJANGO_SECRET_KEY, DB_PASSWORD, and MARIADB_ROOT_PASSWORD

# Build the images (from the project root)
cd ..
docker build -f docker/backend.Dockerfile -t storyteller-backend .
docker build -f docker/frontend.Dockerfile -t storyteller-frontend .

# Start the stack
cd docker
docker compose up -d

# Create a superuser (first time only)
docker compose exec backend python manage.py createsuperuser
```

The app will be available at `http://localhost`.

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Frontend │────▶│ Backend  │────▶│ MariaDB  │
│  nginx   │:80  │ gunicorn │:8000│          │:3306
│          │     │          │────▶│  Redis   │
└──────────┘     └──────────┘     └──────────┘
```

- nginx serves the React SPA and proxies `/api/` to the backend
- The backend runs Django with gunicorn
- MariaDB stores all application data
- Redis provides persistent draft caching

## Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | Service definitions and orchestration |
| `backend.Dockerfile` | Python image with Django + gunicorn |
| `frontend.Dockerfile` | Multi-stage build: Node (build) → nginx (serve) |
| `nginx.conf` | nginx config with API proxy and SPA fallback |
| `.env.example` | Template for environment variables |

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
```

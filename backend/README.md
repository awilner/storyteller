# Storyteller Backend

Django + Django REST Framework API for the Storyteller writing application.

## Prerequisites

- Python 3.10+
- pip
- Pandoc
- DefusedXML (for handling yWriter imports safely)

## Quick Start

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create a superuser (optional)
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/api/`.

## Running Tests

```bash
python manage.py test api
```

## Environment Variables

All settings have sensible defaults for local development (SQLite, in-memory cache, debug mode). Override via environment variables for production.

### Core

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | insecure dev key | Secret key for cryptographic signing |
| `DJANGO_DEBUG` | `True` | Set to `False` in production |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed hostnames |
| `CORS_ALLOWED_ORIGINS` | — | Comma-separated origins for CORS |
| `CSRF_TRUSTED_ORIGINS` | — | Comma-separated trusted origins for CSRF |
| `COOKIE_SECURE` | `False` | Set to `True` when serving over HTTPS |
| `LANGUAGE_CODE` | `en` | Default language |

### Database

SQLite is used by default. Set `DB_ENGINE=mariadb` to use MariaDB.

| Variable | Default | Description |
|---|---|---|
| `DB_ENGINE` | `sqlite` | `sqlite` or `mariadb` |
| `DB_PATH` | `db.sqlite3` | SQLite file path |
| `DB_NAME` | `app` | MariaDB database name |
| `DB_USER` | `root` | MariaDB user |
| `DB_PASSWORD` | — | MariaDB password |
| `DB_HOST` | `127.0.0.1` | MariaDB host |
| `DB_PORT` | `3306` | MariaDB port |

### Cache

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | — | Redis URL (e.g. `redis://localhost:6379/0`). Falls back to in-memory cache. |

### OIDC (Optional)

| Variable | Default | Description |
|---|---|---|
| `OIDC_DISCOVERY_URL` | — | OpenID Connect discovery URL |
| `OIDC_CLIENT_ID` | — | OAuth2 client ID |
| `OIDC_CLIENT_SECRET` | — | OAuth2 client secret |

## Project Structure

```
backend/
├── config/              # Django settings, root URLs, WSGI
├── api/
│   ├── models.py        # Project, Folder, ProjectFile, FileVersion,
│   │                    # Label, Status, CompileLayout, OIDCIdentity, UserSettings
│   ├── views/         # All API endpoints
│   ├── serializers.py   # DRF serializers
│   ├── urls.py          # URL routing
│   ├── permissions.py   # IsProjectOwner permission
│   ├── translations.py  # i18n strings served to the frontend
│   ├── oidc.py          # OIDC token exchange helpers
│   ├── scrivener.py     # Scrivener (.scriv.zip) importer
│   ├── ywriter.py       # yWriter7 (.yw7) importer
│   ├── exporters.py     # Scrivener and yWriter exporters
│   ├── compiler/        # Manuscript compile engine

│   ├── migrations/
│   └── tests/
├── locale/              # Translation message files
├── manage.py
└── requirements.txt
```

## Key Dependencies

| Package | Purpose |
|---|---|
| Django | Web framework |
| djangorestframework | REST API |
| django-cors-headers | CORS support |
| django-redis | Redis cache backend |
| striprtf | RTF-to-text for Scrivener import |
| pypandoc | Pandoc wrapper for compile (DOCX, PDF, EPUB, etc.) |
| PyJWT | JWT handling for OIDC |
| mysqlclient | MariaDB driver (production only) |
| defusedxml | safely handle imported XML files |

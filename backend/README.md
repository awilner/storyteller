# Storyteller Backend

Django + Django REST Framework API for the Storyteller writing application, with Django Channels for real-time WebSocket communication.

## Prerequisites

- Python 3.10+
- pip
- Pandoc (for document compilation)

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

For collaborative editing, also start the [HocusPocus server](../hocuspocus/README.md).

## Running Tests

```bash
python manage.py test api
```

This runs unit tests, integration tests, and property-based tests (Hypothesis).

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

### Cache and Channels

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | — | Redis URL (e.g. `redis://localhost:6379/0`). Falls back to in-memory cache. Also used as the Django Channels channel layer when set. |

### HocusPocus Integration

| Variable | Default | Description |
|---|---|---|
| `HOCUSPOCUS_SECRET` | — | Shared secret for authenticating HocusPocus auth callbacks |

### OIDC (Optional)

| Variable | Default | Description |
|---|---|---|
| `OIDC_DISCOVERY_URL` | — | OpenID Connect discovery URL |
| `OIDC_CLIENT_ID` | — | OAuth2 client ID |
| `OIDC_CLIENT_SECRET` | — | OAuth2 client secret |

## Project Structure

```
backend/
├── config/              # Django settings, root URLs, ASGI/WSGI
├── api/
│   ├── views/           # API endpoints
│   │   ├── auth.py      # Login, register, session management
│   │   ├── project.py   # Project CRUD
│   │   ├── sharing.py   # Project sharing, permissions, Yjs auth callback
│   │   ├── progress.py  # Per-user progress tracking, contribution ranking
│   │   ├── compile.py   # Manuscript compilation
│   │   ├── import_export.py # Scrivener and yWriter import/export
│   │   ├── label.py     # Label management
│   │   ├── status.py    # Status management
│   │   ├── layout.py    # Compile layout management
│   │   └── oidc.py      # OIDC authentication
│   ├── compiler/        # Manuscript compile engine
│   ├── import_export/   # Scrivener and yWriter importers/exporters
│   ├── models.py        # Project, Folder, ProjectFile, FileVersion,
│   │                    # Label, Status, CompileLayout, ProjectShare,
│   │                    # ObjectPermissionOverride, UserProgressSettings,
│   │                    # DailyWordCount, SessionWordCount,
│   │                    # ManuscriptWordCount, OIDCIdentity, UserSettings
│   ├── serializers.py   # DRF serializers
│   ├── consumers.py     # Django Channels WebSocket consumers
│   ├── broadcast.py     # Centralised WebSocket broadcast helper
│   ├── routing.py       # Channels WebSocket URL routing
│   ├── urls.py          # HTTP URL routing
│   ├── permissions.py   # Role-based project permissions
│   ├── progress.py      # Word count computation, contribution ranking
│   ├── translations.py  # i18n strings served to the frontend
│   ├── oidc.py          # OIDC token exchange helpers
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
| channels | Django Channels for WebSocket support |
| channels-redis | Redis channel layer for Channels |
| daphne | ASGI server (replaces gunicorn for WebSocket support) |
| django-redis | Redis cache backend |
| striprtf | RTF-to-text for Scrivener import |
| pypandoc | Pandoc wrapper for compile (DOCX, PDF, EPUB, etc.) |
| hypothesis | Property-based testing |
| PyJWT | JWT handling for OIDC |
| mysqlclient | MariaDB driver (production only) |
| defusedxml | Safely handle imported XML files |

## Real-Time Broadcast System

The backend broadcasts project-level events to all connected WebSocket clients so collaborators see changes immediately without refreshing.

### How It Works

1. A view performs a mutation (e.g. creates a folder)
2. The view calls `broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)`
3. `broadcast.py` sends a message to the `project_{pk}` Channels group
4. The `ProjectConsumer.project_event()` handler forwards the payload to every connected client
5. The frontend WebSocket hook dispatches to the appropriate handler based on the `type` field

### Usage

```python
from ..broadcast import broadcast_project_event

# In any view, after a successful mutation:
broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)

# Extra keyword arguments are included in the payload:
broadcast_project_event(project_pk, "settings_changed", user_id=request.user.id, fields=["title"])
```

### Event Types

| Event | Source views | Description |
|---|---|---|
| `tree_changed` | `project.py` | Folder/file create, update, delete, reorder, duplicate, copy, empty trash |
| `settings_changed` | `project.py` | Project title, description, or settings updated |
| `labels_changed` | `label.py` | Label created, updated, or deleted |
| `statuses_changed` | `status.py` | Status created, updated, or deleted |
| `layouts_changed` | `layout.py` | Compile layout created, updated, or deleted |
| `permission_changed` | `sharing.py` | Share or per-object override created, updated, or deleted |

`access_revoked` is a special case that uses a dedicated Channels message type (not `project_event`) because the consumer needs to close the affected user's WebSocket connection.

### Adding a New Event Type

1. Pick a descriptive name (e.g. `"my_feature_changed"`)
2. Call `broadcast_project_event(project_pk, "my_feature_changed", ...)` in your view
3. Optionally add a named handler in the frontend (`onMyFeatureChanged`), or use the generic `onProjectEvent` fallback

No changes to `consumers.py` or `broadcast.py` are needed — the system is fully generic.

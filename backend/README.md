# Storyteller Backend

Django + Django REST Framework API for the Storyteller writing application.

## Prerequisites

- Python 3.10+
- pip

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

# Create a superuser (optional, for Django admin)
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

All settings have sensible defaults for local development. Override via environment variables as needed.

### Core

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | insecure dev key | Secret key for cryptographic signing. Set a real value in production. |
| `DJANGO_DEBUG` | `True` | Set to `False` in production. |

### Database

SQLite is used by default. Set `DB_ENGINE=mariadb` to use MariaDB instead.

| Variable | Default | Description |
|---|---|---|
| `DB_ENGINE` | `sqlite` | `sqlite` or `mariadb` |
| `DB_PATH` | `db.sqlite3` | SQLite file path (only when `DB_ENGINE=sqlite`) |
| `DB_NAME` | `app` | MariaDB database name |
| `DB_USER` | `root` | MariaDB user |
| `DB_PASSWORD` | *(empty)* | MariaDB password |
| `DB_HOST` | `127.0.0.1` | MariaDB host |
| `DB_PORT` | `3306` | MariaDB port |

> `mysqlclient` is only required when using MariaDB.

### Cache

Falls back to Django's in-memory cache when Redis is not configured.

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | *(empty)* | Redis connection URL, e.g. `redis://localhost:6379/0` |

### OIDC (Optional)

Enable OpenID Connect authentication by setting all three variables.

| Variable | Default | Description |
|---|---|---|
| `OIDC_DISCOVERY_URL` | *(empty)* | Provider discovery URL, e.g. `https://accounts.google.com/.well-known/openid-configuration` |
| `OIDC_CLIENT_ID` | *(empty)* | OAuth2 client ID |
| `OIDC_CLIENT_SECRET` | *(empty)* | OAuth2 client secret |

### Internationalization

| Variable | Default | Description |
|---|---|---|
| `LANGUAGE_CODE` | `en` | Default language (`en`, `es`, `fr`, `de`, `pt`) |

## Project Structure

```
backend/
├── config/          # Django project settings, root URL conf, WSGI
├── api/             # Main application
│   ├── models.py    # Project, Folder, ProjectFile, FileVersion, OIDCIdentity
│   ├── views.py     # All API endpoints
│   ├── serializers.py
│   ├── urls.py
│   ├── permissions.py
│   ├── translations.py  # i18n strings served to the frontend
│   ├── oidc.py      # OIDC token exchange helpers
│   ├── scrivener.py # Scrivener (.scriv.zip) project importer
│   ├── ywriter.py   # yWriter7 (.yw7.zip) project importer
│   ├── migrations/
│   └── tests/
├── locale/          # Translation message files
├── manage.py
└── requirements.txt
```

# Translations (i18n)

This directory contains Django translation message files used to localize the frontend UI.

## How It Works

1. All translatable UI strings are defined in `api/translations.py` using Django's `gettext()`.
2. The frontend fetches them via `GET /api/i18n/strings/`, which returns a flat JSON object of key-value pairs in the active language.
3. The active language is determined by the `Accept-Language` header or Django's locale middleware.

## Supported Languages

Configured in `config/settings.py`:

| Code | Language |
|------|----------|
| `en` | English (default) |
| `es` | Español |
| `fr` | Français |
| `de` | Deutsch |
| `pt` | Português |

## Directory Structure

```
locale/
└── <language_code>/
    └── LC_MESSAGES/
        ├── django.po    # Human-editable translation source
        └── django.mo    # Compiled binary (generated)
```

## Adding a New Language

```bash
cd backend

# Generate the .po file for a new language (e.g. Italian)
python manage.py makemessages -l it

# This creates locale/it/LC_MESSAGES/django.po
# Edit that file and fill in the msgstr translations.
```

Then add the language to `LANGUAGES` in `config/settings.py`:

```python
LANGUAGES = [
    ...
    ("it", "Italiano"),
]
```

## Updating Translations After Changing Strings

When you add or modify strings in `api/translations.py`:

```bash
cd backend

# Re-extract messages into .po files for all languages
python manage.py makemessages --all

# Edit the .po files to translate new/changed strings

# Compile .po → .mo
python manage.py compilemessages
```

## Adding a New UI String

1. Add the key and `_("English text")` call in `api/translations.py` inside `_get_ui_strings()`.
2. Run `python manage.py makemessages --all` to update `.po` files.
3. Translate the new `msgstr` entries in each language's `.po` file.
4. Run `python manage.py compilemessages`.
5. In the frontend, use `t("your.key")` via the `useI18n()` hook.

> After changing translations, hard-refresh the browser (Cmd+Shift+R) to re-fetch `/api/i18n/strings/`.

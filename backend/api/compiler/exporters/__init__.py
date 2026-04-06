"""
Format exporter registry for the compile engine.

Exporters register themselves via the ``register_exporter`` decorator.
The registry is a simple dict mapping format keys to metadata dicts
containing the export callable, content type, and file extension.
"""

EXPORTER_REGISTRY = {}


def register_exporter(format_key, content_type, extension):
    """Decorator to register a format exporter."""

    def decorator(fn):
        EXPORTER_REGISTRY[format_key] = {
            "export": fn,
            "content_type": content_type,
            "extension": extension,
        }
        return fn

    return decorator


def get_exporter(format_key):
    """Look up an exporter by format key. Raises ValueError if not found."""
    if format_key not in EXPORTER_REGISTRY:
        raise ValueError(f"Unsupported format: {format_key}")
    return EXPORTER_REGISTRY[format_key]


def get_available_formats():
    """Return list of registered format keys."""
    return list(EXPORTER_REGISTRY.keys())


# Import pandoc exporters so they auto-register on import.
from . import pandoc_exporters  # noqa: F401

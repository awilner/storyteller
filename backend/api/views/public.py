import logging
import os

from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

_GITHUB_REPO = "awilner/storyteller"
_VERSION_CACHE_KEY = "app_version_check"
_VERSION_CACHE_TTL = 3600  # 1 hour

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def config_view(request):
    """Expose non-secret frontend configuration."""
    from django.conf import settings
    return Response({
        "oidc_enabled": bool(settings.OIDC_CLIENT_ID and settings.OIDC_DISCOVERY_URL),
    })


def _read_current_version():
    version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "v0.0.0-dev"


def _check_latest_release():
    """Check GitHub API for the latest release. Returns dict or None."""
    cached = cache.get(_VERSION_CACHE_KEY)
    if cached is not None:
        return cached

    import requests as http_requests
    try:
        resp = http_requests.get(
            f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "tag": data.get("tag_name", ""),
                "url": data.get("html_url", ""),
                "name": data.get("name", ""),
            }
            cache.set(_VERSION_CACHE_KEY, result, _VERSION_CACHE_TTL)
            return result
    except Exception:
        logger.debug("Failed to check GitHub for latest release", exc_info=True)

    cache.set(_VERSION_CACHE_KEY, {}, _VERSION_CACHE_TTL)
    return {}


@api_view(["GET"])
@permission_classes([AllowAny])
def timezones_view(request):
    """Return list of common IANA timezone names."""
    from zoneinfo import available_timezones
    zones = sorted(available_timezones())
    return Response(zones)


@api_view(["GET"])
@permission_classes([AllowAny])
def version_view(request):
    """Return current app version and latest release info."""
    current = _read_current_version()
    latest = _check_latest_release()
    latest_tag = latest.get("tag", "") if latest else ""
    result = {
        "current": current,
        "repo_url": f"https://github.com/{_GITHUB_REPO}",
    }
    if latest_tag and latest_tag != current and latest_tag != "":
        result["latest"] = latest_tag
        result["latest_url"] = latest.get("url", "")
        result["latest_name"] = latest.get("name", "")
    return Response(result)

import datetime
import logging
import os
import secrets

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .exporters import export_scrivener, export_ywriter
from .models import CompileLayout, DailyWordCount, FileVersion, Folder, Label, ManuscriptWordCount, OIDCIdentity, Project, ProjectFile, SessionWordCount, Status
from django.db import models as db_models
from .oidc import exchange_code_for_claims, get_authorization_url
from .permissions import IsProjectOwner
from .scrivener import import_scrivener_zip
from .ywriter import import_ywriter
from .compiler.engine import CompileEngine
from .progress import compute_project_word_count
from .serializers import (
    CompileLayoutSerializer,
    CompileRequestSerializer,
    DailyWordCountSerializer,
    FileVersionDetailSerializer,
    FileVersionListSerializer,
    FolderCreateSerializer,
    FolderUpdateSerializer,
    LabelSerializer,
    ManuscriptWordCountSerializer,
    ProjectCreateSerializer,
    ProjectListSerializer,
    ProjectTreeSerializer,
    ProjectUpdateSerializer,
    RegisterSerializer,
    SessionWordCountSerializer,
    StatusSerializer,
    TextCreateSerializer,
    TextUpdateSerializer,
    UserSerializer,
)


# ── Public config ─────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def config_view(request):
    """Expose non-secret frontend configuration."""
    from django.conf import settings
    return Response({
        "oidc_enabled": bool(settings.OIDC_CLIENT_ID and settings.OIDC_DISCOVERY_URL),
    })


_GITHUB_REPO = "awilner/storyteller"
_VERSION_CACHE_KEY = "app_version_check"
_VERSION_CACHE_TTL = 3600  # 1 hour

logger = logging.getLogger(__name__)


def _read_current_version():
    version_file = os.path.join(os.path.dirname(__file__), "VERSION")
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

    # Cache empty result to avoid hammering GitHub on errors
    cache.set(_VERSION_CACHE_KEY, {}, _VERSION_CACHE_TTL)
    return {}


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


# ── Local auth ────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    login(request, user)
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": _("Invalid credentials.")},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({"detail": _("Logged out.")})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Change the authenticated user's password."""
    current_password = request.data.get("current_password", "")
    new_password = request.data.get("new_password", "")
    if not current_password or not new_password:
        return Response(
            {"detail": _("Both current and new password are required.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not request.user.check_password(current_password):
        return Response(
            {"detail": _("Current password is incorrect.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(new_password) < 8:
        return Response(
            {"detail": _("New password must be at least 8 characters.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    request.user.set_password(new_password)
    request.user.save()
    login(request, request.user)  # Re-login to refresh session
    return Response({"detail": _("Password changed.")})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def user_settings_view(request):
    """Get or update the authenticated user's preferences."""
    from .models import UserSettings
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    if request.method == "GET":
        return Response(settings_obj.preferences)
    # PATCH — merge incoming keys into existing preferences
    if not isinstance(request.data, dict):
        return Response(
            {"detail": _("Expected a JSON object.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    settings_obj.preferences.update(request.data)
    settings_obj.save()
    return Response(settings_obj.preferences)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    """Return the currently authenticated user."""
    return Response(UserSerializer(request.user).data)


# ── OIDC auth ─────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def oidc_login_view(request):
    """Return the OIDC authorization URL. Frontend redirects the browser there."""
    redirect_uri = request.query_params.get("redirect_uri", "")
    if not redirect_uri:
        return Response(
            {"detail": _("redirect_uri query param is required.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    state = secrets.token_urlsafe(32)
    request.session["oidc_state"] = state
    url = get_authorization_url(redirect_uri, state)
    return Response({"authorization_url": url})


@api_view(["POST"])
@permission_classes([AllowAny])
def oidc_callback_view(request):
    code = request.data.get("code", "")
    redirect_uri = request.data.get("redirect_uri", "")
    state = request.data.get("state", "")

    if not code or not redirect_uri:
        return Response(
            {"detail": _("code and redirect_uri are required.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    expected_state = request.session.pop("oidc_state", None)
    if not expected_state or state != expected_state:
        return Response(
            {"detail": _("Invalid or missing state parameter.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        claims = exchange_code_for_claims(code, redirect_uri)
    except Exception as exc:
        return Response(
            {"detail": _("OIDC token exchange failed: %(error)s") % {"error": exc}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sub = claims.get("sub", "")
    email = claims.get("email", "")
    provider = claims.get("iss", "oidc")

    try:
        identity = OIDCIdentity.objects.select_related("user").get(
            provider=provider, sub=sub,
        )
        user = identity.user
    except OIDCIdentity.DoesNotExist:
        base_username = email.split("@")[0] if email else f"oidc_{sub[:8]}"
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User.objects.create_user(username=username, email=email)
        OIDCIdentity.objects.create(
            user=user, provider=provider, sub=sub, email=email,
        )

    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def oidc_link_view(request):
    code = request.data.get("code", "")
    redirect_uri = request.data.get("redirect_uri", "")
    state = request.data.get("state", "")

    if not code or not redirect_uri:
        return Response(
            {"detail": _("code and redirect_uri are required.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    expected_state = request.session.pop("oidc_state", None)
    if not expected_state or state != expected_state:
        return Response(
            {"detail": _("Invalid or missing state parameter.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        claims = exchange_code_for_claims(code, redirect_uri)
    except Exception as exc:
        return Response(
            {"detail": _("OIDC token exchange failed: %(error)s") % {"error": exc}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sub = claims.get("sub", "")
    email = claims.get("email", "")
    provider = claims.get("iss", "oidc")

    if OIDCIdentity.objects.filter(provider=provider, sub=sub).exists():
        return Response(
            {"detail": _("This OIDC identity is already linked to an account.")},
            status=status.HTTP_409_CONFLICT,
        )

    OIDCIdentity.objects.create(
        user=request.user, provider=provider, sub=sub, email=email,
    )
    return Response({"detail": _("OIDC identity linked.")}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def oidc_unlink_view(request, identity_id):
    """Unlink an OIDC identity from the current user."""
    deleted, _count = OIDCIdentity.objects.filter(
        id=identity_id, user=request.user,
    ).delete()
    if not deleted:
        return Response(
            {"detail": _("Identity not found.")},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response({"detail": _("OIDC identity unlinked.")})


# ── Project Editor API ────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def project_list_view(request):
    if request.method == "GET":
        projects = Project.objects.filter(owner=request.user)
        return Response(ProjectListSerializer(projects, many=True).data)

    serializer = ProjectCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(owner=request.user)
    project = serializer.instance
    # Seed default folders
    manuscript = Folder.objects.create(project=project, title=_("Manuscript"), icon="📖", order=0)
    ch1 = Folder.objects.create(project=project, parent=manuscript, title="Chapter 1", order=0)
    ProjectFile.objects.create(project=project, folder=ch1, file_type=ProjectFile.FileType.TEXT, title="Scene 1", order=0)
    Folder.objects.create(project=project, title=_("Characters"), icon="👥", order=1)
    Folder.objects.create(project=project, title=_("Locations"), icon="🌎", order=2)
    Folder.objects.create(project=project, title=_("Notes"), icon="📒", order=3)
    # Seed default labels
    Label.objects.bulk_create([
        Label(project=project, name="Idea", colour="#F5A623", order=0),
        Label(project=project, name="Note", colour="#4A90D9", order=1),
        Label(project=project, name="Chapter", colour="#7B68EE", order=2),
        Label(project=project, name="Scene", colour="#50C878", order=3),
        Label(project=project, name="Research", colour="#E74C3C", order=4),
    ])
    Status.objects.bulk_create([
        Status(project=project, name="To Do", colour="#95A5A6", order=0),
        Status(project=project, name="First Draft", colour="#F39C12", order=1),
        Status(project=project, name="Revised Draft", colour="#3498DB", order=2),
        Status(project=project, name="Final Draft", colour="#9B59B6", order=3),
        Status(project=project, name="Done", colour="#2ECC71", order=4),
    ])
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def project_detail_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)

    if request.method == "DELETE":
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    serializer = ProjectUpdateSerializer(project, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(ProjectListSerializer(project).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def project_tree_view(request, project_pk):
    project = get_object_or_404(
        Project.objects.prefetch_related(
            "folders__texts",
            "folders__children__texts",
            "folders__children__children__texts",
            "folders__children__children__children__texts",
            "files",
            "labels",
            "statuses",
        ),
        pk=project_pk,
    )
    # Auto-create trash folder if missing
    if not project.folders.filter(is_trash=True).exists():
        Folder.objects.create(
            project=project,
            is_trash=True,
            title=_("Trash"),
            icon="🗑️",
            parent=None,
            order=9999,
        )
        # Re-fetch to include the new folder in prefetched data
        project = Project.objects.prefetch_related(
            "folders__texts",
            "folders__children__texts",
            "folders__children__children__texts",
            "folders__children__children__children__texts",
            "files",
            "labels",
            "statuses",
        ).get(pk=project_pk)
    return Response(ProjectTreeSerializer(project).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def folder_create_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    serializer = FolderCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    parent = serializer.validated_data.get("parent")
    if parent and parent.project_id != project.pk:
        return Response(
            {"detail": _("Parent folder does not belong to this project.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer.save(project=project)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def folder_detail_view(request, project_pk, folder_pk):
    folder = get_object_or_404(Folder, pk=folder_pk, project_id=project_pk)

    if request.method == "DELETE":
        if folder.is_trash:
            return Response(
                {"detail": _("Cannot delete the trash folder.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        folder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    serializer = FolderUpdateSerializer(folder, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    vd = serializer.validated_data
    if "pov_character" in vd and vd["pov_character"] is not None:
        pov = vd["pov_character"]
        if pov.file_type != "character" or pov.project_id != project_pk:
            return Response(
                {"detail": _("POV must be a character in this project.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
    if "label" in vd and vd["label"] is not None:
        if vd["label"].project_id != project_pk:
            return Response(
                {"detail": _("Label does not belong to this project.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
    if "status" in vd and vd["status"] is not None:
        if vd["status"].project_id != project_pk:
            return Response(
                {"detail": _("Status does not belong to this project.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
    serializer.save()
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def text_create_view(request, project_pk, folder_pk):
    project = get_object_or_404(Project, pk=project_pk)
    folder = get_object_or_404(Folder, pk=folder_pk, project=project)
    serializer = TextCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    file_type = request.data.get("file_type", ProjectFile.FileType.TEXT)
    serializer.save(
        project=project,
        folder=folder,
        file_type=file_type,
    )
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def text_detail_view(request, project_pk, file_pk):
    scene = get_object_or_404(
        ProjectFile,
        pk=file_pk,
        project_id=project_pk,
    )

    if request.method == "DELETE":
        scene.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    serializer = TextUpdateSerializer(scene, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    vd = serializer.validated_data
    if "pov_character" in vd and vd["pov_character"] is not None:
        pov = vd["pov_character"]
        if pov.file_type != "character" or pov.project_id != project_pk:
            return Response(
                {"detail": _("POV must be a character in this project.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
    if "label" in vd and vd["label"] is not None:
        if vd["label"].project_id != project_pk:
            return Response(
                {"detail": _("Label does not belong to this project.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
    if "status" in vd and vd["status"] is not None:
        if vd["status"].project_id != project_pk:
            return Response(
                {"detail": _("Status does not belong to this project.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
    serializer.save()
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def file_detail_view(request, file_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    cache_key = f"draft:{pf.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response({
            "id": pf.pk,
            "title": pf.title,
            "content": cached,
            "source": "cache",
        })
    return Response({
        "id": pf.pk,
        "title": pf.title,
        "content": pf.content,
        "source": "persisted",
    })


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def file_cache_view(request, file_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    cache_key = f"draft:{pf.pk}"

    if request.method == "GET":
        cached = cache.get(cache_key)
        if cached is None:
            return Response(
                {"detail": _("No cached draft.")},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"content": cached})

    if request.method == "PUT":
        content = request.data.get("content", "")
        cache.set(cache_key, content, timeout=86400)
        return Response({"detail": _("Draft cached.")})

    # DELETE
    cache.delete(cache_key)
    return Response({"detail": _("Draft cache cleared.")})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def file_versions_view(request, file_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)

    if request.method == "GET":
        versions = pf.versions.all()
        return Response(FileVersionListSerializer(versions, many=True).data)

    # POST — create a new version
    content = request.data.get("content", "")
    with transaction.atomic():
        version = FileVersion.objects.create(file=pf, content=content)
        pf.content = content
        pf.save()
    cache.delete(f"draft:{pf.pk}")
    return Response(
        FileVersionDetailSerializer(version).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def file_version_detail_view(request, file_pk, version_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    version = get_object_or_404(FileVersion, pk=version_pk, file=pf)
    return Response(FileVersionDetailSerializer(version).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def file_version_revert_view(request, file_pk, version_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    version = get_object_or_404(FileVersion, pk=version_pk, file=pf)
    with transaction.atomic():
        new_version = FileVersion.objects.create(file=pf, content=version.content)
        pf.content = version.content
        pf.save()
    cache.delete(f"draft:{pf.pk}")
    return Response(
        FileVersionDetailSerializer(new_version).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def reorder_view(request, project_pk):
    """
    Bulk reorder folders and texts within a project.

    Expects JSON body:
    {
      "folders": [{"id": 1, "order": 0, "parent": null}, ...],
      "texts": [{"id": 5, "order": 0, "folder": 2}, ...]
    }
    """
    project = get_object_or_404(Project, pk=project_pk)
    folder_updates = request.data.get("folders", [])
    text_updates = request.data.get("texts", [])

    with transaction.atomic():
        for item in folder_updates:
            fid = item.get("id")
            if fid is None:
                continue
            folder = Folder.objects.filter(pk=fid, project=project).first()
            if not folder:
                continue
            update = {}
            if "order" in item:
                update["order"] = item["order"]
            if "parent" in item:
                parent_id = item["parent"]
                if parent_id is None:
                    update["parent"] = None
                else:
                    parent = Folder.objects.filter(pk=parent_id, project=project).first()
                    if parent:
                        update["parent"] = parent
                if "parent" in update:
                    if isinstance(update["parent"], Folder):
                        folder.parent = update.pop("parent")
                    else:
                        folder.parent = None
                        del update["parent"]
            for k, v in update.items():
                setattr(folder, k, v)
            folder.save()

        for item in text_updates:
            tid = item.get("id")
            if tid is None:
                continue
            text = ProjectFile.objects.filter(
                pk=tid, project=project,
            ).first()
            if not text:
                continue
            if "order" in item:
                text.order = item["order"]
            if "folder" in item:
                folder_id = item["folder"]
                if folder_id is not None:
                    folder = Folder.objects.filter(pk=folder_id, project=project).first()
                    if folder:
                        text.folder = folder
            text.save()

    return Response({"detail": _("Reordered.")})


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def empty_trash_view(request, project_pk):
    """Delete all contents of the project's trash folder."""
    project = get_object_or_404(Project, pk=project_pk)
    trash_folder = project.folders.filter(is_trash=True).first()
    if not trash_folder:
        return Response(
            {"detail": _("Trash folder not found.")},
            status=status.HTTP_404_NOT_FOUND,
        )
    Folder.objects.filter(parent=trash_folder).delete()
    ProjectFile.objects.filter(folder=trash_folder).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── Scrivener import ──────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def scrivener_import_view(request):
    """Import a Scrivener .scriv.zip file as a new project."""
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response(
            {"detail": _("No file uploaded.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        project = import_scrivener_zip(uploaded, request.user)
    except ValueError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        ProjectListSerializer(project).data,
        status=status.HTTP_201_CREATED,
    )


# ── yWriter7 import ───────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ywriter_import_view(request):
    """Import a yWriter7 .yw7 file as a new project."""
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response(
            {"detail": _("No file uploaded.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        project = import_ywriter(uploaded, request.user)
    except ValueError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        ProjectListSerializer(project).data,
        status=status.HTTP_201_CREATED,
    )


# ── Export ────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def export_scrivener_view(request, project_pk):
    """Export a project as a Scrivener .scriv.zip file."""
    project = get_object_or_404(Project, pk=project_pk)
    data = export_scrivener(project)
    safe_title = project.title.replace('"', "'")
    response = HttpResponse(data, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{safe_title}.scriv.zip"'
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def export_ywriter_view(request, project_pk):
    """Export a project as a yWriter7 .yw7 file."""
    project = get_object_or_404(Project, pk=project_pk)
    data = export_ywriter(project)
    safe_title = project.title.replace('"', "'")
    response = HttpResponse(data, content_type="application/xml")
    response["Content-Disposition"] = f'attachment; filename="{safe_title}.yw7"'
    return response


# ── Labels ─────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def label_list_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)

    if request.method == "GET":
        labels = Label.objects.filter(project=project).order_by("order")
        return Response(LabelSerializer(labels, many=True).data)

    serializer = LabelSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        serializer.save(project=project)
    except IntegrityError:
        return Response(
            {"detail": _("A label with this name already exists in the project.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def label_detail_view(request, project_pk, label_pk):
    label = get_object_or_404(Label, pk=label_pk, project_id=project_pk)

    if request.method == "DELETE":
        count = (
            Folder.objects.filter(label=label).count()
            + ProjectFile.objects.filter(label=label).count()
        )
        if count > 0 and request.query_params.get("confirm") != "true":
            return Response(
                {
                    "count": count,
                    "detail": _(
                        "This label is assigned to %(count)d items. "
                        "Add ?confirm=true to proceed."
                    ) % {"count": count},
                },
                status=status.HTTP_409_CONFLICT,
            )
        if count > 0:
            Folder.objects.filter(label=label).update(label=None)
            ProjectFile.objects.filter(label=label).update(label=None)
        label.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    serializer = LabelSerializer(label, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    try:
        serializer.save()
    except IntegrityError:
        return Response(
            {"detail": _("A label with this name already exists in the project.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(serializer.data)


# ── Statuses ──────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def status_list_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)

    if request.method == "GET":
        statuses = Status.objects.filter(project=project).order_by("order")
        return Response(StatusSerializer(statuses, many=True).data)

    serializer = StatusSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        serializer.save(project=project)
    except IntegrityError:
        return Response(
            {"detail": _("A status with this name already exists in the project.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def status_detail_view(request, project_pk, status_pk):
    status_obj = get_object_or_404(Status, pk=status_pk, project_id=project_pk)

    if request.method == "DELETE":
        count = (
            Folder.objects.filter(status=status_obj).count()
            + ProjectFile.objects.filter(status=status_obj).count()
        )
        if count > 0 and request.query_params.get("confirm") != "true":
            return Response(
                {
                    "count": count,
                    "detail": _(
                        "This status is assigned to %(count)d items. "
                        "Add ?confirm=true to proceed."
                    ) % {"count": count},
                },
                status=status.HTTP_409_CONFLICT,
            )
        if count > 0:
            Folder.objects.filter(status=status_obj).update(status=None)
            ProjectFile.objects.filter(status=status_obj).update(status=None)
        status_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    serializer = StatusSerializer(status_obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    try:
        serializer.save()
    except IntegrityError:
        return Response(
            {"detail": _("A status with this name already exists in the project.")},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(serializer.data)


# ── Compile Layouts ───────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def compile_layout_list_view(request, project_pk):
    """List or create compile layouts for a project."""
    project = get_object_or_404(Project, pk=project_pk)

    if request.method == "GET":
        layouts = CompileLayout.objects.filter(project=project)
        return Response(CompileLayoutSerializer(layouts, many=True).data)

    serializer = CompileLayoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(project=project)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def compile_layout_detail_view(request, project_pk, layout_pk):
    """Retrieve, update, or delete a compile layout."""
    layout = get_object_or_404(CompileLayout, pk=layout_pk, project_id=project_pk)

    if request.method == "GET":
        return Response(CompileLayoutSerializer(layout).data)

    if request.method == "DELETE":
        layout.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    serializer = CompileLayoutSerializer(layout, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ── Compile ───────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def compile_view(request, project_pk):
    """Compile project content and return the generated file."""
    project = get_object_or_404(Project, pk=project_pk)

    serializer = CompileRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    root_folder_id = data["root_folder_id"]
    format_key = data["format"]
    layout_id = data.get("layout_id")
    front_matter_folder_id = data.get("front_matter_folder_id")
    back_matter_folder_id = data.get("back_matter_folder_id")

    # Validate root folder belongs to project and is not trash
    root_folder = project.folders.filter(pk=root_folder_id).first()
    if root_folder is None:
        return Response(
            {"detail": _("Folder not found.")},
            status=status.HTTP_404_NOT_FOUND,
        )
    if root_folder.is_trash:
        return Response(
            {"detail": _("Cannot compile from trash folder.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Resolve layout settings
    layout_settings = None
    if layout_id:
        layout = project.compile_layouts.filter(pk=layout_id).first()
        if layout is None:
            return Response(
                {"detail": _("Layout not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )
        layout_settings = layout.settings

    # Validate front/back matter folders if provided
    if front_matter_folder_id is not None:
        fm_folder = project.folders.filter(pk=front_matter_folder_id).first()
        if fm_folder is None:
            return Response(
                {"detail": _("Folder not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

    if back_matter_folder_id is not None:
        bm_folder = project.folders.filter(pk=back_matter_folder_id).first()
        if bm_folder is None:
            return Response(
                {"detail": _("Folder not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

    try:
        engine = CompileEngine()
        file_bytes, content_type, filename = engine.compile(
            project=project,
            root_folder_id=root_folder_id,
            format_key=format_key,
            layout_settings=layout_settings,
            front_matter_folder_id=front_matter_folder_id,
            back_matter_folder_id=back_matter_folder_id,
        )
    except ValueError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        return Response(
            {"detail": _("Compile failed: %(error)s") % {"error": str(exc)}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    safe_filename = filename.replace('"', "'")
    response = HttpResponse(file_bytes, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{safe_filename}"'
    return response


# ── Progress Tracking ─────────────────────────────────────────

@api_view(["GET", "PATCH", "POST"])
@permission_classes([IsAuthenticated])
def progress_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk, owner=request.user)

    if request.method == "GET":
        current_wc = compute_project_word_count(project)
        settings = project.settings or {}
        user = request.user

        # Upsert today's manuscript snapshot
        today = datetime.date.today()
        ms_snapshot, created = ManuscriptWordCount.objects.get_or_create(
            project=project, date=today,
            defaults={"word_count": current_wc, "start_word_count": current_wc},
        )
        if not created:
            ms_snapshot.word_count = current_wc
            ms_snapshot.save(update_fields=["word_count", "updated_at"])

        # Upsert today's daily word count for this user
        daily_obj, daily_created = DailyWordCount.objects.get_or_create(
            project=project, date=today, user=user,
            defaults={"word_count": 0},
        )
        # Daily delta = current manuscript wc - start of day manuscript wc
        daily_wc = current_wc - ms_snapshot.start_word_count
        if not daily_created:
            daily_obj.word_count = daily_wc
            daily_obj.save(update_fields=["word_count", "updated_at"])
        else:
            daily_obj.word_count = daily_wc
            daily_obj.save(update_fields=["word_count"])

        # Initialize session start if missing
        if "session_start_word_count" not in settings:
            settings["session_start_word_count"] = current_wc
            settings["session_started_at"] = datetime.datetime.now().isoformat()
            project.settings = settings
            project.save(update_fields=["settings"])

        # Ensure session_start_word_count is an int
        session_start = settings.get("session_start_word_count", current_wc)
        try:
            session_start = int(session_start)
        except (TypeError, ValueError):
            session_start = current_wc
        session_wc = current_wc - session_start

        snapshots = ManuscriptWordCount.objects.filter(project=project).order_by("date")
        daily_counts = DailyWordCount.objects.filter(project=project, user=user).order_by("date")
        sessions = SessionWordCount.objects.filter(project=project, user=user).order_by("-ended_at")[:50]

        return Response({
            "current_word_count": current_wc,
            "manuscript_target": settings.get("manuscript_target"),
            "daily_target": settings.get("daily_target"),
            "session_target": settings.get("session_target"),
            "daily_word_count": daily_wc,
            "session_word_count": session_wc,
            "snapshots": ManuscriptWordCountSerializer(snapshots, many=True).data,
            "daily_counts": DailyWordCountSerializer(daily_counts, many=True).data,
            "sessions": SessionWordCountSerializer(sessions, many=True).data,
        })

    elif request.method == "PATCH":
        settings = project.settings or {}
        errors = {}
        for key in ("manuscript_target", "daily_target", "session_target"):
            if key in request.data:
                val = request.data[key]
                if val is None or val == "":
                    settings.pop(key, None)
                else:
                    try:
                        val = int(val)
                    except (TypeError, ValueError):
                        errors[key] = ["Must be a positive integer."]
                        continue
                    if val <= 0:
                        errors[key] = ["Ensure this value is greater than 0."]
                        continue
                    settings[key] = val
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        project.settings = settings
        project.save(update_fields=["settings"])
        return Response({
            "manuscript_target": settings.get("manuscript_target"),
            "daily_target": settings.get("daily_target"),
            "session_target": settings.get("session_target"),
        })

    else:  # POST
        action = request.data.get("action")
        if action != "reset_session":
            return Response({"detail": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            current_wc = compute_project_word_count(project)
            settings = project.settings or {}
            old_start = settings.get("session_start_word_count", current_wc)
            try:
                old_start = int(old_start)
            except (TypeError, ValueError):
                old_start = current_wc
            session_started = settings.get("session_started_at")
            word_count = current_wc - old_start
            logger.info("reset_session: project=%s current_wc=%s old_start=%s word_count=%s session_started=%r",
                        project_pk, current_wc, old_start, word_count, session_started)
            if word_count != 0:
                started = datetime.datetime.now()
                if session_started:
                    try:
                        parsed = datetime.datetime.fromisoformat(str(session_started))
                        if parsed.tzinfo is not None:
                            parsed = parsed.replace(tzinfo=None)
                        started = parsed
                    except (ValueError, TypeError):
                        logger.warning("reset_session: failed to parse session_started_at=%r, using now()", session_started, exc_info=True)
                logger.info("reset_session: creating SessionWordCount started_at=%s", started)
                SessionWordCount.objects.create(
                    project=project,
                    user=request.user,
                    started_at=started,
                    word_count=word_count,
                )
            settings["session_start_word_count"] = current_wc
            settings["session_started_at"] = datetime.datetime.now().isoformat()
            project.settings = settings
            project.save(update_fields=["settings"])
            return Response({"session_start_word_count": current_wc, "session_word_count": 0})
        except Exception:
            logger.exception("reset_session failed for project %s", project_pk)
            raise


# ── Duplicate & Copy to Project ───────────────────────────────

def _duplicate_folder_recursive(source_folder, target_project, target_parent, order, copy_suffix=""):
    """Recursively duplicate a folder and its contents. Returns the new folder."""
    new_folder = Folder.objects.create(
        project=target_project,
        parent=target_parent,
        title=source_folder.title + copy_suffix,
        description=source_folder.description,
        notes=source_folder.notes,
        tags=source_folder.tags,
        target_word_count=source_folder.target_word_count,
        icon=source_folder.icon,
        order=order,
    )
    # Duplicate child items interleaved by order
    child_folders = list(source_folder.children.order_by("order"))
    child_texts = list(source_folder.texts.order_by("order"))
    combined = [(cf.order, "folder", cf) for cf in child_folders if not cf.is_trash]
    combined += [(ct.order, "text", ct) for ct in child_texts]
    combined.sort(key=lambda x: x[0])
    for i, (_, kind, obj) in enumerate(combined):
        if kind == "folder":
            _duplicate_folder_recursive(obj, target_project, new_folder, i)
        else:
            ProjectFile.objects.create(
                project=target_project,
                folder=new_folder,
                file_type=obj.file_type,
                title=obj.title,
                description=obj.description,
                notes=obj.notes,
                tags=obj.tags,
                target_word_count=obj.target_word_count,
                icon=obj.icon,
                content=obj.content,
                order=i,
            )
    return new_folder


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def duplicate_folder_view(request, project_pk, folder_pk):
    """Duplicate a folder and all its contents right after the original."""
    project = get_object_or_404(Project, pk=project_pk)
    folder = get_object_or_404(Folder, pk=folder_pk, project=project)
    if folder.is_trash:
        return Response({"detail": _("Cannot duplicate the trash folder.")}, status=status.HTTP_400_BAD_REQUEST)
    insert_order = folder.order + 1
    # Shift siblings after the source to make room
    Folder.objects.filter(project=project, parent=folder.parent, order__gte=insert_order).update(
        order=db_models.F("order") + 1
    )
    new_folder = _duplicate_folder_recursive(folder, project, folder.parent, insert_order, copy_suffix=" copy")
    return Response({"id": new_folder.pk, "title": new_folder.title}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def duplicate_text_view(request, project_pk, file_pk):
    """Duplicate a text file right after the original."""
    project = get_object_or_404(Project, pk=project_pk)
    text = get_object_or_404(ProjectFile, pk=file_pk, project=project)
    insert_order = text.order + 1
    # Shift siblings after the source to make room
    ProjectFile.objects.filter(folder=text.folder, order__gte=insert_order).update(
        order=db_models.F("order") + 1
    )
    new_text = ProjectFile.objects.create(
        project=project,
        folder=text.folder,
        file_type=text.file_type,
        title=text.title + " copy",
        description=text.description,
        notes=text.notes,
        tags=text.tags,
        target_word_count=text.target_word_count,
        icon=text.icon,
        content=text.content,
        order=insert_order,
    )
    return Response({"id": new_text.pk, "title": new_text.title}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def copy_to_project_view(request, project_pk):
    """Copy a folder or text to another project."""
    source_project = get_object_or_404(Project, pk=project_pk)
    target_project_id = request.data.get("target_project_id")
    item_type = request.data.get("type")  # "folder" or "text"
    item_id = request.data.get("id")

    if not target_project_id or not item_type or not item_id:
        return Response({"detail": _("target_project_id, type, and id are required.")}, status=status.HTTP_400_BAD_REQUEST)

    target_project = Project.objects.filter(pk=target_project_id, owner=request.user).first()
    if not target_project:
        return Response({"detail": _("Target project not found.")}, status=status.HTTP_404_NOT_FOUND)

    # Find or create the "From <source project>" folder in the target
    import_folder_title = f"From {source_project.title}"
    import_folder = target_project.folders.filter(title=import_folder_title, parent__isnull=True).first()
    if not import_folder:
        next_order = (target_project.folders.filter(parent__isnull=True).aggregate(m=db_models.Max("order"))["m"] or 0) + 1
        import_folder = Folder.objects.create(
            project=target_project, title=import_folder_title, parent=None, order=next_order,
        )

    child_order = (import_folder.children.aggregate(m=db_models.Max("order"))["m"] or -1) + 1
    text_order = (import_folder.texts.aggregate(m=db_models.Max("order"))["m"] or -1) + 1

    if item_type == "folder":
        folder = get_object_or_404(Folder, pk=item_id, project=source_project)
        _duplicate_folder_recursive(folder, target_project, import_folder, child_order)
    elif item_type == "text":
        text = get_object_or_404(ProjectFile, pk=item_id, project=source_project)
        ProjectFile.objects.create(
            project=target_project, folder=import_folder, file_type=text.file_type,
            title=text.title, description=text.description, notes=text.notes,
            tags=text.tags, target_word_count=text.target_word_count, icon=text.icon,
            content=text.content, order=text_order,
        )
    else:
        return Response({"detail": _("type must be 'folder' or 'text'.")}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"detail": _("Copied.")}, status=status.HTTP_201_CREATED)

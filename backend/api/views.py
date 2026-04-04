import secrets

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .exporters import export_scrivener, export_ywriter
from .models import FileVersion, Folder, OIDCIdentity, Project, ProjectFile
from .oidc import exchange_code_for_claims, get_authorization_url
from .permissions import IsProjectOwner
from .scrivener import import_scrivener_zip
from .ywriter import import_ywriter
from .serializers import (
    FileVersionDetailSerializer,
    FileVersionListSerializer,
    FolderCreateSerializer,
    FolderUpdateSerializer,
    ProjectCreateSerializer,
    ProjectListSerializer,
    ProjectTreeSerializer,
    ProjectUpdateSerializer,
    RegisterSerializer,
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

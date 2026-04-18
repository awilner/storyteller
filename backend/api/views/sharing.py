import logging
import os

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..broadcast import broadcast_project_event
from ..models import (
    Folder,
    ObjectPermissionOverride,
    Project,
    ProjectFile,
    ProjectShare,
)
from ..serializers import (
    ObjectPermissionOverrideSerializer,
    ProjectShareSerializer,
    UserSearchSerializer,
)

logger = logging.getLogger(__name__)


# ── WebSocket broadcast helpers ───────────────────────────────

def _broadcast_permission_changed(project_pk, user_id, new_role, username=None, **extra):
    """Send a permission_changed event to the project's channel group."""
    broadcast_project_event(
        project_pk, "permission_changed",
        user_id=user_id, new_role=new_role,
        **({"username": username} if username else {}),
        **extra,
    )


def _broadcast_access_revoked(project_pk, user_id):
    """Send a user_access_revoked event to the project's channel group.

    This uses a dedicated Channels message type because the consumer
    needs to close the affected user's connection — behaviour that the
    generic project_event handler does not perform.
    """
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"project_{project_pk}",
            {
                "type": "user_access_revoked",
                "user_id": user_id,
            },
        )
    except Exception:
        logger.warning("Failed to broadcast user_access_revoked for project %s", project_pk, exc_info=True)


# ── Helpers ───────────────────────────────────────────────────

def _get_project(project_pk):
    """Resolve a project by PK or 404."""
    return get_object_or_404(Project, pk=project_pk)


def _require_owner(project, user):
    """Return a 403 Response if *user* is not the project owner, else None."""
    if project.owner_id != user.id:
        return Response(
            {"detail": "Only the project owner can manage collaborators."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _has_project_access(project, user):
    """Return True if *user* owns the project or has a share."""
    if project.owner_id == user.id:
        return True
    return ProjectShare.objects.filter(project=project, user=user).exists()


# Permission hierarchy: higher index = higher privilege
_PERMISSION_RANK = {
    "none": 0,
    "read-only": 1,
    "co-author": 2,
    "owner": 3,
}


def _is_downgrade(base_role, override_permission):
    """Return True when *override_permission* is strictly lower than *base_role*."""
    return _PERMISSION_RANK.get(override_permission, 0) < _PERMISSION_RANK.get(base_role, 0)


def _is_upgrade(base_role, override_permission):
    """Return True when *override_permission* is higher than *base_role*."""
    return _PERMISSION_RANK.get(override_permission, 0) >= _PERMISSION_RANK.get(base_role, 0)


# ── Share list / create ───────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def share_list_view(request, project_pk):
    """
    GET  — list collaborators (any authenticated user with project access).
    POST — add a collaborator (owner only).
    """
    project = _get_project(project_pk)

    if request.method == "GET":
        if not _has_project_access(project, request.user):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )
        shares = ProjectShare.objects.filter(project=project).select_related("user")
        return Response(ProjectShareSerializer(shares, many=True).data)

    # POST — owner only
    forbidden = _require_owner(project, request.user)
    if forbidden:
        return forbidden

    username = request.data.get("username")
    role = request.data.get("role")

    if not username:
        return Response(
            {"detail": "username is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Look up target user
    try:
        target_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response(
            {"detail": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Cannot share with self
    if target_user.id == project.owner_id:
        return Response(
            {"detail": "Cannot share a project with its owner."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        try:
            share = ProjectShare.objects.create(
                project=project,
                user=target_user,
                role=role,
            )
        except IntegrityError:
            return Response(
                {"detail": "This user already has access to this project."},
                status=status.HTTP_409_CONFLICT,
            )

    _broadcast_permission_changed(project.pk, target_user.id, role, username=target_user.username)

    return Response(
        ProjectShareSerializer(share).data,
        status=status.HTTP_201_CREATED,
    )


# ── Share detail (change role / revoke) ───────────────────────

@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def share_detail_view(request, project_pk, share_pk):
    """
    PATCH  — change a collaborator's role (owner only).
    DELETE — revoke a collaborator's access (owner only).
    """
    project = _get_project(project_pk)
    forbidden = _require_owner(project, request.user)
    if forbidden:
        return forbidden

    share = get_object_or_404(ProjectShare.objects.select_related("user"), pk=share_pk, project=project)

    if request.method == "DELETE":
        revoked_user_id = share.user_id
        with transaction.atomic():
            # Cascade: remove all overrides for this user on this project
            ObjectPermissionOverride.objects.filter(
                project=project, user=share.user,
            ).delete()
            share.delete()
        _broadcast_access_revoked(project.pk, revoked_user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH — change role
    new_role = request.data.get("role")
    if new_role not in dict(ProjectShare.Role.choices):
        return Response(
            {"detail": "Invalid role."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    old_role = share.role

    with transaction.atomic():
        share.role = new_role
        share.save()

        # Downgrade co-author → read-only: clean up overrides that are no
        # longer valid.  A "read-only" override on a now-read-only user is
        # redundant (same level), so we keep only "none" overrides.
        if old_role == "co-author" and new_role == "read-only":
            ObjectPermissionOverride.objects.filter(
                project=project,
                user=share.user,
                permission="read-only",
            ).delete()

    _broadcast_permission_changed(project.pk, share.user_id, new_role, username=share.user.username)

    return Response(ProjectShareSerializer(share).data)


# ── Search users ──────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_users_view(request, project_pk):
    """Search users by username, excluding the owner and existing collaborators."""
    project = _get_project(project_pk)
    forbidden = _require_owner(project, request.user)
    if forbidden:
        return forbidden

    query = request.query_params.get("q", "").strip()
    if not query:
        return Response([])

    existing_user_ids = set(
        ProjectShare.objects.filter(project=project).values_list("user_id", flat=True)
    )
    existing_user_ids.add(project.owner_id)

    users = (
        User.objects.filter(username__icontains=query)
        .exclude(id__in=existing_user_ids)[:10]
    )
    return Response(UserSearchSerializer(users, many=True).data)


# ── Override list / create ────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def override_list_view(request, project_pk):
    """
    GET  — list overrides. Owners see all overrides; collaborators see
           only their own overrides.
    POST — create an override (owner only).
    """
    project = _get_project(project_pk)

    if request.method == "GET":
        if project.owner_id == request.user.id:
            # Owner sees all overrides
            overrides = ObjectPermissionOverride.objects.filter(project=project)
        elif _has_project_access(project, request.user):
            # Collaborator sees only their own overrides
            overrides = ObjectPermissionOverride.objects.filter(
                project=project, user=request.user,
            )
        else:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            ObjectPermissionOverrideSerializer(overrides, many=True).data,
        )

    # POST — owner only
    forbidden = _require_owner(project, request.user)
    if forbidden:
        return forbidden

    # POST — create override
    serializer = ObjectPermissionOverrideSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    target_user = serializer.validated_data["user"]
    permission = serializer.validated_data["permission"]

    # The user must be a collaborator on this project
    share = ProjectShare.objects.filter(project=project, user=target_user).first()
    if share is None:
        return Response(
            {"detail": "User is not a collaborator on this project."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Overrides can only downgrade — reject if permission is not strictly lower
    if not _is_downgrade(share.role, permission):
        return Response(
            {"detail": "Object permission cannot exceed the collaborator's project-level role."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        override = serializer.save(project=project)

    _broadcast_permission_changed(
        project.pk,
        target_user.id,
        permission,
        override_id=override.id,
        target_folder=override.target_folder_id,
        target_file=override.target_file_id,
    )

    return Response(
        ObjectPermissionOverrideSerializer(override).data,
        status=status.HTTP_201_CREATED,
    )


# ── Override detail (update / delete) ─────────────────────────

@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def override_detail_view(request, project_pk, override_pk):
    """
    PATCH  — update an override (owner only).
    DELETE — remove an override (owner only).
    """
    project = _get_project(project_pk)
    forbidden = _require_owner(project, request.user)
    if forbidden:
        return forbidden

    override = get_object_or_404(
        ObjectPermissionOverride, pk=override_pk, project=project,
    )

    if request.method == "DELETE":
        affected_user_id = override.user_id
        target_folder = override.target_folder_id
        target_file = override.target_file_id
        override.delete()
        # Broadcast that the override was removed — the user's effective
        # permission reverts to their project-level role.
        share = ProjectShare.objects.filter(
            project=project, user_id=affected_user_id,
        ).first()
        reverted_role = share.role if share else None
        _broadcast_permission_changed(
            project.pk,
            affected_user_id,
            reverted_role,
            target_folder=target_folder,
            target_file=target_file,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH — update
    new_permission = request.data.get("permission")
    if new_permission not in dict(ObjectPermissionOverride.Permission.choices):
        return Response(
            {"detail": "Invalid permission."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate downgrade-only
    share = ProjectShare.objects.filter(
        project=project, user=override.user,
    ).first()
    if share is None:
        return Response(
            {"detail": "User is not a collaborator on this project."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _is_downgrade(share.role, new_permission):
        return Response(
            {"detail": "Object permission cannot exceed the collaborator's project-level role."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    override.permission = new_permission
    override.save()

    _broadcast_permission_changed(
        project.pk,
        override.user_id,
        new_permission,
        override_id=override.id,
        target_folder=override.target_folder_id,
        target_file=override.target_file_id,
    )

    return Response(ObjectPermissionOverrideSerializer(override).data)


# ── Internal Yjs auth endpoint ────────────────────────────────

def _get_ancestor_chain_for_file(project_file):
    """
    Build the ancestor chain from a ProjectFile up to the project root.

    Returns a list starting with the file itself, then its parent folder,
    grandparent folder, etc.
    """
    ancestors = [project_file]
    current_folder = project_file.folder
    while current_folder is not None:
        ancestors.append(current_folder)
        if current_folder.parent_id:
            try:
                current_folder = Folder.objects.get(pk=current_folder.parent_id)
            except Folder.DoesNotExist:
                break
        else:
            current_folder = None
    return ancestors


def _compute_effective_for_file(share, project_file):
    """
    Compute the effective permission for a collaborator on a specific file.

    Walks the ancestor chain from root toward the file; the nearest
    ancestor override wins. If no override exists, the project-level
    role applies.
    """
    from django.db.models import Q

    ancestors = _get_ancestor_chain_for_file(project_file)
    if not ancestors:
        return share.role

    folder_ids = [a.id for a in ancestors if isinstance(a, Folder)]
    file_ids = [a.id for a in ancestors if isinstance(a, ProjectFile)]

    q = Q()
    if folder_ids:
        q |= Q(target_folder_id__in=folder_ids)
    if file_ids:
        q |= Q(target_file_id__in=file_ids)

    overrides = ObjectPermissionOverride.objects.filter(
        q,
        user=share.user,
        project=share.project,
    )

    override_map = {}
    for o in overrides:
        if o.target_folder_id:
            key = ("folder", o.target_folder_id)
        else:
            key = ("file", o.target_file_id)
        override_map[key] = o.permission

    # Walk from root toward target; nearest ancestor override wins
    for ancestor in reversed(ancestors):
        if isinstance(ancestor, Folder):
            key = ("folder", ancestor.id)
        else:
            key = ("file", ancestor.id)
        if key in override_map:
            perm = override_map[key]
            return None if perm == "none" else perm

    return share.role


@csrf_exempt
@require_POST
def yjs_auth_view(request):
    """
    Internal endpoint called by HocusPocus to authenticate a Yjs
    WebSocket connection.

    POST /api/internal/yjs-auth/
    Body: { "file_id": <int>, "cookie": "<session cookie string>" }

    Validates the session, resolves the user, computes the effective
    permission on the file, and returns user info.

    Access is restricted to internal requests via a shared secret
    (HOCUSPOCUS_SECRET environment variable).
    """
    import json

    # Verify shared secret.
    # When HOCUSPOCUS_SECRET is not set (empty), skip the check to allow
    # local development without extra configuration. In production, always
    # set HOCUSPOCUS_SECRET on both the backend and HocusPocus.
    expected_secret = os.environ.get("HOCUSPOCUS_SECRET", "")
    provided_secret = request.headers.get("X-Hocuspocus-Secret", "")
    if expected_secret and provided_secret != expected_secret:
        return JsonResponse(
            {"detail": "Unauthorized: invalid or missing secret."},
            status=403,
        )

    # Parse request body
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"detail": "Invalid JSON body."},
            status=400,
        )

    file_id = body.get("file_id")
    cookie_str = body.get("cookie", "")

    if not file_id:
        return JsonResponse(
            {"detail": "file_id is required."},
            status=400,
        )

    # Extract session ID from cookie string
    session_id = None
    if cookie_str:
        # Parse "sessionid=abc123; other=..." format
        for part in cookie_str.split(";"):
            part = part.strip()
            if part.startswith("sessionid="):
                session_id = part.split("=", 1)[1]
                break

    if not session_id:
        return JsonResponse(
            {"detail": "No valid session found."},
            status=401,
        )

    # Validate session
    session = SessionStore(session_key=session_id)
    user_id = session.get("_auth_user_id")
    if not user_id:
        return JsonResponse(
            {"detail": "Invalid or expired session."},
            status=401,
        )

    # Resolve user
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse(
            {"detail": "User not found."},
            status=401,
        )

    # Resolve file
    try:
        project_file = ProjectFile.objects.select_related(
            "project", "folder"
        ).get(pk=file_id)
    except ProjectFile.DoesNotExist:
        return JsonResponse(
            {"detail": "File not found."},
            status=404,
        )

    project = project_file.project

    # Compute permission
    if project.owner_id == user.id:
        permission = "owner"
    else:
        share = ProjectShare.objects.filter(
            project=project, user=user
        ).first()
        if share is None:
            return JsonResponse(
                {"detail": "No access to this file."},
                status=403,
            )
        permission = _compute_effective_for_file(share, project_file)
        if permission is None:
            return JsonResponse(
                {"detail": "No access to this file."},
                status=403,
            )

    return JsonResponse({
        "user_id": user.id,
        "username": user.username,
        "permission": permission,
    })

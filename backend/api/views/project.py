import logging

from django.core.cache import cache
from django.db import models as db_models, transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..broadcast import broadcast_project_event
from ..models import FileVersion, Folder, Label, ObjectPermissionOverride, Project, ProjectFile, ProjectShare, Status
from ..permissions import ProjectPermission
from ..serializers import (
    FileVersionDetailSerializer,
    FileVersionListSerializer,
    FolderCreateSerializer,
    FolderUpdateSerializer,
    ProjectCreateSerializer,
    ProjectListSerializer,
    ProjectTreeSerializer,
    ProjectUpdateSerializer,
    TextCreateSerializer,
    TextUpdateSerializer,
)

logger = logging.getLogger(__name__)


def _effective_perm_for_folder(project, user, folder):
    """Compute the effective permission for a co-author on a specific folder.

    Walks up the folder tree looking for the nearest ObjectPermissionOverride.
    Returns the project-level role if no override is found.
    Owners always get "owner".
    """
    if project.owner_id == user.id:
        return "owner"
    share = ProjectShare.objects.filter(project=project, user=user).first()
    if not share:
        return None

    # Build ancestor chain (folder → parent → grandparent → ...)
    ancestors = []
    current = folder
    while current is not None:
        ancestors.append(current)
        current = Folder.objects.filter(pk=current.parent_id).first() if current.parent_id else None

    folder_ids = [a.id for a in ancestors]
    overrides = ObjectPermissionOverride.objects.filter(
        project=project, user=user, target_folder_id__in=folder_ids,
    )
    override_map = {o.target_folder_id: o.permission for o in overrides}

    # Walk from root toward target; nearest ancestor override wins
    for ancestor in reversed(ancestors):
        if ancestor.id in override_map:
            perm = override_map[ancestor.id]
            return None if perm == "none" else perm

    return share.role


def _check_write_perm(request):
    """Return a 403 Response if the user's effective permission is read-only, else None."""
    eff = getattr(request, "effective_permission", None)
    if eff == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def project_list_view(request):
    if request.method == "GET":
        owned = Project.objects.filter(owner=request.user)
        shared_ids = ProjectShare.objects.filter(
            user=request.user
        ).values_list('project_id', flat=True)
        shared = Project.objects.filter(id__in=shared_ids)

        owned_data = ProjectListSerializer(owned, many=True).data
        for p in owned_data:
            p['role'] = 'owner'

        shared_data = ProjectListSerializer(shared, many=True).data
        shares = ProjectShare.objects.filter(user=request.user).select_related('project__owner')
        share_map = {s.project_id: s for s in shares}
        for p in shared_data:
            share = share_map.get(p['id'])
            if share:
                p['role'] = share.role
                p['owner_name'] = share.project.owner.username

        return Response(owned_data + shared_data)

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
@permission_classes([IsAuthenticated, ProjectPermission])
def project_detail_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == "DELETE":
        if request.project_role != "owner":
            return Response(
                {"detail": "Only the project owner can delete this project."},
                status=status.HTTP_403_FORBIDDEN,
            )
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    # PATCH — owner and co-author can update settings
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = ProjectUpdateSerializer(project, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    broadcast_project_event(project_pk, "settings_changed", user_id=request.user.id)
    return Response(ProjectListSerializer(project).data)


# ── Tree filtering helpers for per-object "none" overrides ────


def _get_blocked_object_ids(project, user):
    """
    Return (blocked_folder_ids, blocked_file_ids) — sets of IDs where
    the user has a 'none' override on this project.
    """
    overrides = ObjectPermissionOverride.objects.filter(
        project=project, user=user, permission="none",
    )
    blocked_folders = set()
    blocked_files = set()
    for o in overrides:
        if o.target_folder_id:
            blocked_folders.add(o.target_folder_id)
        if o.target_file_id:
            blocked_files.add(o.target_file_id)
    return blocked_folders, blocked_files


def _filter_tree(folders, blocked_folders, blocked_files):
    """
    Recursively remove blocked folders and files from the serialized tree.
    If a folder is blocked, it and all its descendants are removed.
    """
    result = []
    for folder in folders:
        if folder["id"] in blocked_folders:
            continue
        # Filter files in this folder
        folder["items"] = [
            item for item in folder.get("items", [])
            if item["id"] not in blocked_files
        ]
        # Recurse into children
        folder["children"] = _filter_tree(
            folder.get("children", []), blocked_folders, blocked_files,
        )
        result.append(folder)
    return result


@api_view(["GET"])
@permission_classes([IsAuthenticated, ProjectPermission])
def project_tree_view(request, project_pk):
    project = get_object_or_404(
        Project.objects.prefetch_related(
            "folders__texts", "folders__children__texts",
            "folders__children__children__texts",
            "folders__children__children__children__texts",
            "files", "labels", "statuses",
        ),
        pk=project_pk,
    )
    if not project.folders.filter(is_trash=True).exists():
        Folder.objects.create(project=project, is_trash=True, title=_("Trash"), icon="🗑️", parent=None, order=9999)
        project = Project.objects.prefetch_related(
            "folders__texts", "folders__children__texts",
            "folders__children__children__texts",
            "folders__children__children__children__texts",
            "files", "labels", "statuses",
        ).get(pk=project_pk)
    data = ProjectTreeSerializer(project).data
    data["role"] = getattr(request, "project_role", "owner")

    # For non-owners, filter out objects where the user has no access.
    if data["role"] != "owner":
        blocked_folders, blocked_files = _get_blocked_object_ids(
            project, request.user,
        )
        if blocked_folders or blocked_files:
            data["folders"] = _filter_tree(
                data["folders"], blocked_folders, blocked_files,
            )

    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def folder_create_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = FolderCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    parent = serializer.validated_data.get("parent")
    if parent and parent.project_id != project.pk:
        return Response({"detail": _("Parent folder does not belong to this project.")}, status=status.HTTP_400_BAD_REQUEST)
    # Check effective permission on the parent folder
    if parent and request.project_role == "co-author":
        eff = _effective_perm_for_folder(project, request.user, parent)
        if eff in ("read-only", None):
            return Response(
                {"detail": "Read-only access does not allow this action."},
                status=status.HTTP_403_FORBIDDEN,
            )
    serializer.save(project=project)
    broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated, ProjectPermission])
def folder_detail_view(request, project_pk, folder_pk):
    folder = get_object_or_404(Folder, pk=folder_pk, project_id=project_pk)
    denied = _check_write_perm(request)
    if denied:
        return denied
    if request.method == "DELETE":
        if folder.is_trash:
            return Response({"detail": _("Cannot delete the trash folder.")}, status=status.HTTP_400_BAD_REQUEST)
        folder.delete()
        broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = FolderUpdateSerializer(folder, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    vd = serializer.validated_data
    if "pov_character" in vd and vd["pov_character"] is not None:
        pov = vd["pov_character"]
        if pov.file_type != "character" or pov.project_id != project_pk:
            return Response({"detail": _("POV must be a character in this project.")}, status=status.HTTP_400_BAD_REQUEST)
    if "label" in vd and vd["label"] is not None:
        if vd["label"].project_id != project_pk:
            return Response({"detail": _("Label does not belong to this project.")}, status=status.HTTP_400_BAD_REQUEST)
    if "status" in vd and vd["status"] is not None:
        if vd["status"].project_id != project_pk:
            return Response({"detail": _("Status does not belong to this project.")}, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def text_create_view(request, project_pk, folder_pk):
    project = get_object_or_404(Project, pk=project_pk)
    folder = get_object_or_404(Folder, pk=folder_pk, project=project)
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    # Check effective permission on the target folder
    if request.project_role == "co-author":
        eff = _effective_perm_for_folder(project, request.user, folder)
        if eff in ("read-only", None):
            return Response(
                {"detail": "Read-only access does not allow this action."},
                status=status.HTTP_403_FORBIDDEN,
            )
    serializer = TextCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    file_type = request.data.get("file_type", ProjectFile.FileType.TEXT)
    serializer.save(project=project, folder=folder, file_type=file_type)
    broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated, ProjectPermission])
def text_detail_view(request, project_pk, file_pk):
    scene = get_object_or_404(ProjectFile, pk=file_pk, project_id=project_pk)
    denied = _check_write_perm(request)
    if denied:
        return denied
    if request.method == "DELETE":
        scene.delete()
        broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = TextUpdateSerializer(scene, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    vd = serializer.validated_data
    if "pov_character" in vd and vd["pov_character"] is not None:
        pov = vd["pov_character"]
        if pov.file_type != "character" or pov.project_id != project_pk:
            return Response({"detail": _("POV must be a character in this project.")}, status=status.HTTP_400_BAD_REQUEST)
    if "label" in vd and vd["label"] is not None:
        if vd["label"].project_id != project_pk:
            return Response({"detail": _("Label does not belong to this project.")}, status=status.HTTP_400_BAD_REQUEST)
    if "status" in vd and vd["status"] is not None:
        if vd["status"].project_id != project_pk:
            return Response({"detail": _("Status does not belong to this project.")}, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, ProjectPermission])
def file_detail_view(request, file_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    cache_key = f"draft:{pf.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response({"id": pf.pk, "title": pf.title, "content": cached, "source": "cache"})
    return Response({"id": pf.pk, "title": pf.title, "content": pf.content, "source": "persisted"})


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated, ProjectPermission])
def file_cache_view(request, file_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    cache_key = f"draft:{pf.pk}"
    if request.method == "GET":
        cached = cache.get(cache_key)
        if cached is None:
            return Response({"detail": _("No cached draft.")}, status=status.HTTP_404_NOT_FOUND)
        return Response({"content": cached})
    denied = _check_write_perm(request)
    if denied:
        return denied
    if request.method == "PUT":
        content = request.data.get("content", "")
        cache.set(cache_key, content, timeout=86400)
        return Response({"detail": _("Draft cached.")})
    cache.delete(cache_key)
    return Response({"detail": _("Draft cache cleared.")})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def file_versions_view(request, file_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    if request.method == "GET":
        return Response(FileVersionListSerializer(pf.versions.all(), many=True).data)
    denied = _check_write_perm(request)
    if denied:
        return denied
    content = request.data.get("content", "")
    with transaction.atomic():
        version = FileVersion.objects.create(file=pf, content=content)
        pf.content = content
        pf.save()
    cache.delete(f"draft:{pf.pk}")
    return Response(FileVersionDetailSerializer(version).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated, ProjectPermission])
def file_version_detail_view(request, file_pk, version_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    version = get_object_or_404(FileVersion, pk=version_pk, file=pf)
    return Response(FileVersionDetailSerializer(version).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def file_version_revert_view(request, file_pk, version_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    version = get_object_or_404(FileVersion, pk=version_pk, file=pf)
    denied = _check_write_perm(request)
    if denied:
        return denied
    with transaction.atomic():
        new_version = FileVersion.objects.create(file=pf, content=version.content)
        pf.content = version.content
        pf.save()
    cache.delete(f"draft:{pf.pk}")
    return Response(FileVersionDetailSerializer(new_version).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def reorder_view(request, project_pk):
    """Bulk reorder folders and texts within a project."""
    project = get_object_or_404(Project, pk=project_pk)
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )

    folder_updates = request.data.get("folders", [])
    text_updates = request.data.get("texts", [])

    # For co-authors, check effective permission on each affected folder.
    # Moving a folder the user can write is allowed (even if it contains
    # read-only children). But reordering within or moving into a
    # read-only folder is blocked.
    if request.project_role == "co-author":
        for item in folder_updates:
            fid = item.get("id")
            if fid is None:
                continue
            folder = Folder.objects.filter(pk=fid, project=project).first()
            if not folder:
                continue
            # Check the folder itself — can the user modify it?
            eff = _effective_perm_for_folder(project, request.user, folder)
            if eff in ("read-only", None):
                return Response(
                    {"detail": "Read-only access does not allow this action."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # If moving to a new parent, check the destination
            if "parent" in item and item["parent"] is not None:
                dest = Folder.objects.filter(pk=item["parent"], project=project).first()
                if dest:
                    dest_eff = _effective_perm_for_folder(project, request.user, dest)
                    if dest_eff in ("read-only", None):
                        return Response(
                            {"detail": "Read-only access does not allow this action."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
        for item in text_updates:
            tid = item.get("id")
            if tid is None:
                continue
            text = ProjectFile.objects.filter(pk=tid, project=project).select_related("folder").first()
            if not text or not text.folder:
                continue
            # Check the text's current folder
            eff = _effective_perm_for_folder(project, request.user, text.folder)
            if eff in ("read-only", None):
                return Response(
                    {"detail": "Read-only access does not allow this action."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # If moving to a new folder, check the destination
            if "folder" in item and item["folder"] is not None and item["folder"] != text.folder_id:
                dest = Folder.objects.filter(pk=item["folder"], project=project).first()
                if dest:
                    dest_eff = _effective_perm_for_folder(project, request.user, dest)
                    if dest_eff in ("read-only", None):
                        return Response(
                            {"detail": "Read-only access does not allow this action."},
                            status=status.HTTP_403_FORBIDDEN,
                        )

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
            text = ProjectFile.objects.filter(pk=tid, project=project).first()
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
    broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
    return Response({"detail": _("Reordered.")})


@api_view(["POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def empty_trash_view(request, project_pk):
    """Delete all contents of the project's trash folder."""
    project = get_object_or_404(Project, pk=project_pk)
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    trash_folder = project.folders.filter(is_trash=True).first()
    if not trash_folder:
        return Response({"detail": _("Trash folder not found.")}, status=status.HTTP_404_NOT_FOUND)
    Folder.objects.filter(parent=trash_folder).delete()
    ProjectFile.objects.filter(folder=trash_folder).delete()
    broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── Duplicate & Copy to Project ───────────────────────────────

def _duplicate_folder_recursive(source_folder, target_project, target_parent, order, copy_suffix=""):
    """Recursively duplicate a folder and its contents."""
    new_folder = Folder.objects.create(
        project=target_project, parent=target_parent,
        title=source_folder.title + copy_suffix,
        description=source_folder.description, notes=source_folder.notes,
        tags=source_folder.tags, target_word_count=source_folder.target_word_count,
        icon=source_folder.icon, order=order,
    )
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
                project=target_project, folder=new_folder, file_type=obj.file_type,
                title=obj.title, description=obj.description, notes=obj.notes,
                tags=obj.tags, target_word_count=obj.target_word_count,
                icon=obj.icon, content=obj.content, order=i,
            )
    return new_folder


@api_view(["POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def duplicate_folder_view(request, project_pk, folder_pk):
    """Duplicate a folder and all its contents right after the original."""
    project = get_object_or_404(Project, pk=project_pk)
    folder = get_object_or_404(Folder, pk=folder_pk, project=project)
    denied = _check_write_perm(request)
    if denied:
        return denied
    if folder.is_trash:
        return Response({"detail": _("Cannot duplicate the trash folder.")}, status=status.HTTP_400_BAD_REQUEST)
    insert_order = folder.order + 1
    Folder.objects.filter(project=project, parent=folder.parent, order__gte=insert_order).update(order=db_models.F("order") + 1)
    new_folder = _duplicate_folder_recursive(folder, project, folder.parent, insert_order, copy_suffix=" copy")
    broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
    return Response({"id": new_folder.pk, "title": new_folder.title}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def duplicate_text_view(request, project_pk, file_pk):
    """Duplicate a text file right after the original."""
    project = get_object_or_404(Project, pk=project_pk)
    text = get_object_or_404(ProjectFile, pk=file_pk, project=project)
    denied = _check_write_perm(request)
    if denied:
        return denied
    insert_order = text.order + 1
    ProjectFile.objects.filter(folder=text.folder, order__gte=insert_order).update(order=db_models.F("order") + 1)
    new_text = ProjectFile.objects.create(
        project=project, folder=text.folder, file_type=text.file_type,
        title=text.title + " copy", description=text.description, notes=text.notes,
        tags=text.tags, target_word_count=text.target_word_count,
        icon=text.icon, content=text.content, order=insert_order,
    )
    broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)
    return Response({"id": new_text.pk, "title": new_text.title}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def copy_to_project_view(request, project_pk):
    """Copy a folder or text to another project."""
    source_project = get_object_or_404(Project, pk=project_pk)
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    target_project_id = request.data.get("target_project_id")
    item_type = request.data.get("type")
    item_id = request.data.get("id")
    if not target_project_id or not item_type or not item_id:
        return Response({"detail": _("target_project_id, type, and id are required.")}, status=status.HTTP_400_BAD_REQUEST)
    target_project = Project.objects.filter(pk=target_project_id, owner=request.user).first()
    if not target_project:
        return Response({"detail": _("Target project not found.")}, status=status.HTTP_404_NOT_FOUND)
    import_folder_title = f"From {source_project.title}"
    import_folder = target_project.folders.filter(title=import_folder_title, parent__isnull=True).first()
    if not import_folder:
        next_order = (target_project.folders.filter(parent__isnull=True).aggregate(m=db_models.Max("order"))["m"] or 0) + 1
        import_folder = Folder.objects.create(project=target_project, title=import_folder_title, parent=None, order=next_order)
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
    broadcast_project_event(target_project_id, "tree_changed", user_id=request.user.id)
    return Response({"detail": _("Copied.")}, status=status.HTTP_201_CREATED)

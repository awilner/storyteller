from django.core.cache import cache
from django.db import models as db_models, transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import FileVersion, Folder, Label, Project, ProjectFile, Status
from ..permissions import IsProjectOwner
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
    serializer = ProjectUpdateSerializer(project, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(ProjectListSerializer(project).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsProjectOwner])
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
    return Response(ProjectTreeSerializer(project).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def folder_create_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    serializer = FolderCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    parent = serializer.validated_data.get("parent")
    if parent and parent.project_id != project.pk:
        return Response({"detail": _("Parent folder does not belong to this project.")}, status=status.HTTP_400_BAD_REQUEST)
    serializer.save(project=project)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def folder_detail_view(request, project_pk, folder_pk):
    folder = get_object_or_404(Folder, pk=folder_pk, project_id=project_pk)
    if request.method == "DELETE":
        if folder.is_trash:
            return Response({"detail": _("Cannot delete the trash folder.")}, status=status.HTTP_400_BAD_REQUEST)
        folder.delete()
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
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def text_create_view(request, project_pk, folder_pk):
    project = get_object_or_404(Project, pk=project_pk)
    folder = get_object_or_404(Folder, pk=folder_pk, project=project)
    serializer = TextCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    file_type = request.data.get("file_type", ProjectFile.FileType.TEXT)
    serializer.save(project=project, folder=folder, file_type=file_type)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def text_detail_view(request, project_pk, file_pk):
    scene = get_object_or_404(ProjectFile, pk=file_pk, project_id=project_pk)
    if request.method == "DELETE":
        scene.delete()
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
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def file_detail_view(request, file_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    cache_key = f"draft:{pf.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response({"id": pf.pk, "title": pf.title, "content": cached, "source": "cache"})
    return Response({"id": pf.pk, "title": pf.title, "content": pf.content, "source": "persisted"})


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def file_cache_view(request, file_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    cache_key = f"draft:{pf.pk}"
    if request.method == "GET":
        cached = cache.get(cache_key)
        if cached is None:
            return Response({"detail": _("No cached draft.")}, status=status.HTTP_404_NOT_FOUND)
        return Response({"content": cached})
    if request.method == "PUT":
        content = request.data.get("content", "")
        cache.set(cache_key, content, timeout=86400)
        return Response({"detail": _("Draft cached.")})
    cache.delete(cache_key)
    return Response({"detail": _("Draft cache cleared.")})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def file_versions_view(request, file_pk):
    pf = get_object_or_404(ProjectFile, pk=file_pk)
    if request.method == "GET":
        return Response(FileVersionListSerializer(pf.versions.all(), many=True).data)
    content = request.data.get("content", "")
    with transaction.atomic():
        version = FileVersion.objects.create(file=pf, content=content)
        pf.content = content
        pf.save()
    cache.delete(f"draft:{pf.pk}")
    return Response(FileVersionDetailSerializer(version).data, status=status.HTTP_201_CREATED)


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
    return Response(FileVersionDetailSerializer(new_version).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def reorder_view(request, project_pk):
    """Bulk reorder folders and texts within a project."""
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
    return Response({"detail": _("Reordered.")})


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def empty_trash_view(request, project_pk):
    """Delete all contents of the project's trash folder."""
    project = get_object_or_404(Project, pk=project_pk)
    trash_folder = project.folders.filter(is_trash=True).first()
    if not trash_folder:
        return Response({"detail": _("Trash folder not found.")}, status=status.HTTP_404_NOT_FOUND)
    Folder.objects.filter(parent=trash_folder).delete()
    ProjectFile.objects.filter(folder=trash_folder).delete()
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
@permission_classes([IsAuthenticated, IsProjectOwner])
def duplicate_folder_view(request, project_pk, folder_pk):
    """Duplicate a folder and all its contents right after the original."""
    project = get_object_or_404(Project, pk=project_pk)
    folder = get_object_or_404(Folder, pk=folder_pk, project=project)
    if folder.is_trash:
        return Response({"detail": _("Cannot duplicate the trash folder.")}, status=status.HTTP_400_BAD_REQUEST)
    insert_order = folder.order + 1
    Folder.objects.filter(project=project, parent=folder.parent, order__gte=insert_order).update(order=db_models.F("order") + 1)
    new_folder = _duplicate_folder_recursive(folder, project, folder.parent, insert_order, copy_suffix=" copy")
    return Response({"id": new_folder.pk, "title": new_folder.title}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def duplicate_text_view(request, project_pk, file_pk):
    """Duplicate a text file right after the original."""
    project = get_object_or_404(Project, pk=project_pk)
    text = get_object_or_404(ProjectFile, pk=file_pk, project=project)
    insert_order = text.order + 1
    ProjectFile.objects.filter(folder=text.folder, order__gte=insert_order).update(order=db_models.F("order") + 1)
    new_text = ProjectFile.objects.create(
        project=project, folder=text.folder, file_type=text.file_type,
        title=text.title + " copy", description=text.description, notes=text.notes,
        tags=text.tags, target_word_count=text.target_word_count,
        icon=text.icon, content=text.content, order=insert_order,
    )
    return Response({"id": new_text.pk, "title": new_text.title}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def copy_to_project_view(request, project_pk):
    """Copy a folder or text to another project."""
    source_project = get_object_or_404(Project, pk=project_pk)
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
    return Response({"detail": _("Copied.")}, status=status.HTTP_201_CREATED)

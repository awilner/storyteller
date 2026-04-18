from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..broadcast import broadcast_project_event
from ..models import Folder, Project, ProjectFile, Status
from ..permissions import ProjectPermission
from ..serializers import StatusSerializer


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def status_list_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == "GET":
        statuses = Status.objects.filter(project=project).order_by("order")
        return Response(StatusSerializer(statuses, many=True).data)
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = StatusSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        serializer.save(project=project)
    except IntegrityError:
        return Response({"detail": _("A status with this name already exists in the project.")}, status=status.HTTP_400_BAD_REQUEST)
    broadcast_project_event(project_pk, "statuses_changed", user_id=request.user.id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated, ProjectPermission])
def status_detail_view(request, project_pk, status_pk):
    status_obj = get_object_or_404(Status, pk=status_pk, project_id=project_pk)
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if request.method == "DELETE":
        count = Folder.objects.filter(status=status_obj).count() + ProjectFile.objects.filter(status=status_obj).count()
        if count > 0 and request.query_params.get("confirm") != "true":
            return Response(
                {"count": count, "detail": _("This status is assigned to %(count)d items. Add ?confirm=true to proceed.") % {"count": count}},
                status=status.HTTP_409_CONFLICT,
            )
        if count > 0:
            Folder.objects.filter(status=status_obj).update(status=None)
            ProjectFile.objects.filter(status=status_obj).update(status=None)
        status_obj.delete()
        broadcast_project_event(project_pk, "statuses_changed", user_id=request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = StatusSerializer(status_obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    try:
        serializer.save()
    except IntegrityError:
        return Response({"detail": _("A status with this name already exists in the project.")}, status=status.HTTP_400_BAD_REQUEST)
    broadcast_project_event(project_pk, "statuses_changed", user_id=request.user.id)
    return Response(serializer.data)

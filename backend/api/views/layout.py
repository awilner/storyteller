from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..broadcast import broadcast_project_event
from ..models import CompileLayout, Project
from ..permissions import ProjectPermission
from ..serializers import CompileLayoutSerializer


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def compile_layout_list_view(request, project_pk):
    """List or create compile layouts for a project."""
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == "GET":
        layouts = CompileLayout.objects.filter(project=project)
        return Response(CompileLayoutSerializer(layouts, many=True).data)
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = CompileLayoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(project=project)
    broadcast_project_event(project_pk, "layouts_changed", user_id=request.user.id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, ProjectPermission])
def compile_layout_detail_view(request, project_pk, layout_pk):
    """Retrieve, update, or delete a compile layout."""
    layout = get_object_or_404(CompileLayout, pk=layout_pk, project_id=project_pk)
    if request.method == "GET":
        return Response(CompileLayoutSerializer(layout).data)
    if request.project_role == "read-only":
        return Response(
            {"detail": "Read-only access does not allow this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if request.method == "DELETE":
        layout.delete()
        broadcast_project_event(project_pk, "layouts_changed", user_id=request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = CompileLayoutSerializer(layout, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    broadcast_project_event(project_pk, "layouts_changed", user_id=request.user.id)
    return Response(serializer.data)

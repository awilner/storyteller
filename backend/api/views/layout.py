from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import CompileLayout, Project
from ..permissions import IsProjectOwner
from ..serializers import CompileLayoutSerializer


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
    serializer = CompileLayoutSerializer(layout, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)

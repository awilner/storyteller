import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..import_export import export_scrivener, export_ywriter
from ..models import Project
from ..permissions import ProjectPermission
from ..import_export import import_scrivener_zip
from ..serializers import ProjectListSerializer
from ..import_export import import_ywriter

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def scrivener_import_view(request):
    """Import a Scrivener .scriv.zip file as a new project."""
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response({"detail": _("No file uploaded.")}, status=status.HTTP_400_BAD_REQUEST)
    try:
        project = import_scrivener_zip(uploaded, request.user)
    except ValueError:
        logger.error("Scrivener import failed.", exc_info=True)
        return Response({"detail": "Scrivener import failed."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(ProjectListSerializer(project).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ywriter_import_view(request):
    """Import a yWriter7 .yw7 file as a new project."""
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response({"detail": _("No file uploaded.")}, status=status.HTTP_400_BAD_REQUEST)
    try:
        project = import_ywriter(uploaded, request.user)
    except ValueError:
        logger.error("YWriter import failed.", exc_info=True)
        return Response({"detail": "YWriter import failed."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(ProjectListSerializer(project).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated, ProjectPermission])
def export_scrivener_view(request, project_pk):
    """Export a project as a Scrivener .scriv.zip file."""
    project = get_object_or_404(Project, pk=project_pk)
    data = export_scrivener(project)
    safe_title = project.title.replace('"', "'")
    response = HttpResponse(data, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{safe_title}.scriv.zip"'
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated, ProjectPermission])
def export_ywriter_view(request, project_pk):
    """Export a project as a yWriter7 .yw7 file."""
    project = get_object_or_404(Project, pk=project_pk)
    data = export_ywriter(project)
    safe_title = project.title.replace('"', "'")
    response = HttpResponse(data, content_type="application/xml")
    response["Content-Disposition"] = f'attachment; filename="{safe_title}.yw7"'
    return response

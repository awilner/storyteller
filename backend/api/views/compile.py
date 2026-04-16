import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..compiler.engine import CompileEngine
from ..models import Project
from ..permissions import IsProjectOwner
from ..serializers import CompileRequestSerializer

logger = logging.getLogger(__name__)


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

    root_folder = project.folders.filter(pk=root_folder_id).first()
    if root_folder is None:
        return Response({"detail": _("Folder not found.")}, status=status.HTTP_404_NOT_FOUND)
    if root_folder.is_trash:
        return Response({"detail": _("Cannot compile from trash folder.")}, status=status.HTTP_400_BAD_REQUEST)

    layout_settings = None
    if layout_id:
        layout = project.compile_layouts.filter(pk=layout_id).first()
        if layout is None:
            return Response({"detail": _("Layout not found.")}, status=status.HTTP_404_NOT_FOUND)
        layout_settings = layout.settings

    if front_matter_folder_id is not None:
        if project.folders.filter(pk=front_matter_folder_id).first() is None:
            return Response({"detail": _("Folder not found.")}, status=status.HTTP_404_NOT_FOUND)

    if back_matter_folder_id is not None:
        if project.folders.filter(pk=back_matter_folder_id).first() is None:
            return Response({"detail": _("Folder not found.")}, status=status.HTTP_404_NOT_FOUND)

    try:
        engine = CompileEngine()
        file_bytes, content_type, filename = engine.compile(
            project=project, root_folder_id=root_folder_id, format_key=format_key,
            layout_settings=layout_settings, front_matter_folder_id=front_matter_folder_id,
            back_matter_folder_id=back_matter_folder_id,
        )
    except ValueError:
        logger.error("Compile failed.", exc_info=True)
        return Response({"detail": "Compile failed."}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.error("Compile failed.", exc_info=True)
        return Response({"detail": _("Compile failed.")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    safe_filename = filename.replace('"', "'")
    response = HttpResponse(file_bytes, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{safe_filename}"'
    return response

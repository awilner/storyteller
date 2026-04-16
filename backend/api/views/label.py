from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Folder, Label, Project, ProjectFile
from ..permissions import IsProjectOwner
from ..serializers import LabelSerializer


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
        return Response({"detail": _("A label with this name already exists in the project.")}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsProjectOwner])
def label_detail_view(request, project_pk, label_pk):
    label = get_object_or_404(Label, pk=label_pk, project_id=project_pk)
    if request.method == "DELETE":
        count = Folder.objects.filter(label=label).count() + ProjectFile.objects.filter(label=label).count()
        if count > 0 and request.query_params.get("confirm") != "true":
            return Response(
                {"count": count, "detail": _("This label is assigned to %(count)d items. Add ?confirm=true to proceed.") % {"count": count}},
                status=status.HTTP_409_CONFLICT,
            )
        if count > 0:
            Folder.objects.filter(label=label).update(label=None)
            ProjectFile.objects.filter(label=label).update(label=None)
        label.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = LabelSerializer(label, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    try:
        serializer.save()
    except IntegrityError:
        return Response({"detail": _("A label with this name already exists in the project.")}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.data)

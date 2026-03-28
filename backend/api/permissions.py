from rest_framework import permissions

from .models import Project, ProjectFile


class IsProjectOwner(permissions.BasePermission):
    """
    Allow access only to the owner of the resolved Project.

    Resolves the project from view kwargs:
    - project_pk  → look up Project directly
    - file_pk     → look up ProjectFile, then its project
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        project = self._resolve_project(view)
        if project is None:
            return False

        return project.owner_id == user.id

    # ------------------------------------------------------------------
    def _resolve_project(self, view):
        """Return the Project instance from URL kwargs, or None."""
        kwargs = view.kwargs

        project_pk = kwargs.get("project_pk")
        if project_pk is not None:
            try:
                return Project.objects.get(pk=project_pk)
            except Project.DoesNotExist:
                return None

        file_pk = kwargs.get("file_pk")
        if file_pk is not None:
            try:
                return ProjectFile.objects.select_related("project").get(
                    pk=file_pk,
                ).project
            except ProjectFile.DoesNotExist:
                return None

        return None

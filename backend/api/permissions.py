from rest_framework import permissions
from django.db.models import Q

from .models import (
    Folder,
    ObjectPermissionOverride,
    Project,
    ProjectFile,
    ProjectShare,
)


class ProjectPermission(permissions.BasePermission):
    """
    Resolves effective permission for the current user on the target project/object.

    Sets ``request.project_role`` to one of: "owner", "co-author", "read-only", None.
    Sets ``request.effective_permission`` for object-level checks.
    """

    def has_permission(self, request, view):
        project = self._resolve_project(view)
        if project is None:
            return False

        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Owner always has full access
        if project.owner_id == user.id:
            request.project_role = "owner"
            request.effective_permission = "owner"
            return True

        # Check for a share record
        share = ProjectShare.objects.filter(
            project=project, user=user
        ).first()
        if share is None:
            return False

        request.project_role = share.role
        request.effective_permission = self._compute_effective(share, view)
        return request.effective_permission is not None

    # ------------------------------------------------------------------
    # Project resolution
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

    # ------------------------------------------------------------------
    # Object resolution
    # ------------------------------------------------------------------

    def _resolve_object(self, view):
        """
        Extract the target object type and ID from view kwargs.

        Returns a tuple of (obj_type, obj_id) where obj_type is 'folder',
        'file', or None when the endpoint is project-level.
        """
        kwargs = view.kwargs

        folder_pk = kwargs.get("folder_pk")
        if folder_pk is not None:
            return ("folder", folder_pk)

        file_pk = kwargs.get("file_pk")
        if file_pk is not None:
            return ("file", file_pk)

        return (None, None)

    # ------------------------------------------------------------------
    # Ancestor chain
    # ------------------------------------------------------------------

    def _get_ancestor_chain(self, obj_type, obj_id):
        """
        Build the chain from the target object up to the project root.

        Returns a list starting with the target object itself, then its
        parent folder, grandparent, etc.  Each element is a Folder or
        ProjectFile instance.
        """
        ancestors = []

        if obj_type == "file":
            try:
                pf = ProjectFile.objects.select_related("folder").get(pk=obj_id)
            except ProjectFile.DoesNotExist:
                return ancestors
            ancestors.append(pf)
            current_folder = pf.folder
        elif obj_type == "folder":
            try:
                current_folder = Folder.objects.get(pk=obj_id)
            except Folder.DoesNotExist:
                return ancestors
            ancestors.append(current_folder)
            current_folder = current_folder.parent
        else:
            return ancestors

        # Walk up the folder tree
        while current_folder is not None:
            ancestors.append(current_folder)
            # Avoid extra queries when parent is already loaded
            try:
                current_folder = Folder.objects.get(pk=current_folder.parent_id) if current_folder.parent_id else None
            except Folder.DoesNotExist:
                break

        return ancestors

    # ------------------------------------------------------------------
    # Effective permission computation
    # ------------------------------------------------------------------

    def _compute_effective(self, share, view):
        """
        Walk the folder tree to find the nearest ancestor override.

        1. Start with the collaborator's project-level role from ProjectShare.
        2. Look up ObjectPermissionOverride for the target object and ancestors.
        3. The nearest ancestor override wins.  If it is 'none', return None
           (no access).
        4. If no override exists, the project-level role applies.
        """
        obj_type, obj_id = self._resolve_object(view)
        if obj_type is None:
            # Project-level endpoint — no object overrides apply
            return share.role

        ancestors = self._get_ancestor_chain(obj_type, obj_id)
        if not ancestors:
            return share.role

        # Collect all relevant overrides in a single query
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

        # Walk from root toward target; nearest ancestor override wins (per req 8.1, 8.2)
        for ancestor in reversed(ancestors):
            if isinstance(ancestor, Folder):
                key = ("folder", ancestor.id)
            else:
                key = ("file", ancestor.id)

            if key in override_map:
                perm = override_map[key]
                return None if perm == "none" else perm

        # No override found — project-level role applies
        return share.role



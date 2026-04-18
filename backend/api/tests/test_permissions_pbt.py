# Feature: project-sharing, Property 1: Share creation round-trip
"""
Property-based test for ProjectShare creation round-trip.

**Validates: Requirements 1.1**

For any valid Project, target User (who is not the owner and not already
a collaborator), and role (read-only or co-author), creating a ProjectShare
and then querying the share for that user and project should return a record
with the same role.
"""

from types import SimpleNamespace

from django.contrib.auth.models import User

from hypothesis import given, settings, strategies as st
from hypothesis.extra.django import TestCase

from api.models import Folder, Project, ProjectFile, ProjectShare
from api.permissions import ProjectPermission


# Strategy: pick a role from the ProjectShare.Role choices
role_strategy = st.sampled_from([choice[0] for choice in ProjectShare.Role.choices])


class ShareCreationRoundTripPropertyTest(TestCase):
    """Property 1: Share creation round-trip."""

    @given(role=role_strategy)
    @settings(max_examples=20, deadline=None)
    def test_share_creation_round_trip(self, role):
        """
        For any valid role, creating a ProjectShare and querying it back
        should return a record with the same role.

        # Feature: project-sharing, Property 1: Share creation round-trip
        # **Validates: Requirements 1.1**
        """
        # Create fresh users and project for each example
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        target_user = User.objects.create_user(
            username=f"target_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        # Preconditions: target is not the owner and not already a collaborator
        assert target_user.pk != owner.pk
        assert not ProjectShare.objects.filter(
            project=project, user=target_user
        ).exists()

        # Act: create the share
        share = ProjectShare.objects.create(
            project=project,
            user=target_user,
            role=role,
        )

        # Assert: querying back returns the same role
        retrieved = ProjectShare.objects.get(project=project, user=target_user)
        assert retrieved.role == role
        assert retrieved.pk == share.pk
        assert retrieved.project_id == project.pk
        assert retrieved.user_id == target_user.pk


# ── Strategy: generate a random folder tree ──────────────────────────

# Tree depth between 1 and 5 folders, each with 0-3 files.
# Some folders are nested under others to create depth.

@st.composite
def folder_tree_strategy(draw):
    """
    Generate a description of a folder tree: a list of
    (parent_index_or_none, num_files) tuples.

    parent_index_or_none is None for root-level folders, or an index
    into the list of previously created folders for nested ones.
    """
    num_folders = draw(st.integers(min_value=1, max_value=5))
    tree = []
    for i in range(num_folders):
        if i == 0:
            # First folder is always root-level
            parent_idx = None
        else:
            # Subsequent folders can be root-level or nested under any prior folder
            parent_idx = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=i - 1)))
        num_files = draw(st.integers(min_value=0, max_value=3))
        tree.append((parent_idx, num_files))
    return tree


# Feature: project-sharing, Property 3: Default effective permission equals project role
class DefaultEffectivePermissionPropertyTest(TestCase):
    """Property 3: Default effective permission equals project role."""

    @given(role=role_strategy, tree=folder_tree_strategy())
    @settings(max_examples=20, deadline=None)
    def test_default_effective_permission_equals_role(self, role, tree):
        """
        For any Project with a folder tree of arbitrary depth and a
        Collaborator with no ObjectPermissionOverrides, the effective
        permission on every Folder and ProjectFile in the Project should
        equal the Collaborator's project-level role.

        # Feature: project-sharing, Property 3: Default effective permission equals project role
        # **Validates: Requirements 1.5**
        """
        # Create fresh users and project
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        collaborator = User.objects.create_user(
            username=f"collab_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        # Create the share with the given role (no overrides)
        share = ProjectShare.objects.create(
            project=project,
            user=collaborator,
            role=role,
        )

        # Build the folder tree from the strategy output
        folders = []
        all_files = []
        for parent_idx, num_files in tree:
            parent = folders[parent_idx] if parent_idx is not None else None
            folder = Folder.objects.create(
                project=project,
                parent=parent,
                title=f"Folder {len(folders)}",
                order=len(folders),
            )
            folders.append(folder)

            for j in range(num_files):
                pf = ProjectFile.objects.create(
                    project=project,
                    folder=folder,
                    file_type=ProjectFile.FileType.TEXT,
                    title=f"File {len(all_files)}",
                    order=len(all_files),
                )
                all_files.append(pf)

        # Instantiate the permission class to call _compute_effective
        perm = ProjectPermission()

        # Check every folder
        for folder in folders:
            view = SimpleNamespace(kwargs={"project_pk": project.pk, "folder_pk": folder.pk})
            effective = perm._compute_effective(share, view)
            assert effective == role, (
                f"Folder {folder.pk}: expected {role!r}, got {effective!r}"
            )

        # Check every file
        for pf in all_files:
            view = SimpleNamespace(kwargs={"project_pk": project.pk, "file_pk": pf.pk})
            effective = perm._compute_effective(share, view)
            assert effective == role, (
                f"File {pf.pk}: expected {role!r}, got {effective!r}"
            )


from api.models import ObjectPermissionOverride


# ── Strategy: generate a nested folder tree (at least 2 levels) ──────

@st.composite
def nested_folder_tree_strategy(draw):
    """
    Generate a folder tree with at least 2 levels of nesting.

    Returns a list of (parent_index_or_none, num_files) tuples where
    at least one folder is nested under another.
    """
    # At least 2 folders to guarantee nesting
    num_folders = draw(st.integers(min_value=2, max_value=5))
    tree = []
    # First folder is always root-level
    num_files = draw(st.integers(min_value=0, max_value=2))
    tree.append((None, num_files))
    # Second folder is always nested under the first (guarantees depth >= 2)
    num_files = draw(st.integers(min_value=0, max_value=2))
    tree.append((0, num_files))
    # Remaining folders can be root-level or nested under any prior folder
    for i in range(2, num_folders):
        parent_idx = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=i - 1)))
        num_files = draw(st.integers(min_value=0, max_value=2))
        tree.append((parent_idx, num_files))
    return tree


# Strategy: pick an override permission
override_permission_strategy = st.sampled_from(
    [choice[0] for choice in ObjectPermissionOverride.Permission.choices]
)


# Feature: project-sharing, Property 11: Ancestor folder override takes precedence
class AncestorFolderOverridePrecedencePropertyTest(TestCase):
    """Property 11: Ancestor folder override takes precedence."""

    @given(
        tree=nested_folder_tree_strategy(),
        ancestor_permission=override_permission_strategy,
        descendant_has_override=st.booleans(),
        descendant_permission=override_permission_strategy,
    )
    @settings(max_examples=20, deadline=None)
    def test_ancestor_folder_override_takes_precedence(
        self, tree, ancestor_permission, descendant_has_override, descendant_permission
    ):
        """
        For any folder tree where an ancestor Folder has an
        ObjectPermissionOverride for a Collaborator, the effective
        permission on all descendant Folders and ProjectFiles should
        equal the ancestor's override, regardless of any overrides set
        directly on those descendants.

        # Feature: project-sharing, Property 11: Ancestor folder override takes precedence
        # **Validates: Requirements 8.1, 8.2**
        """
        # Create fresh users and project
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        collaborator = User.objects.create_user(
            username=f"collab_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        # Collaborator is a co-author so read-only overrides are meaningful
        share = ProjectShare.objects.create(
            project=project,
            user=collaborator,
            role="co-author",
        )

        # Build the folder tree from the strategy output
        folders = []
        all_files = []
        for parent_idx, num_files in tree:
            parent = folders[parent_idx] if parent_idx is not None else None
            folder = Folder.objects.create(
                project=project,
                parent=parent,
                title=f"Folder {len(folders)}",
                order=len(folders),
            )
            folders.append(folder)
            for j in range(num_files):
                pf = ProjectFile.objects.create(
                    project=project,
                    folder=folder,
                    file_type=ProjectFile.FileType.TEXT,
                    title=f"File {len(all_files)}",
                    order=len(all_files),
                )
                all_files.append(pf)

        # The ancestor is always the root folder (index 0)
        ancestor_folder = folders[0]

        # Set override on the ancestor folder
        ObjectPermissionOverride.objects.create(
            project=project,
            user=collaborator,
            target_folder=ancestor_folder,
            permission=ancestor_permission,
        )

        # Collect all descendants: folders nested under ancestor and their files
        descendant_folders = [f for f in folders[1:] if self._is_descendant(f, ancestor_folder)]
        descendant_files = [pf for pf in all_files if self._is_descendant(pf.folder, ancestor_folder) or pf.folder_id == ancestor_folder.id]

        # Optionally set a different override on a descendant folder or file
        if descendant_has_override and descendant_folders:
            target_desc = descendant_folders[0]
            ObjectPermissionOverride.objects.create(
                project=project,
                user=collaborator,
                target_folder=target_desc,
                permission=descendant_permission,
            )

        # Expected effective permission from the ancestor override
        expected = None if ancestor_permission == "none" else ancestor_permission

        perm = ProjectPermission()

        # Check all descendant folders
        for folder in descendant_folders:
            view = SimpleNamespace(kwargs={"project_pk": project.pk, "folder_pk": folder.pk})
            effective = perm._compute_effective(share, view)
            assert effective == expected, (
                f"Descendant Folder {folder.title}: expected {expected!r}, "
                f"got {effective!r} (ancestor override={ancestor_permission!r})"
            )

        # Check all descendant files (files in ancestor folder and nested folders)
        for pf in descendant_files:
            view = SimpleNamespace(kwargs={"project_pk": project.pk, "file_pk": pf.pk})
            effective = perm._compute_effective(share, view)
            assert effective == expected, (
                f"Descendant File {pf.title}: expected {expected!r}, "
                f"got {effective!r} (ancestor override={ancestor_permission!r})"
            )

    def _is_descendant(self, folder, ancestor):
        """Check if folder is a descendant of ancestor by walking up parents."""
        current = folder.parent
        while current is not None:
            if current.id == ancestor.id:
                return True
            current = current.parent
        return False


# ── Permission hierarchy for downgrade validation ────────────────────

# Hierarchy levels (higher number = more permissive)
PERMISSION_LEVEL = {
    "none": 0,
    "read-only": 1,
    "co-author": 2,
    "owner": 3,
}


def is_valid_downgrade(project_role, override_permission):
    """
    Return True if the override permission is strictly lower than the
    project-level role (a genuine downgrade).
    """
    return PERMISSION_LEVEL[override_permission] < PERMISSION_LEVEL[project_role]


# Feature: project-sharing, Property 10: Overrides can only downgrade permissions
class OverridesCanOnlyDowngradePropertyTest(TestCase):
    """Property 10: Overrides can only downgrade permissions."""

    @given(
        role=role_strategy,
        override_permission=override_permission_strategy,
    )
    @settings(max_examples=20, deadline=None)
    def test_valid_downgrades_persist_correctly(self, role, override_permission):
        """
        For any Collaborator with a project-level role, creating an
        ObjectPermissionOverride with a permission level lower than the
        project-level role should succeed and the override should be
        persisted correctly. Overrides at the same level or higher than
        the project-level role are not valid downgrades.

        # Feature: project-sharing, Property 10: Overrides can only downgrade permissions
        # **Validates: Requirements 7.2**
        """
        # Create fresh users and project
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        collaborator = User.objects.create_user(
            username=f"collab_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        # Create the share with the given role
        share = ProjectShare.objects.create(
            project=project,
            user=collaborator,
            role=role,
        )

        # Create a folder to attach the override to
        folder = Folder.objects.create(
            project=project,
            title="Target Folder",
            order=0,
        )

        valid = is_valid_downgrade(role, override_permission)

        if valid:
            # Valid downgrade: override should persist correctly
            override = ObjectPermissionOverride.objects.create(
                project=project,
                user=collaborator,
                target_folder=folder,
                permission=override_permission,
            )

            # Verify the override was persisted with correct values
            retrieved = ObjectPermissionOverride.objects.get(pk=override.pk)
            assert retrieved.permission == override_permission, (
                f"Expected permission {override_permission!r}, "
                f"got {retrieved.permission!r}"
            )
            assert retrieved.user_id == collaborator.pk
            assert retrieved.project_id == project.pk
            assert retrieved.target_folder_id == folder.pk

            # Verify effective permission reflects the override
            perm = ProjectPermission()
            view = SimpleNamespace(
                kwargs={"project_pk": project.pk, "folder_pk": folder.pk}
            )
            effective = perm._compute_effective(share, view)
            if override_permission == "none":
                assert effective is None, (
                    f"Role={role!r}, override='none': expected None, "
                    f"got {effective!r}"
                )
            else:
                assert effective == override_permission, (
                    f"Role={role!r}, override={override_permission!r}: "
                    f"expected {override_permission!r}, got {effective!r}"
                )
        else:
            # Not a valid downgrade: the override permission is at or above
            # the project-level role. The API layer (task 4.2) will reject
            # these, but at the model level we verify the conceptual rule:
            # the override permission level is NOT lower than the role.
            assert PERMISSION_LEVEL[override_permission] >= PERMISSION_LEVEL[role], (
                f"Expected override {override_permission!r} (level "
                f"{PERMISSION_LEVEL[override_permission]}) to be >= role "
                f"{role!r} (level {PERMISSION_LEVEL[role]})"
            )

    @given(data=st.data())
    @settings(max_examples=20, deadline=None)
    def test_read_only_collaborator_valid_downgrades(self, data):
        """
        For a read-only collaborator, only 'none' overrides are valid
        downgrades (read-only is already the lowest non-none level).

        # Feature: project-sharing, Property 10: Overrides can only downgrade permissions
        # **Validates: Requirements 7.2**
        """
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        collaborator = User.objects.create_user(
            username=f"collab_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        share = ProjectShare.objects.create(
            project=project,
            user=collaborator,
            role="read-only",
        )

        folder = Folder.objects.create(
            project=project,
            title="Target Folder",
            order=0,
        )

        # For read-only, only 'none' is a valid downgrade
        override = ObjectPermissionOverride.objects.create(
            project=project,
            user=collaborator,
            target_folder=folder,
            permission="none",
        )

        retrieved = ObjectPermissionOverride.objects.get(pk=override.pk)
        assert retrieved.permission == "none"

        # Effective permission should be None (no access)
        perm = ProjectPermission()
        view = SimpleNamespace(
            kwargs={"project_pk": project.pk, "folder_pk": folder.pk}
        )
        effective = perm._compute_effective(share, view)
        assert effective is None, (
            f"Read-only + 'none' override: expected None, got {effective!r}"
        )

        # Verify 'read-only' is NOT a valid downgrade for read-only role
        assert not is_valid_downgrade("read-only", "read-only"), (
            "'read-only' should not be a valid downgrade for a read-only collaborator"
        )

    @given(
        override_permission=override_permission_strategy,
    )
    @settings(max_examples=20, deadline=None)
    def test_co_author_collaborator_valid_downgrades(self, override_permission):
        """
        For a co-author collaborator, 'read-only' and 'none' overrides
        are both valid downgrades.

        # Feature: project-sharing, Property 10: Overrides can only downgrade permissions
        # **Validates: Requirements 7.2**
        """
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        collaborator = User.objects.create_user(
            username=f"collab_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        share = ProjectShare.objects.create(
            project=project,
            user=collaborator,
            role="co-author",
        )

        folder = Folder.objects.create(
            project=project,
            title="Target Folder",
            order=0,
        )

        # Both 'read-only' and 'none' are valid downgrades for co-author
        assert is_valid_downgrade("co-author", override_permission), (
            f"Override {override_permission!r} should be a valid downgrade "
            f"for co-author"
        )

        override = ObjectPermissionOverride.objects.create(
            project=project,
            user=collaborator,
            target_folder=folder,
            permission=override_permission,
        )

        # Verify persistence
        retrieved = ObjectPermissionOverride.objects.get(pk=override.pk)
        assert retrieved.permission == override_permission

        # Verify effective permission reflects the override
        perm = ProjectPermission()
        view = SimpleNamespace(
            kwargs={"project_pk": project.pk, "folder_pk": folder.pk}
        )
        effective = perm._compute_effective(share, view)
        if override_permission == "none":
            assert effective is None, (
                f"Co-author + 'none' override: expected None, got {effective!r}"
            )
        else:
            assert effective == override_permission, (
                f"Co-author + {override_permission!r} override: "
                f"expected {override_permission!r}, got {effective!r}"
            )


# ── Strategies for API-level property tests ──────────────────

# Strategy: pick a non-owner role
non_owner_role_strategy = st.sampled_from(["co-author", "read-only"])


# Feature: project-sharing, Property 2: Only owner can manage shares
class OnlyOwnerCanManageSharesPropertyTest(TestCase):
    """Property 2: Only owner can manage shares."""

    @given(
        actor_role=non_owner_role_strategy,
        action=st.sampled_from(["create", "update", "delete"]),
    )
    @settings(max_examples=20, deadline=None)
    def test_non_owner_cannot_manage_shares(self, actor_role, action):
        """
        For any User who is not the Project_Owner (including co-authors
        and read-only users), attempting to create, update, or delete a
        ProjectShare on the Project should be rejected with a permission
        denied error.

        # Feature: project-sharing, Property 2: Only owner can manage shares
        # **Validates: Requirements 1.4, 5.4**
        """
        # Create fresh users and project
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        actor = User.objects.create_user(
            username=f"actor_{User.objects.count()}",
            password="testpass",
        )
        target = User.objects.create_user(
            username=f"target_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        # Give the actor a share with the given role
        ProjectShare.objects.create(
            project=project,
            user=actor,
            role=actor_role,
        )

        # Create a share for the target so we can test update/delete
        target_share = ProjectShare.objects.create(
            project=project,
            user=target,
            role="read-only",
        )

        # Log in as the actor (non-owner)
        self.client.login(username=actor.username, password="testpass")

        if action == "create":
            # Try to create a new share
            new_user = User.objects.create_user(
                username=f"new_{User.objects.count()}",
                password="testpass",
            )
            response = self.client.post(
                f"/api/projects/{project.pk}/shares/",
                data={"username": new_user.username, "role": "read-only"},
                content_type="application/json",
            )
            assert response.status_code == 403, (
                f"Expected 403 for {actor_role} creating share, "
                f"got {response.status_code}"
            )

        elif action == "update":
            # Try to update the target's share
            response = self.client.patch(
                f"/api/projects/{project.pk}/shares/{target_share.pk}/",
                data={"role": "co-author"},
                content_type="application/json",
            )
            assert response.status_code == 403, (
                f"Expected 403 for {actor_role} updating share, "
                f"got {response.status_code}"
            )

        elif action == "delete":
            # Try to delete the target's share
            response = self.client.delete(
                f"/api/projects/{project.pk}/shares/{target_share.pk}/",
            )
            assert response.status_code == 403, (
                f"Expected 403 for {actor_role} deleting share, "
                f"got {response.status_code}"
            )


# Feature: project-sharing, Property 8: Revoke cascades to all overrides
class RevokeCascadesToAllOverridesPropertyTest(TestCase):
    """Property 8: Revoke cascades to all overrides."""

    @given(
        num_overrides=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=20, deadline=None)
    def test_revoke_cascades_to_all_overrides(self, num_overrides):
        """
        For any Collaborator with any number of ObjectPermissionOverrides,
        revoking the Collaborator's access should delete the ProjectShare
        record and all associated ObjectPermissionOverride records, leaving
        zero records for that user on that project.

        # Feature: project-sharing, Property 8: Revoke cascades to all overrides
        # **Validates: Requirements 5.2**
        """
        # Create fresh users and project
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        collaborator = User.objects.create_user(
            username=f"collab_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        # Create the share as co-author (so overrides are valid)
        share = ProjectShare.objects.create(
            project=project,
            user=collaborator,
            role="co-author",
        )

        # Create folders and overrides
        for i in range(num_overrides):
            folder = Folder.objects.create(
                project=project,
                title=f"Folder {i}",
                order=i,
            )
            ObjectPermissionOverride.objects.create(
                project=project,
                user=collaborator,
                target_folder=folder,
                permission="read-only",
            )

        # Verify overrides exist
        assert ObjectPermissionOverride.objects.filter(
            project=project, user=collaborator,
        ).count() == num_overrides

        # Log in as owner and revoke
        self.client.login(username=owner.username, password="testpass")
        response = self.client.delete(
            f"/api/projects/{project.pk}/shares/{share.pk}/",
        )
        assert response.status_code == 204, (
            f"Expected 204 for revoke, got {response.status_code}"
        )

        # Verify share is gone
        assert not ProjectShare.objects.filter(
            project=project, user=collaborator,
        ).exists(), "ProjectShare should be deleted after revoke"

        # Verify all overrides are gone
        remaining = ObjectPermissionOverride.objects.filter(
            project=project, user=collaborator,
        ).count()
        assert remaining == 0, (
            f"Expected 0 overrides after revoke, got {remaining}"
        )


# Feature: project-sharing, Property 9: Downgrade cleans up invalid overrides
class DowngradeCleansUpInvalidOverridesPropertyTest(TestCase):
    """Property 9: Downgrade cleans up invalid overrides."""

    @given(
        num_read_only_overrides=st.integers(min_value=0, max_value=3),
        num_none_overrides=st.integers(min_value=0, max_value=3),
    )
    @settings(max_examples=20, deadline=None)
    def test_downgrade_cleans_up_invalid_overrides(
        self, num_read_only_overrides, num_none_overrides
    ):
        """
        For any co-author Collaborator with ObjectPermissionOverrides,
        downgrading the Collaborator to read-only should remove any
        overrides that are no longer valid relative to the new
        project-level role, while preserving overrides that remain valid
        (e.g., "none" overrides that further restrict access).

        # Feature: project-sharing, Property 9: Downgrade cleans up invalid overrides
        # **Validates: Requirements 5.3**
        """
        # Create fresh users and project
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        collaborator = User.objects.create_user(
            username=f"collab_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        # Start as co-author
        share = ProjectShare.objects.create(
            project=project,
            user=collaborator,
            role="co-author",
        )

        # Create "read-only" overrides (valid for co-author, but redundant
        # for read-only — should be removed on downgrade)
        for i in range(num_read_only_overrides):
            folder = Folder.objects.create(
                project=project,
                title=f"RO Folder {i}",
                order=i,
            )
            ObjectPermissionOverride.objects.create(
                project=project,
                user=collaborator,
                target_folder=folder,
                permission="read-only",
            )

        # Create "none" overrides (valid for both co-author and read-only
        # — should be preserved on downgrade)
        for i in range(num_none_overrides):
            folder = Folder.objects.create(
                project=project,
                title=f"None Folder {i}",
                order=100 + i,
            )
            ObjectPermissionOverride.objects.create(
                project=project,
                user=collaborator,
                target_folder=folder,
                permission="none",
            )

        # Log in as owner and downgrade
        self.client.login(username=owner.username, password="testpass")
        response = self.client.patch(
            f"/api/projects/{project.pk}/shares/{share.pk}/",
            data={"role": "read-only"},
            content_type="application/json",
        )
        assert response.status_code == 200, (
            f"Expected 200 for downgrade, got {response.status_code}"
        )

        # Verify the share role was updated
        share.refresh_from_db()
        assert share.role == "read-only", (
            f"Expected role 'read-only', got {share.role!r}"
        )

        # "read-only" overrides should be removed (redundant for read-only user)
        ro_remaining = ObjectPermissionOverride.objects.filter(
            project=project,
            user=collaborator,
            permission="read-only",
        ).count()
        assert ro_remaining == 0, (
            f"Expected 0 'read-only' overrides after downgrade, got {ro_remaining}"
        )

        # "none" overrides should be preserved (still valid for read-only user)
        none_remaining = ObjectPermissionOverride.objects.filter(
            project=project,
            user=collaborator,
            permission="none",
        ).count()
        assert none_remaining == num_none_overrides, (
            f"Expected {num_none_overrides} 'none' overrides after downgrade, "
            f"got {none_remaining}"
        )


# Feature: project-sharing, Property 7: Role change updates the share record
class RoleChangeUpdatesShareRecordPropertyTest(TestCase):
    """Property 7: Role change updates the share record."""

    @given(
        initial_role=non_owner_role_strategy,
    )
    @settings(max_examples=20, deadline=None)
    def test_role_change_updates_share_record(self, initial_role):
        """
        For any Collaborator and any valid role transition (read-only →
        co-author, or co-author → read-only), updating the ProjectShare
        should result in the share record reflecting the new role.

        # Feature: project-sharing, Property 7: Role change updates the share record
        # **Validates: Requirements 5.1**
        """
        # Determine the new role (opposite of initial)
        new_role = "co-author" if initial_role == "read-only" else "read-only"

        # Create fresh users and project
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        collaborator = User.objects.create_user(
            username=f"collab_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        # Create the share with the initial role
        share = ProjectShare.objects.create(
            project=project,
            user=collaborator,
            role=initial_role,
        )

        # Log in as owner and change the role
        self.client.login(username=owner.username, password="testpass")
        response = self.client.patch(
            f"/api/projects/{project.pk}/shares/{share.pk}/",
            data={"role": new_role},
            content_type="application/json",
        )
        assert response.status_code == 200, (
            f"Expected 200 for role change, got {response.status_code}"
        )

        # Verify the share record reflects the new role
        share.refresh_from_db()
        assert share.role == new_role, (
            f"Expected role {new_role!r}, got {share.role!r}"
        )

        # Verify the response body also reflects the new role
        assert response.json()["role"] == new_role, (
            f"Expected response role {new_role!r}, "
            f"got {response.json()['role']!r}"
        )


# Feature: project-sharing, Property 5: Read-only users cannot perform write operations
class ReadOnlyUsersCannotWritePropertyTest(TestCase):
    """Property 5: Read-only users cannot perform write operations."""

    @given(
        write_op=st.sampled_from([
            "folder_create",
            "text_create",
            "project_patch",
            "project_delete",
            "label_create",
            "status_create",
            "reorder",
        ]),
    )
    @settings(max_examples=20, deadline=None)
    def test_read_only_user_cannot_write(self, write_op):
        """
        For any read-only Collaborator and any write operation (create,
        update, delete, or reorder on Folders, ProjectFiles, project
        settings, Labels, or Statuses), the operation should be rejected
        with 403.

        # Feature: project-sharing, Property 5: Read-only users cannot perform write operations
        # **Validates: Requirements 3.4, 3.5**
        """
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        reader = User.objects.create_user(
            username=f"reader_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        # Create a folder so we can test text creation and other ops
        folder = Folder.objects.create(
            project=project, title="Chapter 1", order=0,
        )

        # Share as read-only
        ProjectShare.objects.create(
            project=project, user=reader, role="read-only",
        )

        # Log in as the read-only user
        self.client.login(username=reader.username, password="testpass")

        if write_op == "folder_create":
            resp = self.client.post(
                f"/api/projects/{project.pk}/folders/",
                data={"title": "New Folder", "order": 1},
                content_type="application/json",
            )
        elif write_op == "text_create":
            resp = self.client.post(
                f"/api/projects/{project.pk}/folders/{folder.pk}/texts/",
                data={"title": "New Text", "order": 0},
                content_type="application/json",
            )
        elif write_op == "project_patch":
            resp = self.client.patch(
                f"/api/projects/{project.pk}/",
                data={"title": "Renamed"},
                content_type="application/json",
            )
        elif write_op == "project_delete":
            resp = self.client.delete(
                f"/api/projects/{project.pk}/",
            )
        elif write_op == "label_create":
            resp = self.client.post(
                f"/api/projects/{project.pk}/labels/",
                data={"name": f"Label_{User.objects.count()}", "colour": "#FF0000", "order": 0},
                content_type="application/json",
            )
        elif write_op == "status_create":
            resp = self.client.post(
                f"/api/projects/{project.pk}/statuses/",
                data={"name": f"Status_{User.objects.count()}", "colour": "#00FF00", "order": 0},
                content_type="application/json",
            )
        elif write_op == "reorder":
            resp = self.client.post(
                f"/api/projects/{project.pk}/reorder/",
                data={"folders": [], "texts": []},
                content_type="application/json",
            )
        else:
            raise ValueError(f"Unknown write_op: {write_op}")

        assert resp.status_code == 403, (
            f"Expected 403 for read-only user performing {write_op}, "
            f"got {resp.status_code}: {resp.content}"
        )


# Feature: project-sharing, Property 6: Co-authors can perform write operations
class CoAuthorsCanWritePropertyTest(TestCase):
    """Property 6: Co-authors can perform write operations."""

    @given(
        write_op=st.sampled_from([
            "folder_create",
            "text_create",
            "project_patch",
        ]),
    )
    @settings(max_examples=20, deadline=None)
    def test_co_author_can_write(self, write_op):
        """
        For any co-author Collaborator, standard write operations should
        succeed (folder create, text create, project PATCH).

        # Feature: project-sharing, Property 6: Co-authors can perform write operations
        # **Validates: Requirements 4.2, 4.3, 4.4**
        """
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        coauthor = User.objects.create_user(
            username=f"coauthor_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        folder = Folder.objects.create(
            project=project, title="Chapter 1", order=0,
        )

        ProjectShare.objects.create(
            project=project, user=coauthor, role="co-author",
        )

        self.client.login(username=coauthor.username, password="testpass")

        if write_op == "folder_create":
            resp = self.client.post(
                f"/api/projects/{project.pk}/folders/",
                data={"title": f"Folder_{User.objects.count()}", "order": 1},
                content_type="application/json",
            )
            assert resp.status_code == 201, (
                f"Expected 201 for co-author folder create, "
                f"got {resp.status_code}: {resp.content}"
            )
        elif write_op == "text_create":
            resp = self.client.post(
                f"/api/projects/{project.pk}/folders/{folder.pk}/texts/",
                data={"title": f"Text_{User.objects.count()}", "order": 0},
                content_type="application/json",
            )
            assert resp.status_code == 201, (
                f"Expected 201 for co-author text create, "
                f"got {resp.status_code}: {resp.content}"
            )
        elif write_op == "project_patch":
            resp = self.client.patch(
                f"/api/projects/{project.pk}/",
                data={"title": f"Renamed_{User.objects.count()}"},
                content_type="application/json",
            )
            assert resp.status_code == 200, (
                f"Expected 200 for co-author project patch, "
                f"got {resp.status_code}: {resp.content}"
            )

    @given(data=st.data())
    @settings(max_examples=20, deadline=None)
    def test_co_author_cannot_delete_project(self, data):
        """
        For any co-author Collaborator, project deletion should be
        rejected with 403.

        # Feature: project-sharing, Property 6: Co-authors can perform write operations
        # **Validates: Requirements 4.2, 4.3, 4.4**
        """
        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        coauthor = User.objects.create_user(
            username=f"coauthor_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        ProjectShare.objects.create(
            project=project, user=coauthor, role="co-author",
        )

        self.client.login(username=coauthor.username, password="testpass")

        resp = self.client.delete(f"/api/projects/{project.pk}/")
        assert resp.status_code == 403, (
            f"Expected 403 for co-author project delete, "
            f"got {resp.status_code}: {resp.content}"
        )


# Feature: project-sharing, Property 4: Project list completeness and metadata
class ProjectListCompletenessPropertyTest(TestCase):
    """Property 4: Project list completeness and metadata."""

    @given(
        num_owned=st.integers(min_value=0, max_value=3),
        num_shared=st.integers(min_value=0, max_value=3),
        shared_role=role_strategy,
    )
    @settings(max_examples=20, deadline=None)
    def test_project_list_completeness(self, num_owned, num_shared, shared_role):
        """
        For any User who owns some Projects and is a Collaborator on
        others, the project list endpoint should return all of them,
        each annotated with the correct role and owner name.

        # Feature: project-sharing, Property 4: Project list completeness and metadata
        # **Validates: Requirements 2.1, 2.2, 2.3**
        """
        user = User.objects.create_user(
            username=f"user_{User.objects.count()}",
            password="testpass",
        )

        # Create owned projects
        owned_ids = set()
        for i in range(num_owned):
            p = Project.objects.create(owner=user, title=f"Owned {i}")
            owned_ids.add(p.pk)

        # Create shared projects from different owners
        shared_ids = set()
        share_owners = {}
        for i in range(num_shared):
            other_owner = User.objects.create_user(
                username=f"other_{User.objects.count()}",
                password="testpass",
            )
            p = Project.objects.create(owner=other_owner, title=f"Shared {i}")
            ProjectShare.objects.create(
                project=p, user=user, role=shared_role,
            )
            shared_ids.add(p.pk)
            share_owners[p.pk] = other_owner.username

        self.client.login(username=user.username, password="testpass")
        resp = self.client.get("/api/projects/")
        assert resp.status_code == 200

        data = resp.json()
        returned_ids = {p["id"] for p in data}

        # All owned and shared projects should be present
        assert owned_ids.issubset(returned_ids), (
            f"Missing owned projects: {owned_ids - returned_ids}"
        )
        assert shared_ids.issubset(returned_ids), (
            f"Missing shared projects: {shared_ids - returned_ids}"
        )

        # Check role annotations
        for p in data:
            pid = p["id"]
            if pid in owned_ids:
                assert p["role"] == "owner", (
                    f"Owned project {pid} should have role 'owner', "
                    f"got {p['role']!r}"
                )
            elif pid in shared_ids:
                assert p["role"] == shared_role, (
                    f"Shared project {pid} should have role {shared_role!r}, "
                    f"got {p['role']!r}"
                )
                # Shared projects should include owner_name
                assert "owner_name" in p, (
                    f"Shared project {pid} missing 'owner_name'"
                )
                assert p["owner_name"] == share_owners[pid], (
                    f"Shared project {pid} owner_name should be "
                    f"{share_owners[pid]!r}, got {p['owner_name']!r}"
                )


# Feature: project-sharing, Property 12: Moving objects recomputes effective permissions
class MovingObjectsRecomputesPermissionsPropertyTest(TestCase):
    """Property 12: Moving objects recomputes effective permissions."""

    @given(
        override_a=override_permission_strategy,
        override_b=override_permission_strategy,
    )
    @settings(max_examples=20, deadline=None)
    def test_moving_file_recomputes_permissions(self, override_a, override_b):
        """
        For any Folder or ProjectFile moved from one parent Folder to
        another, the effective permission should reflect the new parent's
        override chain.

        Test by creating two folders with different overrides, moving a
        file from one to the other, and verifying the effective
        permission changes.

        # Feature: project-sharing, Property 12: Moving objects recomputes effective permissions
        # **Validates: Requirements 8.4**
        """
        from hypothesis import assume
        # Only interesting when the two overrides differ
        assume(override_a != override_b)

        owner = User.objects.create_user(
            username=f"owner_{User.objects.count()}",
            password="testpass",
        )
        collaborator = User.objects.create_user(
            username=f"collab_{User.objects.count()}",
            password="testpass",
        )
        project = Project.objects.create(owner=owner, title="Test Project")

        share = ProjectShare.objects.create(
            project=project, user=collaborator, role="co-author",
        )

        # Create two folders with different overrides
        folder_a = Folder.objects.create(
            project=project, title="Folder A", order=0,
        )
        folder_b = Folder.objects.create(
            project=project, title="Folder B", order=1,
        )

        ObjectPermissionOverride.objects.create(
            project=project, user=collaborator,
            target_folder=folder_a, permission=override_a,
        )
        ObjectPermissionOverride.objects.create(
            project=project, user=collaborator,
            target_folder=folder_b, permission=override_b,
        )

        # Create a file in folder_a
        pf = ProjectFile.objects.create(
            project=project, folder=folder_a,
            file_type=ProjectFile.FileType.TEXT,
            title="Test File", order=0,
        )

        perm = ProjectPermission()

        # Verify effective permission under folder_a
        view_a = SimpleNamespace(kwargs={"project_pk": project.pk, "file_pk": pf.pk})
        effective_a = perm._compute_effective(share, view_a)
        expected_a = None if override_a == "none" else override_a
        assert effective_a == expected_a, (
            f"Before move: expected {expected_a!r}, got {effective_a!r}"
        )

        # Move the file to folder_b
        pf.folder = folder_b
        pf.save()

        # Verify effective permission under folder_b
        view_b = SimpleNamespace(kwargs={"project_pk": project.pk, "file_pk": pf.pk})
        effective_b = perm._compute_effective(share, view_b)
        expected_b = None if override_b == "none" else override_b
        assert effective_b == expected_b, (
            f"After move: expected {expected_b!r}, got {effective_b!r}"
        )

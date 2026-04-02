from django.conf import settings
from django.db import models


# ── Book project models ───────────────────────────────────────

class Project(models.Model):
    """A book project owned by a user."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default="")
    settings = models.JSONField(
        blank=True,
        default=dict,
        help_text="Project-level settings (e.g. editor_font).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class Folder(models.Model):
    """Groups items within a project into ordered folders. Supports nesting."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="folders",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    tags = models.JSONField(blank=True, default=list)
    target_word_count = models.PositiveIntegerField(null=True, blank=True)
    icon = models.CharField(max_length=10, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    is_trash = models.BooleanField(
        default=False,
        help_text="Whether this folder is the project's trash folder.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.order}. {self.title}"


class ProjectFile(models.Model):
    """
    A markdown file belonging to a project.

    type determines the role of the file:
      - text: narrative content, optionally grouped into a folder
      - character: character profile (world-building)
      - location: location description (world-building)
      - item: object or artifact (world-building)
      - note: free-form notes (world-building)
    """

    class FileType(models.TextChoices):
        TEXT = "text", "Text"
        CHARACTER = "character", "Character"
        LOCATION = "location", "Location"
        ITEM = "item", "Item"
        NOTE = "note", "Note"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="files",
    )
    folder = models.ForeignKey(
        Folder,
        on_delete=models.CASCADE,
        related_name="texts",
        help_text="Parent folder for this file.",
    )
    file_type = models.CharField(
        max_length=20,
        choices=FileType.choices,
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    tags = models.JSONField(blank=True, default=list)
    target_word_count = models.PositiveIntegerField(null=True, blank=True)
    icon = models.CharField(max_length=10, blank=True, default="")
    content = models.TextField(
        blank=True,
        default="",
        help_text="Markdown content.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Sort order within folder (texts) or within project (world-building).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"[{self.file_type}] {self.title}"


class FileVersion(models.Model):
    """An immutable snapshot of a ProjectFile's content at a point in time."""

    file = models.ForeignKey(
        ProjectFile,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    content = models.TextField()
    content_length = models.PositiveIntegerField(
        editable=False,
        help_text="Cached length of content in characters.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.content_length = len(self.content)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Version {self.pk} of {self.file}"


class OIDCIdentity(models.Model):
    """Links an OIDC provider subject to a local Django user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oidc_identities",
    )
    provider = models.CharField(max_length=200)
    sub = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("provider", "sub")
        verbose_name_plural = "OIDC identities"

    def __str__(self):
        return f"{self.provider}:{self.sub} → {self.user}"


class UserSettings(models.Model):
    """Per-user application preferences."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="app_settings",
    )
    preferences = models.JSONField(
        blank=True,
        default=dict,
        help_text="User preferences (e.g. default_editor_font).",
    )

    class Meta:
        verbose_name_plural = "User settings"

    def __str__(self):
        return f"Settings for {self.user}"

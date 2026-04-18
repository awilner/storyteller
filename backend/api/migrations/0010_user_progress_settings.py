"""Data migration: create UserProgressSettings table and move per-project
progress keys from Project.settings into per-user records for the owner."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


# Keys that move from project.settings → UserProgressSettings
_MIGRATED_KEYS = (
    "daily_target",
    "session_target",
    "session_start_word_count",
    "session_started_at",
)


def forwards(apps, schema_editor):
    """For every project whose settings JSON contains any of the four
    progress keys, create (or update) a UserProgressSettings row for the
    project owner and strip the keys from the JSON."""

    Project = apps.get_model("api", "Project")
    UserProgressSettings = apps.get_model("api", "UserProgressSettings")

    for project in Project.objects.all().iterator():
        project_settings = project.settings or {}
        has_keys = any(k in project_settings for k in _MIGRATED_KEYS)
        if not has_keys:
            continue

        ups, _created = UserProgressSettings.objects.get_or_create(
            project=project,
            user=project.owner,
        )

        # Copy values from project.settings → UserProgressSettings fields
        if "daily_target" in project_settings:
            ups.daily_target = project_settings["daily_target"]
        if "session_target" in project_settings:
            ups.session_target = project_settings["session_target"]
        if "session_start_word_count" in project_settings:
            ups.session_start_word_count = project_settings["session_start_word_count"]
        if "session_started_at" in project_settings:
            ups.session_started_at = project_settings["session_started_at"]
        ups.save()

        # Remove the migrated keys from project.settings
        for key in _MIGRATED_KEYS:
            project_settings.pop(key, None)
        project.settings = project_settings
        project.save(update_fields=["settings"])


def backwards(apps, schema_editor):
    """Reverse migration: copy values from the owner's UserProgressSettings
    back into project.settings so the old code can read them."""

    Project = apps.get_model("api", "Project")
    UserProgressSettings = apps.get_model("api", "UserProgressSettings")

    for project in Project.objects.all().iterator():
        try:
            ups = UserProgressSettings.objects.get(
                project=project,
                user=project.owner,
            )
        except UserProgressSettings.DoesNotExist:
            continue

        project_settings = project.settings or {}

        if ups.daily_target is not None:
            project_settings["daily_target"] = ups.daily_target
        if ups.session_target is not None:
            project_settings["session_target"] = ups.session_target
        if ups.session_start_word_count is not None:
            project_settings["session_start_word_count"] = ups.session_start_word_count
        if ups.session_started_at is not None:
            project_settings["session_started_at"] = (
                ups.session_started_at.isoformat()
                if hasattr(ups.session_started_at, "isoformat")
                else str(ups.session_started_at)
            )

        project.settings = project_settings
        project.save(update_fields=["settings"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0009_alter_sessionwordcount_unique_together_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProgressSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "daily_target",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "session_target",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "session_start_word_count",
                    models.IntegerField(blank=True, null=True),
                ),
                (
                    "session_started_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_progress_settings",
                        to="api.project",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress_settings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("project", "user")},
            },
        ),
        migrations.RunPython(forwards, backwards),
    ]

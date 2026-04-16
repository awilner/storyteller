# Remove auto_now_add from SessionWordCount.ended_at so we can set it
# explicitly as UTC. Backfill any NULL ended_at with started_at.

from django.db import migrations, models


def backfill_ended_at(apps, schema_editor):
    """Set ended_at = started_at for any rows where ended_at is NULL."""
    SessionWordCount = apps.get_model("api", "SessionWordCount")
    SessionWordCount.objects.filter(ended_at__isnull=True).update(
        ended_at=models.F("started_at"),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_progress_tracking"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sessionwordcount",
            name="ended_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(backfill_ended_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sessionwordcount",
            name="ended_at",
            field=models.DateTimeField(),
        ),
    ]

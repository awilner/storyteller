import datetime
import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import DailyWordCount, ManuscriptWordCount, Project, SessionWordCount
from ..progress import compute_project_word_count
from ..serializers import DailyWordCountSerializer, ManuscriptWordCountSerializer, SessionWordCountSerializer

logger = logging.getLogger(__name__)


@api_view(["GET", "PATCH", "POST"])
@permission_classes([IsAuthenticated])
def progress_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk, owner=request.user)

    if request.method == "GET":
        current_wc = compute_project_word_count(project)
        settings = project.settings or {}
        user = request.user

        # Upsert today's manuscript snapshot
        today = datetime.date.today()
        ms_snapshot, created = ManuscriptWordCount.objects.get_or_create(
            project=project, date=today,
            defaults={"word_count": current_wc, "start_word_count": current_wc},
        )
        if not created:
            ms_snapshot.word_count = current_wc
            ms_snapshot.save(update_fields=["word_count", "updated_at"])

        # Upsert today's daily word count for this user
        daily_obj, daily_created = DailyWordCount.objects.get_or_create(
            project=project, date=today, user=user,
            defaults={"word_count": 0},
        )
        daily_wc = current_wc - ms_snapshot.start_word_count
        if not daily_created:
            daily_obj.word_count = daily_wc
            daily_obj.save(update_fields=["word_count", "updated_at"])
        else:
            daily_obj.word_count = daily_wc
            daily_obj.save(update_fields=["word_count"])

        # Initialize session start if missing
        if "session_start_word_count" not in settings:
            settings["session_start_word_count"] = current_wc
            settings["session_started_at"] = datetime.datetime.now().isoformat()
            project.settings = settings
            project.save(update_fields=["settings"])

        session_start = settings.get("session_start_word_count", current_wc)
        try:
            session_start = int(session_start)
        except (TypeError, ValueError):
            session_start = current_wc
        session_wc = current_wc - session_start

        snapshots = ManuscriptWordCount.objects.filter(project=project).order_by("date")
        daily_counts = DailyWordCount.objects.filter(project=project, user=user).order_by("date")
        sessions = SessionWordCount.objects.filter(project=project, user=user).order_by("-ended_at")[:50]

        return Response({
            "current_word_count": current_wc,
            "manuscript_target": settings.get("manuscript_target"),
            "daily_target": settings.get("daily_target"),
            "session_target": settings.get("session_target"),
            "daily_word_count": daily_wc,
            "session_word_count": session_wc,
            "snapshots": ManuscriptWordCountSerializer(snapshots, many=True).data,
            "daily_counts": DailyWordCountSerializer(daily_counts, many=True).data,
            "sessions": SessionWordCountSerializer(sessions, many=True).data,
        })

    elif request.method == "PATCH":
        settings = project.settings or {}
        errors = {}
        for key in ("manuscript_target", "daily_target", "session_target"):
            if key in request.data:
                val = request.data[key]
                if val is None or val == "":
                    settings.pop(key, None)
                else:
                    try:
                        val = int(val)
                    except (TypeError, ValueError):
                        errors[key] = ["Must be a positive integer."]
                        continue
                    if val <= 0:
                        errors[key] = ["Ensure this value is greater than 0."]
                        continue
                    settings[key] = val
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        project.settings = settings
        project.save(update_fields=["settings"])
        return Response({
            "manuscript_target": settings.get("manuscript_target"),
            "daily_target": settings.get("daily_target"),
            "session_target": settings.get("session_target"),
        })

    else:  # POST
        action = request.data.get("action")
        if action != "reset_session":
            return Response({"detail": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            current_wc = compute_project_word_count(project)
            settings = project.settings or {}
            old_start = settings.get("session_start_word_count", current_wc)
            try:
                old_start = int(old_start)
            except (TypeError, ValueError):
                old_start = current_wc
            session_started = settings.get("session_started_at")
            word_count = current_wc - old_start
            logger.info("reset_session: project=%s current_wc=%s old_start=%s word_count=%s session_started=%r",
                        project_pk, current_wc, old_start, word_count, session_started)
            if word_count != 0:
                started = datetime.datetime.now()
                if session_started:
                    try:
                        parsed = datetime.datetime.fromisoformat(str(session_started))
                        if parsed.tzinfo is not None:
                            parsed = parsed.replace(tzinfo=None)
                        started = parsed
                    except (ValueError, TypeError):
                        logger.warning("reset_session: failed to parse session_started_at=%r, using now()", session_started, exc_info=True)
                logger.info("reset_session: creating SessionWordCount started_at=%s", started)
                SessionWordCount.objects.create(
                    project=project, user=request.user,
                    started_at=started, word_count=word_count,
                )
            settings["session_start_word_count"] = current_wc
            settings["session_started_at"] = datetime.datetime.now().isoformat()
            project.settings = settings
            project.save(update_fields=["settings"])
            return Response({"session_start_word_count": current_wc, "session_word_count": 0})
        except Exception:
            logger.exception("reset_session failed for project %s", project_pk)
            raise

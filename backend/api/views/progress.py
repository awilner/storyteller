import datetime
import logging
import time

from zoneinfo import ZoneInfo

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import DailyWordCount, ManuscriptWordCount, Project, SessionWordCount, UserProgressSettings, UserSettings
from ..permissions import ProjectPermission
from ..progress import compute_contribution_ranking, compute_project_word_count
from ..serializers import DailyWordCountSerializer, ManuscriptWordCountSerializer, SessionWordCountSerializer

logger = logging.getLogger(__name__)


def _get_user_tz(user):
    """Get user's timezone as a ZoneInfo. Falls back to server local tz."""
    try:
        prefs = UserSettings.objects.get(user=user).preferences
        tz_name = prefs.get("timezone", "")
        if tz_name:
            return ZoneInfo(tz_name)
    except (UserSettings.DoesNotExist, KeyError):
        pass
    # Server default
    local_tz = time.tzname[0]
    try:
        return ZoneInfo(local_tz)
    except Exception:
        return ZoneInfo("UTC")


def _get_user_today(user):
    """Get the user's 'today' date, accounting for timezone and day cutover offset.

    The cutover offset shifts when the day boundary falls:
      0 = Midnight (default)
      +4 = 4 AM next day (day resets at 4am — for night owls)
      -6 = 6 PM (day resets at 6pm)
    """
    tz = _get_user_tz(user)
    now = datetime.datetime.now(tz)
    cutover_offset = 0
    try:
        prefs = UserSettings.objects.get(user=user).preferences
        cutover_offset = int(prefs.get("day_cutover_hour", 0))
    except (UserSettings.DoesNotExist, KeyError, TypeError, ValueError):
        pass
    # Shift the clock back by the offset to determine the logical date
    adjusted = now - datetime.timedelta(hours=cutover_offset)
    return adjusted.date()


@api_view(["GET", "PATCH", "POST"])
@permission_classes([IsAuthenticated, ProjectPermission])
def progress_view(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)

    if request.method == "GET":
        current_wc = compute_project_word_count(project)
        proj_settings = project.settings or {}
        user = request.user
        role = getattr(request, "project_role", None)

        # Resolve the user's per-user progress settings record
        user_progress, _created = UserProgressSettings.objects.get_or_create(
            project=project, user=user,
        )

        # Compute "today" for the manuscript using the project owner's timezone
        owner_tz = _get_user_tz(project.owner)
        owner_today = datetime.datetime.now(owner_tz).date()

        # Upsert today's manuscript snapshot
        ms_snapshot, created = ManuscriptWordCount.objects.get_or_create(
            project=project, date=owner_today,
            defaults={"word_count": current_wc, "start_word_count": current_wc},
        )
        if not created:
            ms_snapshot.word_count = current_wc
            ms_snapshot.save(update_fields=["word_count", "updated_at"])

        # Resolve timezone strings for the response
        owner_tz_name = str(owner_tz)
        user_tz = _get_user_tz(user)
        user_tz_name = str(user_tz)

        snapshots = ManuscriptWordCount.objects.filter(project=project).order_by("date")

        # Build base response (shared by all roles)
        data = {
            "current_word_count": current_wc,
            "manuscript_target": proj_settings.get("manuscript_target"),
            "snapshots": ManuscriptWordCountSerializer(snapshots, many=True).data,
            "owner_timezone": owner_tz_name,
            "user_timezone": user_tz_name,
        }

        # Determine contribution ranking visibility
        ranking_visibility = proj_settings.get("ranking_visibility", "owner")

        show_ranking = (
            role == "owner"
            or (role == "co-author" and ranking_visibility in ("coauthors", "all"))
            or (role == "read-only" and ranking_visibility == "all")
        )
        if show_ranking:
            data["contribution_ranking"] = compute_contribution_ranking(project)

        # Owner sees ranking visibility setting
        if role == "owner":
            data["ranking_visibility"] = ranking_visibility

        # Read-only users get a limited response — no targets, charts, or session data
        if role == "read-only":
            return Response(data)

        # --- Owner / co-author: full progress data ---

        # Compute "today" for the user (with day cutover support)
        user_today = _get_user_today(user)

        # Upsert today's daily word count for this user
        daily_obj, daily_created = DailyWordCount.objects.get_or_create(
            project=project, date=user_today, user=user,
            defaults={"word_count": 0},
        )
        daily_wc = current_wc - ms_snapshot.start_word_count
        if not daily_created:
            daily_obj.word_count = daily_wc
            daily_obj.save(update_fields=["word_count", "updated_at"])
        else:
            daily_obj.word_count = daily_wc
            daily_obj.save(update_fields=["word_count"])

        # Initialize session start state in UserProgressSettings if missing
        if user_progress.session_start_word_count is None:
            user_progress.session_start_word_count = current_wc
            user_progress.session_started_at = timezone.now()
            user_progress.save(update_fields=["session_start_word_count", "session_started_at", "updated_at"])

        session_start = user_progress.session_start_word_count
        try:
            session_start = int(session_start)
        except (TypeError, ValueError):
            session_start = current_wc
        session_wc = current_wc - session_start

        daily_counts = DailyWordCount.objects.filter(project=project, user=user).order_by("date")
        sessions = SessionWordCount.objects.filter(project=project, user=user).order_by("-ended_at")[:50]

        day_cutover_hour = 0
        try:
            prefs = UserSettings.objects.get(user=user).preferences
            day_cutover_hour = int(prefs.get("day_cutover_hour", 0))
        except (UserSettings.DoesNotExist, KeyError, TypeError, ValueError):
            pass

        data.update({
            "daily_target": user_progress.daily_target,
            "session_target": user_progress.session_target,
            "daily_word_count": daily_wc,
            "session_word_count": session_wc,
            "daily_counts": DailyWordCountSerializer(daily_counts, many=True).data,
            "sessions": SessionWordCountSerializer(sessions, many=True).data,
            "day_cutover_hour": day_cutover_hour,
        })

        return Response(data)

    elif request.method == "PATCH":
        if request.project_role == "read-only":
            return Response(
                {"detail": "Read-only access does not allow this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        proj_settings = project.settings or {}
        errors = {}
        settings_changed = False

        # --- Ranking visibility (owner-only) ---
        if "ranking_visibility" in request.data:
            if request.project_role != "owner":
                return Response(
                    {"detail": "Only the project owner can change ranking visibility."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            val = request.data["ranking_visibility"]
            if val not in ("owner", "coauthors", "all"):
                errors["ranking_visibility"] = ["Must be one of: owner, coauthors, all."]
            else:
                proj_settings["ranking_visibility"] = val
                settings_changed = True

        # --- Manuscript target (project-level) ---
        if "manuscript_target" in request.data:
            val = request.data["manuscript_target"]
            if val is None or val == "":
                proj_settings.pop("manuscript_target", None)
                settings_changed = True
            else:
                if isinstance(val, float):
                    errors["manuscript_target"] = ["Must be a positive integer."]
                else:
                    try:
                        val = int(val)
                    except (TypeError, ValueError):
                        errors["manuscript_target"] = ["Must be a positive integer."]
                    else:
                        if val <= 0:
                            errors["manuscript_target"] = ["Must be a positive integer."]
                        else:
                            proj_settings["manuscript_target"] = val
                            settings_changed = True

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # --- Per-user targets (UserProgressSettings) ---
        user_progress, _created = UserProgressSettings.objects.get_or_create(
            project=project, user=request.user,
        )
        user_fields_changed = []

        for target_key in ("daily_target", "session_target"):
            if target_key in request.data:
                val = request.data[target_key]
                if val is None or val == "":
                    setattr(user_progress, target_key, None)
                    user_fields_changed.append(target_key)
                else:
                    if isinstance(val, float):
                        errors[target_key] = ["Must be a positive integer."]
                        continue
                    try:
                        val = int(val)
                    except (TypeError, ValueError):
                        errors[target_key] = ["Must be a positive integer."]
                        continue
                    if val <= 0:
                        errors[target_key] = ["Must be a positive integer."]
                        continue
                    setattr(user_progress, target_key, val)
                    user_fields_changed.append(target_key)

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if settings_changed:
            project.settings = proj_settings
            project.save(update_fields=["settings"])

        if user_fields_changed:
            user_fields_changed.append("updated_at")
            user_progress.save(update_fields=user_fields_changed)

        return Response({
            "manuscript_target": proj_settings.get("manuscript_target"),
            "daily_target": user_progress.daily_target,
            "session_target": user_progress.session_target,
        })

    else:  # POST
        if request.project_role == "read-only":
            return Response(
                {"detail": "Read-only access does not allow this action."},
                status=status.HTTP_403_FORBIDDEN,
            )
        action = request.data.get("action")
        if action != "reset_session":
            return Response({"detail": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            current_wc = compute_project_word_count(project)

            # Read session state from the user's UserProgressSettings record
            user_progress, _created = UserProgressSettings.objects.get_or_create(
                project=project, user=request.user,
            )

            old_start = user_progress.session_start_word_count
            if old_start is None:
                old_start = current_wc
            try:
                old_start = int(old_start)
            except (TypeError, ValueError):
                old_start = current_wc

            session_started = user_progress.session_started_at
            word_count = current_wc - old_start
            logger.info("reset_session: project=%s current_wc=%s old_start=%s word_count=%s session_started=%r",
                        project_pk, current_wc, old_start, word_count, session_started)
            if word_count != 0:
                started = timezone.now()
                if session_started:
                    try:
                        parsed = session_started
                        # Handle string values that may exist from legacy data
                        if isinstance(parsed, str):
                            parsed = datetime.datetime.fromisoformat(parsed)
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
                        started = parsed
                    except (ValueError, TypeError):
                        logger.warning("reset_session: failed to parse session_started_at=%r, using now()", session_started, exc_info=True)
                logger.info("reset_session: creating SessionWordCount started_at=%s", started)
                SessionWordCount.objects.create(
                    project=project, user=request.user,
                    started_at=started, ended_at=timezone.now(),
                    word_count=word_count,
                )

            # Reset session state in the user's UserProgressSettings only
            user_progress.session_start_word_count = current_wc
            user_progress.session_started_at = timezone.now()
            user_progress.save(update_fields=["session_start_word_count", "session_started_at", "updated_at"])

            return Response({"session_start_word_count": current_wc, "session_word_count": 0})
        except Exception:
            logger.exception("reset_session failed for project %s", project_pk)
            raise

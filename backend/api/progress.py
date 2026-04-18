from django.db.models import Sum, Value
from django.db.models.functions import Coalesce

from .models import DailyWordCount, Folder, ProjectFile


def count_words(text):
    if not text or not text.strip():
        return 0
    return len(text.split())


def compute_contribution_ranking(project):
    """Return a list of {user_id, username, total_word_count} ordered by total desc.

    Only the owner and co-authors are included. Read-only users are excluded
    because they cannot contribute words to the manuscript.
    """
    from .models import ProjectShare

    # Collect user IDs that are owner or co-author
    eligible_user_ids = {project.owner_id}
    eligible_user_ids.update(
        ProjectShare.objects.filter(project=project, role="co-author")
        .values_list("user_id", flat=True)
    )

    ranking = (
        DailyWordCount.objects
        .filter(project=project, user_id__in=eligible_user_ids)
        .values("user__id", "user__username")
        .annotate(total_word_count=Coalesce(Sum("word_count"), Value(0)))
        .order_by("-total_word_count")
    )
    return [
        {"user_id": r["user__id"], "username": r["user__username"], "total_word_count": r["total_word_count"]}
        for r in ranking
    ]


def _get_trash_folder_ids(project):
    trash = Folder.objects.filter(project=project, is_trash=True).first()
    if not trash:
        return set()
    ids = {trash.id}
    queue = [trash.id]
    while queue:
        parent_id = queue.pop()
        children = list(Folder.objects.filter(parent_id=parent_id).values_list("id", flat=True))
        ids.update(children)
        queue.extend(children)
    return ids


def compute_project_word_count(project):
    trash_ids = _get_trash_folder_ids(project)
    texts = ProjectFile.objects.filter(
        project=project, file_type="text", include_in_compile=True,
    ).only("content")
    if trash_ids:
        texts = texts.exclude(folder_id__in=trash_ids)
    total = 0
    for pf in texts:
        total += count_words(pf.content)
    return total

from .models import Folder, ProjectFile


def count_words(text):
    if not text or not text.strip():
        return 0
    return len(text.split())


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

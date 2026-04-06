from dataclasses import dataclass, field


@dataclass
class Scene:
    title: str
    content: str  # raw markdown


@dataclass
class Chapter:
    title: str
    scenes: list = field(default_factory=list)  # list[Scene]


def _collect_folder(folder):
    """Collect chapters from a single folder hierarchy.

    Interleaves child folders and direct text files by their ``order``
    field so the compiled output matches the project tree ordering.
    """
    chapters: list[Chapter] = []

    # Direct text files of this folder
    direct_texts = list(
        folder.texts.filter(
            include_in_compile=True,
            file_type="text",
        ).order_by("order")
    )

    # Child folders (non-trash, included)
    child_folders = list(
        folder.children.filter(
            include_in_compile=True,
            is_trash=False,
        ).order_by("order")
    )

    # Interleave by order — same logic as the project tree
    combined = []
    for t in direct_texts:
        combined.append(("text", t.order, t))
    for c in child_folders:
        combined.append(("folder", c.order, c))
    combined.sort(key=lambda x: x[1])

    # Accumulate consecutive texts into a single chapter, flush when
    # we hit a child folder (which produces its own chapters).
    pending_scenes: list[Scene] = []

    def flush_pending():
        nonlocal pending_scenes
        if pending_scenes:
            chapters.append(Chapter(title=folder.title, scenes=pending_scenes))
            pending_scenes = []

    for kind, _order, obj in combined:
        if kind == "text":
            pending_scenes.append(Scene(title=obj.title, content=obj.content))
        else:
            flush_pending()
            chapters.extend(_collect_folder(obj))

    flush_pending()

    return chapters


def collect_content(root_folder, front_matter_folder=None, back_matter_folder=None):
    """Traverse the project tree and return an ordered list of Chapters.

    Parameters
    ----------
    root_folder : Folder
        The main compile root.
    front_matter_folder : Folder | None
        Optional folder whose content is prepended.
    back_matter_folder : Folder | None
        Optional folder whose content is appended.

    Returns
    -------
    list[Chapter]
    """
    chapters: list[Chapter] = []

    if front_matter_folder is not None:
        chapters.extend(_collect_folder(front_matter_folder))

    chapters.extend(_collect_folder(root_folder))

    if back_matter_folder is not None:
        chapters.extend(_collect_folder(back_matter_folder))

    return chapters

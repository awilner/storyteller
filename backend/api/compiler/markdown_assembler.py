DEFAULT_LAYOUT = {
    "chapter_heading_style": "title",
    "page_break_before_chapter": True,
    "blank_page_before_chapter": False,
    "body_font_family": "Times New Roman",
    "body_font_size": 12,
    "heading_font_family": "Times New Roman",
    "heading_font_size": 18,
    "show_scene_titles": False,
    "scene_separator": "three_asterisks",
    "scene_separator_custom_text": "",
    "margin_top": "2.54cm",
    "margin_bottom": "2.54cm",
    "margin_left": "3.18cm",
    "margin_right": "3.18cm",
}

_SCENE_SEPARATORS = {
    "horizontal_rule": "\n\n---\n\n",
    "three_asterisks": "\n\n* * *\n\n",
    "blank_line": "\n\n",
    "none": "",
}


def _get(layout, key):
    return layout.get(key, DEFAULT_LAYOUT[key])


def _chapter_heading(chapter, index, layout):
    style = _get(layout, "chapter_heading_style")
    if style == "numbered":
        return f"Chapter {index}"
    if style == "numbered_title":
        return f"Chapter {index}: {chapter.title}"
    # default: "title"
    return chapter.title


def _scene_separator(layout):
    sep_type = _get(layout, "scene_separator")
    if sep_type == "custom_text":
        custom = _get(layout, "scene_separator_custom_text")
        return f"\n\n{custom}\n\n"
    return _SCENE_SEPARATORS.get(sep_type, "\n\n* * *\n\n")


def assemble_markdown(chapters, layout, chapter_offset=1):
    """Build a single markdown document from chapters/scenes.

    Parameters
    ----------
    chapters : list[Chapter]
        Ordered list of chapters containing scenes.
    layout : dict
        Layout settings (keys from DEFAULT_LAYOUT).
    chapter_offset : int
        Starting number for numbered chapter headings.

    Returns
    -------
    str
        The assembled markdown string.
    """
    if layout is None:
        layout = {}

    parts: list[str] = []
    page_break = _get(layout, "page_break_before_chapter")
    show_titles = _get(layout, "show_scene_titles")
    separator = _scene_separator(layout)

    for i, chapter in enumerate(chapters):
        # Page break before chapter (skip for the very first chapter)
        if page_break and i > 0:
            parts.append("\\newpage\n\n")

        # Chapter heading
        heading = _chapter_heading(chapter, chapter_offset + i, layout)
        parts.append(f"# {heading}\n\n")

        for j, scene in enumerate(chapter.scenes):
            # Scene separator between consecutive scenes
            if j > 0 and separator:
                parts.append(separator)

            # Scene title
            if show_titles:
                parts.append(f"## {scene.title}\n\n")

            parts.append(scene.content + "\n\n")

    return "".join(parts)

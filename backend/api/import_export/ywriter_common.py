"""Utilities shared between the yWriter importer and exporter."""

import re


# ── BBCode → Markdown (used by importer) ─────────────────────

def _bbcode_replace(open_tag, close_tag, md_delim):
    """Return a callable that converts a BBCode pair to markdown,
    trimming inner whitespace so delimiters stay valid."""
    pattern = re.compile(
        re.escape(open_tag) + r"(.*?)" + re.escape(close_tag),
        re.DOTALL,
    )

    def _replacer(m):
        inner = m.group(1)
        stripped = inner.strip()
        if not stripped:
            return inner
        leading = inner[: len(inner) - len(inner.lstrip())]
        trailing = inner[len(inner.rstrip()):]
        return f"{leading}{md_delim}{stripped}{md_delim}{trailing}"

    def apply(text):
        return pattern.sub(_replacer, text)

    return apply


_italic = _bbcode_replace("[i]", "[/i]", "*")
_bold = _bbcode_replace("[b]", "[/b]", "**")
_strike = _bbcode_replace("[s]", "[/s]", "~~")


def bbcode_to_markdown(text):
    """Convert yWriter BBCode formatting and line breaks to Markdown."""
    text = _italic(text)
    text = _bold(text)
    text = _strike(text)
    # Normalise existing double-newlines, then convert single → double
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", text)
    return text


# ── Markdown → BBCode (used by exporter) ─────────────────────

def markdown_to_bbcode(text):
    """Convert markdown inline formatting back to yWriter BBCode."""
    # Bold before italic (** before *)
    text = re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/b]", text, flags=re.DOTALL)
    text = re.sub(r"\*(.+?)\*", r"[i]\1[/i]", text, flags=re.DOTALL)
    text = re.sub(r"~~(.+?)~~", r"[s]\1[/s]", text, flags=re.DOTALL)
    # Double newlines → single newline (yWriter paragraph separator)
    text = re.sub(r"\n\n+", "\n", text)
    return text

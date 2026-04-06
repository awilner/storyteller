"""
Pandoc-based format exporters for the compile engine.

Each exporter is registered via ``register_exporter`` and converts an
assembled markdown string into the target format.  pypandoc is imported
lazily so the module loads even when Pandoc is not installed — only the
markdown passthrough exporter is guaranteed to work without it.
"""

import logging
import os
import tempfile

from . import register_exporter

logger = logging.getLogger(__name__)

try:
    import pypandoc

    _HAS_PYPANDOC = True
except ImportError:
    pypandoc = None  # type: ignore[assignment]
    _HAS_PYPANDOC = False
    logger.warning(
        "pypandoc is not installed — only the markdown exporter will be available."
    )


def _require_pypandoc():
    """Raise a clear error when pypandoc is missing."""
    if not _HAS_PYPANDOC:
        raise RuntimeError(
            "pypandoc is not installed. Install it with: pip install pypandoc"
        )


# ── Markdown (passthrough — no pypandoc needed) ─────────────


@register_exporter("markdown", "text/markdown", ".md")
def export_markdown(markdown, layout, project_title):
    """Return the assembled markdown as-is."""
    return markdown.encode("utf-8")


# ── DOCX ─────────────────────────────────────────────────────


@register_exporter(
    "docx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".docx",
)
def export_docx(markdown, layout, project_title):
    _require_pypandoc()
    extra_args = ["--standalone"]
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        pypandoc.convert_text(
            markdown,
            "docx",
            format="markdown",
            extra_args=extra_args,
            outputfile=tmp_path,
        )
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


# ── RTF ──────────────────────────────────────────────────────


@register_exporter("rtf", "application/rtf", ".rtf")
def export_rtf(markdown, layout, project_title):
    _require_pypandoc()
    extra_args = ["--standalone"]
    result = pypandoc.convert_text(
        markdown, "rtf", format="markdown", extra_args=extra_args
    )
    return result.encode("utf-8") if isinstance(result, str) else result


# ── PDF (via LaTeX) ──────────────────────────────────────────


@register_exporter("pdf", "application/pdf", ".pdf")
def export_pdf(markdown, layout, project_title):
    _require_pypandoc()
    margin_top = layout.get("margin_top", "2.54cm") if layout else "2.54cm"
    margin_bottom = layout.get("margin_bottom", "2.54cm") if layout else "2.54cm"
    margin_left = layout.get("margin_left", "3.18cm") if layout else "3.18cm"
    margin_right = layout.get("margin_right", "3.18cm") if layout else "3.18cm"
    geometry = (
        f"top={margin_top},"
        f"bottom={margin_bottom},"
        f"left={margin_left},"
        f"right={margin_right}"
    )
    extra_args = ["-V", f"geometry:{geometry}"]
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        pypandoc.convert_text(
            markdown,
            "pdf",
            format="markdown",
            extra_args=extra_args,
            outputfile=tmp_path,
        )
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


# ── LaTeX ────────────────────────────────────────────────────


@register_exporter("latex", "application/x-latex", ".tex")
def export_latex(markdown, layout, project_title):
    _require_pypandoc()
    extra_args = ["--standalone"]
    result = pypandoc.convert_text(
        markdown, "latex", format="markdown", extra_args=extra_args
    )
    return result.encode("utf-8") if isinstance(result, str) else result


# ── EPUB ─────────────────────────────────────────────────────


@register_exporter("epub", "application/epub+zip", ".epub")
def export_epub(markdown, layout, project_title):
    _require_pypandoc()
    extra_args = ["--standalone"]
    if project_title:
        extra_args.extend(["--metadata", f"title={project_title}"])
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        pypandoc.convert_text(
            markdown,
            "epub",
            format="markdown",
            extra_args=extra_args,
            outputfile=tmp_path,
        )
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


# ── MOBI (via EPUB + Calibre ebook-convert) ──────────────────


@register_exporter("mobi", "application/x-mobipocket-ebook", ".mobi")
def export_mobi(markdown, layout, project_title):
    # TODO: Implement MOBI via EPUB -> ebook-convert (Calibre).
    # For now, raise a clear error so callers know what's needed.
    raise NotImplementedError(
        "MOBI export requires Calibre's ebook-convert tool. "
        "Install Calibre and ensure ebook-convert is on the PATH."
    )

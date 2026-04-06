"""Compile engine — orchestrates tree traversal, markdown assembly, and export."""

from .exporters import get_exporter
from .markdown_assembler import assemble_markdown
from .tree_processor import collect_content


class CompileEngine:
    """Orchestrate the compile pipeline: collect → assemble → export."""

    def compile(
        self,
        project,
        root_folder_id,
        format_key,
        layout_settings=None,
        front_matter_folder_id=None,
        back_matter_folder_id=None,
    ):
        """
        Compile project content into a document.

        Returns (file_bytes, content_type, filename).
        """
        # 1. Resolve root folder
        root_folder = project.folders.filter(
            pk=root_folder_id, is_trash=False,
        ).first()
        if root_folder is None:
            raise ValueError("Root folder not found or is in trash.")

        # 2. Optionally resolve front/back matter folders
        front_matter_folder = None
        if front_matter_folder_id is not None:
            front_matter_folder = project.folders.filter(
                pk=front_matter_folder_id,
            ).first()

        back_matter_folder = None
        if back_matter_folder_id is not None:
            back_matter_folder = project.folders.filter(
                pk=back_matter_folder_id,
            ).first()

        # 3. Collect content from the tree
        chapters = collect_content(
            root_folder, front_matter_folder, back_matter_folder,
        )

        # 4. Validate there is content to compile
        if not any(ch.scenes for ch in chapters):
            raise ValueError("No content to compile")

        # 5. Assemble markdown
        settings = layout_settings or {}
        markdown = assemble_markdown(chapters, settings)

        # 6. Get exporter and produce output
        exporter = get_exporter(format_key)
        file_bytes = exporter["export"](markdown, settings, project.title)

        # 7. Build filename
        filename = f"{project.title}{exporter['extension']}"

        return (file_bytes, exporter["content_type"], filename)

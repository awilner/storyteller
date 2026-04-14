"""
Centralized UI translation strings served to the frontend.

The frontend fetches /api/i18n/strings/ and receives all translatable
UI labels in the active language (determined by Accept-Language header
or Django's locale middleware).
"""

from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def _get_ui_strings():
    """Return a flat dict of all frontend-facing translatable strings."""
    return {
        # Auth
        "auth.register": _("Register"),
        "auth.login": _("Log in"),
        "auth.logout": _("Log out"),
        "auth.username": _("Username"),
        "auth.password": _("Password"),
        "auth.oidc_sign_in": _("Sign in with OIDC"),
        "auth.already_have_account": _("Already have an account?"),
        "auth.no_account_yet": _("No account yet?"),

        # Dashboard
        "dashboard.title": _("Dashboard"),
        "dashboard.your_projects": _("Your Projects"),
        "dashboard.new_project": _("+ New Project"),
        "dashboard.cancel": _("Cancel"),
        "dashboard.project_title_placeholder": _("Project title"),
        "dashboard.description_placeholder": _("Description (optional)"),
        "dashboard.creating": _("Creating…"),
        "dashboard.create": _("Create"),
        "dashboard.loading_projects": _("Loading projects…"),
        "dashboard.no_projects": _("No projects yet. Create one to get started."),
        "dashboard.open": _("Open"),
        "dashboard.delete": _("Delete"),
        "dashboard.confirm_delete_project": _('Delete "%(title)s"? This will permanently remove the project and all its content.'),

        # OIDC
        "oidc.linked_identities": _("Linked OIDC Identities"),
        "oidc.no_identities": _("No OIDC identities linked."),
        "oidc.unlink": _("Unlink"),
        "oidc.link_account": _("Link OIDC Account"),
        "oidc.no_email": _("no email"),
        "oidc.error_title": _("OIDC Error"),
        "oidc.back_to_login": _("Back to login"),
        "oidc.completing_sign_in": _("Completing sign-in…"),
        "oidc.missing_auth_code": _("Missing authorization code from provider."),

        # Editor
        "editor.loading_project": _("Loading project…"),
        "editor.loading_file": _("Loading file…"),
        "editor.saving": _("Saving…"),
        "editor.save": _("Save"),
        "editor.select_file_placeholder": _("Select a file from the project tree to begin editing."),
        "editor.folder_empty": _("This folder has no texts."),
        "editor.draft_cache_warning": _("Draft cache unavailable — edits are only stored locally until you save."),
        "editor.dismiss_warning": _("Dismiss warning"),
        "editor.save_failed": _("Save failed: %(error)s"),
        "editor.words": _("words"),
        "editor.characters": _("characters"),

        # Loading
        "common.loading": _("Loading…"),

        # Project tree
        "tree.new_text": _("New text"),
        "tree.new": _("New"),
        "tree.new_subfolder": _("New subfolder"),
        "tree.new_folder": _("New folder"),
        "tree.new_character": _("New character"),
        "tree.new_location": _("New location"),
        "tree.new_note": _("New note"),
        "tree.rename": _("Rename"),
        "tree.duplicate": _("Duplicate"),
        "tree.copy_to_project": _("Copy to Project"),
        "tree.select_project": _("Select a project:"),
        "tree.delete_folder": _("Move to Trash"),
        "tree.delete_text": _("Move to Trash"),
        "tree.confirm_move_to_trash": _('Move "%(title)s" to Trash?'),
        "tree.folder_title_prompt": _("Folder title:"),
        "tree.text_title_prompt": _("Text title:"),
        "tree.confirm_delete_folder": _('Delete "%(title)s" and all its contents?'),
        "tree.confirm_delete_text": _('Delete "%(title)s"?'),

        # Icons
        "tree.change_icon": _("Change icon"),

        # Import
        "dashboard.import": _("Import"),
        "dashboard.importing": _("Importing…"),
        "dashboard.import_failed": _("Import failed: %(error)s"),
        "import.title": _("Import Project"),
        "import.format": _("Format"),
        "import.file": _("File"),
        "import.import_btn": _("Import"),

        # Properties panel
        "properties.folder_properties": _("Folder Properties"),
        "properties.text_properties": _("Text Properties"),
        "properties.title": _("Title"),
        "properties.description": _("Description"),
        "properties.notes": _("Notes"),
        "properties.tags": _("Tags (comma-separated)"),
        "properties.target_word_count": _("Target Word Count"),
        "properties.saving": _("Saving…"),
        "properties.update": _("Update Properties"),
        "properties.all_saved": _("All changes saved."),

        # Version history
        "versions.title": _("Version History"),

        # Import folder names
        "import.folder_manuscript": _("Manuscript"),
        "import.folder_characters": _("Characters"),
        "import.folder_locations": _("Locations"),
        "import.folder_items": _("Items"),
        "import.folder_notes": _("Notes"),

        # Top bar user menu
        "topbar.account": _("Account"),
        "topbar.settings": _("Settings"),
        "topbar.logout": _("Log out"),
        "topbar.export_scrivener": _("Export as Scrivener"),
        "topbar.export_ywriter": _("Export as yWriter"),
        "topbar.compile_manuscript": _("Compile Manuscript"),
        "topbar.project_settings": _("Project Settings"),

        # Account page
        "account.title": _("Account"),
        "account.change_password": _("Change Password"),
        "account.current_password": _("Current password"),
        "account.new_password": _("New password"),
        "account.confirm_password": _("Confirm new password"),
        "account.change_password_btn": _("Change Password"),
        "account.password_changed": _("Password changed successfully."),
        "account.passwords_mismatch": _("Passwords do not match."),
        "account.oidc_identities": _("Linked OIDC Identities"),

        # Settings page
        "settings.title": _("Settings"),
        "settings.placeholder": _("Settings will be available here in a future update."),
        "settings.default_font": _("Default Editor Font"),
        "settings.project_font": _("Editor Font"),
        "settings.use_default": _("Use default (from user settings)"),
        "settings.font_hint": _("This font is used in the text editor across all projects unless overridden in project settings."),
        "settings.font_preview": _("The quick brown fox jumps over the lazy dog."),
        "settings.auto_save_interval": _("Auto-save interval (seconds)"),
        "settings.auto_save_hint": _("How often unsaved changes are automatically saved. Set to 0 to disable. Default: 60 seconds."),
        "settings.auto_save_project_hint": _("Override the auto-save interval for this project. Leave empty to use the user default."),
        "versions.loading": _("Loading versions…"),
        "versions.no_versions": _("No versions yet."),
        "versions.chars": _("chars"),
        "versions.revert": _("Revert"),
        "versions.reverting": _("Reverting…"),
        "versions.confirm_revert": _("Revert to this version? Current content will be replaced."),
        "versions.loading_preview": _("Loading preview…"),
        "versions.revert_failed": _("Revert failed: %(error)s"),
        "versions.error_loading": _("Error loading version: %(error)s"),

        # Formatting toolbar
        "toolbar.bold": _("Bold"),
        "toolbar.italic": _("Italic"),
        "toolbar.blockquote": _("Blockquote"),
        "toolbar.heading1": _("Heading 1"),
        "toolbar.heading2": _("Heading 2"),
        "toolbar.heading3": _("Heading 3"),
        "toolbar.bullet_list": _("Bullet List"),
        "toolbar.ordered_list": _("Ordered List"),
        "toolbar.code": _("Code"),
        "toolbar.link": _("Link"),
        "toolbar.enter_url": _("Enter URL:"),

        # Trash
        "trash.title": _("Trash"),
        "trash.empty_trash": _("Empty Trash"),
        "trash.permanently_delete": _("Permanently Delete"),
        "trash.confirm_empty": _("Permanently delete all items in the trash? This cannot be undone."),
        "trash.confirm_permanent_delete": _('Permanently delete "%(title)s"? This cannot be undone.'),
        "trash.confirm_permanent_delete_folder": _('Permanently delete "%(title)s" and all its contents? This cannot be undone.'),

        # Compile
        "compile.title": _("Compile Manuscript"),
        "compile.compile_btn": _("Compile"),
        "compile.compiling": _("Compiling…"),
        "compile.root_folder": _("Compile Root"),
        "compile.format": _("Output Format"),
        "compile.layout": _("Layout"),
        "compile.default_layout": _("Default"),
        "compile.new_layout": _("New Layout"),
        "compile.layout_name": _("Layout Name"),
        "compile.front_matter": _("Front Matter"),
        "compile.back_matter": _("Back Matter"),
        "compile.enable_front_matter": _("Include front matter"),
        "compile.enable_back_matter": _("Include back matter"),
        "compile.no_content": _("No content to compile. Check your include/exclude settings."),
        "compile.error": _("Compile failed: %(error)s"),
        "compile.format_docx": _("Word Document (.docx)"),
        "compile.format_rtf": _("Rich Text Format (.rtf)"),
        "compile.format_markdown": _("Markdown (.md)"),
        "compile.format_pdf": _("PDF (.pdf)"),
        "compile.format_latex": _("LaTeX (.tex)"),
        "compile.format_epub": _("EPUB (.epub)"),
        "compile.format_mobi": _("MOBI (.mobi)"),
        "compile.heading_style": _("Chapter Heading Style"),
        "compile.heading_title": _("Title only"),
        "compile.heading_numbered": _("Numbered only"),
        "compile.heading_numbered_title": _("Number and title"),
        "compile.page_break": _("Page break before chapter"),
        "compile.blank_page": _("Blank page before chapter"),
        "compile.body_font": _("Body Font"),
        "compile.body_font_size": _("Body Font Size"),
        "compile.heading_font": _("Heading Font"),
        "compile.heading_font_size": _("Heading Font Size"),
        "compile.show_scene_titles": _("Show scene titles"),
        "compile.scene_separator": _("Scene Separator"),
        "compile.separator_horizontal_rule": _("Horizontal rule"),
        "compile.separator_three_asterisks": _("Three asterisks (* * *)"),
        "compile.separator_custom_text": _("Custom text"),
        "compile.separator_blank_line": _("Blank line"),
        "compile.separator_none": _("None"),
        "compile.custom_separator_text": _("Custom separator text"),
        "compile.margins": _("Page Margins"),
        "compile.margin_top": _("Top"),
        "compile.margin_bottom": _("Bottom"),
        "compile.margin_left": _("Left"),
        "compile.margin_right": _("Right"),

        # Metadata
        "properties.pov": _("POV Character"),
        "properties.label": _("Label"),
        "properties.status": _("Status"),
        "properties.colour": _("Colour"),
        "properties.none_option": _("— None —"),

        # Label manager
        "labels.title": _("Labels"),
        "labels.add": _("Add Label"),
        "labels.name": _("Name"),
        "labels.colour": _("Colour"),
        "labels.delete_warning": _('Delete "%(name)s"? It is assigned to %(count)s items.'),
        "labels.confirm_delete": _("Delete"),

        # Status manager
        "statuses.title": _("Statuses"),
        "statuses.add": _("Add Status"),
        "statuses.name": _("Name"),
        "statuses.colour": _("Colour"),
        "statuses.delete_warning": _('Delete "%(name)s"? It is assigned to %(count)s items.'),
        "statuses.confirm_delete": _("Delete"),

        # TopBar
        "topbar.manage_labels": _("Manage Labels"),
        "topbar.manage_statuses": _("Manage Statuses"),

        # Tree display settings
        "settings.general_tab": _("General"),
        "settings.project_tree_section": _("Project tree"),
        "settings.layouts_tab": _("Layouts"),
        "settings.tree_icon_bg": _("Icon background"),
        "settings.tree_text_colour": _("Text colour"),
        "settings.tree_text_bg": _("Text background"),
        "settings.source_nothing": _("Nothing"),
        "settings.colour_source_pov": _("POV Character"),
        "settings.colour_source_label": _("Label"),
        "settings.colour_source_status": _("Status"),

        # Progress tracking
        "progress.title": _("Progress Tracking"),
        "progress.manuscript_target": _("Manuscript Target (words)"),
        "progress.daily_target": _("Daily Target (words)"),
        "progress.session_target": _("Session Target (words)"),
        "progress.reset_session": _("Reset Session"),
        "progress.save_targets": _("Save Targets"),
        "progress.words_written_today": _("Words written today"),
        "progress.session_words": _("Session words"),
        "progress.insufficient_data": _("Not enough data for the graph yet. Keep writing!"),
        "progress.no_targets": _("No targets configured. Set targets above to track your progress."),
        "progress.back_to_editor": _("Back to Editor"),
        "topbar.progress_tracking": _("Progress Tracking"),
        "dashboard.manuscript_progress": _("Manuscript"),
        "dashboard.daily_progress": _("Today"),

        # Progress page charts
        "progress.word_count_over_time": _("Word Count Over Time"),
        "progress.daily_words": _("Daily Words"),
        "progress.session_history": _("Session History"),
        "progress.no_sessions": _("No sessions recorded yet."),
        "progress.words_label": _("words"),
        "progress.date_label": _("Date"),
        "progress.target_line": _("Target"),
        "progress.projected_completion": _("Projected completion"),

        # Status bar
        "status.manuscript": _("Manuscript"),
        "status.session": _("Session"),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def translations_view(request):
    """Return all UI strings translated to the active language."""
    return Response(_get_ui_strings())

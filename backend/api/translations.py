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
        "tree.new_subfolder": _("New subfolder"),
        "tree.new_folder": _("New folder"),
        "tree.rename": _("Rename"),
        "tree.delete_folder": _("Delete folder"),
        "tree.delete_text": _("Delete text"),
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
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def translations_view(request):
    """Return all UI strings translated to the active language."""
    return Response(_get_ui_strings())

# Re-export all views so urls.py can import from api.views
from .public import config_view, timezones_view, version_view  # noqa: F401
from .auth import (  # noqa: F401
    change_password_view,
    login_view,
    logout_view,
    me_view,
    register_view,
    user_settings_view,
)
from .oidc import (  # noqa: F401
    oidc_callback_view,
    oidc_link_view,
    oidc_login_view,
    oidc_unlink_view,
)
from .project import (  # noqa: F401
    copy_to_project_view,
    duplicate_folder_view,
    duplicate_text_view,
    empty_trash_view,
    file_cache_view,
    file_detail_view,
    file_version_detail_view,
    file_version_revert_view,
    file_versions_view,
    folder_create_view,
    folder_detail_view,
    project_detail_view,
    project_list_view,
    project_tree_view,
    reorder_view,
    text_create_view,
    text_detail_view,
)
from .import_export import (  # noqa: F401
    export_scrivener_view,
    export_ywriter_view,
    scrivener_import_view,
    ywriter_import_view,
)
from .label import label_detail_view, label_list_view  # noqa: F401
from .status import status_detail_view, status_list_view  # noqa: F401
from .layout import compile_layout_detail_view, compile_layout_list_view  # noqa: F401
from .compile import compile_view  # noqa: F401
from .progress import progress_view  # noqa: F401
from .sharing import (  # noqa: F401
    override_detail_view,
    override_list_view,
    search_users_view,
    share_detail_view,
    share_list_view,
    yjs_auth_view,
)

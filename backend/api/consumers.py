from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer

from .models import Project, ProjectShare


def has_project_access(user, project_id):
    """Return True if the user owns or has a share on the project."""
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return False

    if project.owner_id == user.id:
        return True

    return ProjectShare.objects.filter(project=project, user=user).exists()


class ProjectConsumer(JsonWebsocketConsumer):
    """
    WebSocket consumer for project-level notifications.

    Handles:
    - Connection auth via session cookie
    - Project access verification
    - permission_changed: forwards payload to client
    - user_access_revoked: notifies affected user and closes connection

    Close codes:
    - 4001: unauthenticated
    - 4003: unauthorized (no project access)
    """

    def connect(self):
        self.project_id = self.scope["url_route"]["kwargs"]["project_id"]
        self.user = self.scope.get("user")
        self.group_name = f"project_{self.project_id}"

        # Reject unauthenticated connections
        if not self.user or not self.user.is_authenticated:
            self.close(code=4001)
            return

        # Reject users without project access
        if not has_project_access(self.user, self.project_id):
            self.close(code=4003)
            return

        # Join the project channel group and accept
        async_to_sync(self.channel_layer.group_add)(
            self.group_name, self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        # Leave the project channel group
        if hasattr(self, "group_name"):
            async_to_sync(self.channel_layer.group_discard)(
                self.group_name, self.channel_name
            )

    def permission_changed(self, event):
        """Handle permission change broadcast from Sharing Service."""
        self.send_json(event["payload"])

    def user_access_revoked(self, event):
        """Handle access revocation — notify affected user and close."""
        if event["user_id"] == self.user.id:
            self.send_json(
                {
                    "type": "access_revoked",
                    "message": "Your access to this project has been revoked.",
                }
            )
            self.close()

    def project_event(self, event):
        """
        Generic handler for all project-level broadcasts.

        Any event sent via broadcast_project_event() arrives here and is
        forwarded to the client as-is.  The client dispatches on the
        ``type`` field inside the payload (e.g. "tree_changed",
        "settings_changed", "labels_changed", …).
        """
        self.send_json(event["payload"])

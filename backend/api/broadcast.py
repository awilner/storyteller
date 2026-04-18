"""
Centralised WebSocket broadcast for project-level events.

Usage:
    from ..broadcast import broadcast_project_event

    # After a tree mutation:
    broadcast_project_event(project_pk, "tree_changed", user_id=request.user.id)

    # After a project settings update:
    broadcast_project_event(project_pk, "settings_changed", user_id=request.user.id)

    # Any future event type — just pick a new name:
    broadcast_project_event(project_pk, "my_new_event", user_id=..., extra="data")

All keyword arguments beyond project_pk and event_type are included in the
payload sent to every connected client in the project's channel group.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def broadcast_project_event(project_pk, event_type, **kwargs):
    """
    Send an event to every WebSocket client connected to a project.

    Args:
        project_pk: The project ID whose channel group receives the message.
        event_type: A short identifier such as "tree_changed",
                    "settings_changed", "labels_changed", etc.
        **kwargs:   Arbitrary extra fields merged into the payload
                    (e.g. user_id, changed_fields, ...).
    """
    payload = {"type": event_type, **kwargs}
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"project_{project_pk}",
            {
                # Channels dispatches to the consumer method named here.
                "type": "project_event",
                "payload": payload,
            },
        )
    except Exception:
        logger.warning(
            "Failed to broadcast %s for project %s",
            event_type, project_pk, exc_info=True,
        )

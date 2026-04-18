# Feature: project-sharing — WebSocket unit tests for ProjectConsumer
"""
Unit tests for the ProjectConsumer WebSocket consumer.

**Validates: Requirements 6.1, 6.3, 11.1, 11.4**

Uses channels.testing.WebsocketCommunicator with InMemoryChannelLayer.
"""

import asyncio

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase

from api.models import Project, ProjectShare
from config.asgi import application


@database_sync_to_async
def create_user(username, password="testpass"):
    return User.objects.create_user(username=username, password=password)


@database_sync_to_async
def create_project(owner, title="Test Project"):
    return Project.objects.create(owner=owner, title=title)


@database_sync_to_async
def create_share(project, user, role="co-author"):
    return ProjectShare.objects.create(project=project, user=user, role=role)


def build_communicator(project_id, user=None):
    """Build a WebsocketCommunicator for the given project, optionally authenticated."""
    communicator = WebsocketCommunicator(
        application, f"/ws/projects/{project_id}/"
    )
    if user is not None:
        communicator.scope["user"] = user
    return communicator


class ProjectConsumerConnectionTests(TransactionTestCase):
    """Tests for WebSocket connection acceptance and rejection."""

    def setUp(self):
        # Run async setup synchronously
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_connection_accepted_for_authorized_user(self):
        """An authenticated user with project access can connect."""

        async def _test():
            owner = await create_user("ws_owner")
            project = await create_project(owner)

            communicator = build_communicator(project.pk, user=owner)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.disconnect()

        self.loop.run_until_complete(_test())

    def test_connection_accepted_for_collaborator(self):
        """An authenticated collaborator can connect."""

        async def _test():
            owner = await create_user("ws_owner2")
            collab = await create_user("ws_collab")
            project = await create_project(owner)
            await create_share(project, collab, role="read-only")

            communicator = build_communicator(project.pk, user=collab)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.disconnect()

        self.loop.run_until_complete(_test())

    def test_connection_rejected_for_unauthenticated_user(self):
        """An unauthenticated user is rejected with close code 4001."""

        async def _test():
            owner = await create_user("ws_owner3")
            project = await create_project(owner)

            # No user set on scope — simulates unauthenticated
            communicator = build_communicator(project.pk, user=None)
            connected, close_code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(close_code, 4001)

        self.loop.run_until_complete(_test())

    def test_connection_rejected_for_unauthorized_user(self):
        """A user without project access is rejected with close code 4003."""

        async def _test():
            owner = await create_user("ws_owner4")
            stranger = await create_user("ws_stranger")
            project = await create_project(owner)

            communicator = build_communicator(project.pk, user=stranger)
            connected, close_code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(close_code, 4003)

        self.loop.run_until_complete(_test())


class ProjectConsumerMessageTests(TransactionTestCase):
    """Tests for WebSocket message handling."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_permission_changed_forwarded_to_client(self):
        """A permission_changed group message is forwarded to the client."""

        async def _test():
            owner = await create_user("ws_owner5")
            project = await create_project(owner)

            communicator = build_communicator(project.pk, user=owner)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Send a permission_changed message to the project group
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f"project_{project.pk}",
                {
                    "type": "permission_changed",
                    "payload": {
                        "type": "permission_changed",
                        "user_id": 999,
                        "new_role": "read-only",
                    },
                },
            )

            response = await communicator.receive_json_from(timeout=2)
            self.assertEqual(response["type"], "permission_changed")
            self.assertEqual(response["user_id"], 999)
            self.assertEqual(response["new_role"], "read-only")

            await communicator.disconnect()

        self.loop.run_until_complete(_test())

    def test_user_access_revoked_sends_message_and_closes(self):
        """A user_access_revoked message notifies the affected user and closes the connection."""

        async def _test():
            owner = await create_user("ws_owner6")
            collab = await create_user("ws_collab2")
            project = await create_project(owner)
            await create_share(project, collab)

            communicator = build_communicator(project.pk, user=collab)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Send revocation targeting the collaborator
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f"project_{project.pk}",
                {
                    "type": "user_access_revoked",
                    "user_id": collab.id,
                },
            )

            response = await communicator.receive_json_from(timeout=2)
            self.assertEqual(response["type"], "access_revoked")
            self.assertIn("revoked", response["message"].lower())

            # Connection should be closed after the message
            output = await communicator.receive_output(timeout=2)
            self.assertEqual(output["type"], "websocket.close")

        self.loop.run_until_complete(_test())

    def test_user_access_revoked_ignores_other_users(self):
        """A user_access_revoked message targeting another user does not close the connection."""

        async def _test():
            owner = await create_user("ws_owner7")
            project = await create_project(owner)

            communicator = build_communicator(project.pk, user=owner)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Send revocation targeting a different user
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f"project_{project.pk}",
                {
                    "type": "user_access_revoked",
                    "user_id": 99999,  # not the owner
                },
            )

            # The owner should NOT receive any message (the handler
            # only sends when user_id matches)
            timed_out = False
            try:
                await communicator.receive_json_from(timeout=0.5)
            except asyncio.TimeoutError:
                timed_out = True

            self.assertTrue(timed_out, "Expected no message but received one")

            # Use a try/except to handle potential CancelledError on disconnect
            try:
                await communicator.disconnect()
            except asyncio.CancelledError:
                pass

        self.loop.run_until_complete(_test())


# ── Integration tests: WebSocket notification delivery ───────
# Validates: Requirements 6.1, 6.3


class WebSocketNotificationIntegrationTests(TransactionTestCase):
    """
    Integration tests verifying that sharing API actions trigger
    the correct WebSocket messages to connected clients.

    **Validates: Requirements 6.1, 6.3**
    """

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_role_change_sends_permission_changed_message(self):
        """Changing a collaborator's role broadcasts a permission_changed message."""

        async def _test():
            owner = await create_user("ws_int_owner1")
            collab = await create_user("ws_int_collab1")
            project = await create_project(owner)
            share = await create_share(project, collab, role="co-author")

            # Connect the collaborator to the WebSocket
            communicator = build_communicator(project.pk, user=collab)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Owner changes the collaborator's role via the sharing API
            @database_sync_to_async
            def change_role():
                from django.test import Client
                client = Client()
                client.force_login(owner)
                return client.patch(
                    f"/api/projects/{project.pk}/shares/{share.pk}/",
                    data={"role": "read-only"},
                    content_type="application/json",
                )

            resp = await change_role()
            self.assertEqual(resp.status_code, 200)

            # Collaborator should receive a permission_changed message
            msg = await communicator.receive_json_from(timeout=2)
            self.assertEqual(msg["type"], "permission_changed")
            self.assertEqual(msg["user_id"], collab.id)
            self.assertEqual(msg["new_role"], "read-only")

            await communicator.disconnect()

        self.loop.run_until_complete(_test())

    def test_revoke_sends_access_revoked_and_closes(self):
        """Revoking a collaborator's access sends access_revoked and closes the connection."""

        async def _test():
            owner = await create_user("ws_int_owner2")
            collab = await create_user("ws_int_collab2")
            project = await create_project(owner)
            share = await create_share(project, collab, role="co-author")

            # Connect the collaborator to the WebSocket
            communicator = build_communicator(project.pk, user=collab)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Owner revokes the collaborator's access via the sharing API
            @database_sync_to_async
            def revoke_access():
                from django.test import Client
                client = Client()
                client.force_login(owner)
                return client.delete(
                    f"/api/projects/{project.pk}/shares/{share.pk}/",
                )

            resp = await revoke_access()
            self.assertEqual(resp.status_code, 204)

            # Collaborator should receive an access_revoked message
            msg = await communicator.receive_json_from(timeout=2)
            self.assertEqual(msg["type"], "access_revoked")
            self.assertIn("revoked", msg["message"].lower())

            # Connection should be closed after the message
            output = await communicator.receive_output(timeout=2)
            self.assertEqual(output["type"], "websocket.close")

        self.loop.run_until_complete(_test())

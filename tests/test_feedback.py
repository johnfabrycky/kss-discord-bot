import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot.cogs.feedback import Feedback, FeedbackModal


def make_interaction(user_id=1234, display_name="Tester"):
    """Build a minimal Discord interaction double for unit tests."""
    user = SimpleNamespace(id=user_id, display_name=display_name)
    return SimpleNamespace(
        user=user,
        response=SimpleNamespace(
            defer=AsyncMock(),
            send_message=AsyncMock(),
            send_modal=AsyncMock(),
        ),
        followup=SimpleNamespace(send=AsyncMock()),
    )


class FeedbackModalTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests for feedback modal submission behavior."""

    async def test_on_submit_inserts_feedback_and_acknowledges_user(self):
        supabase = MagicMock()
        table = MagicMock()
        supabase.table.return_value = table
        table.insert.return_value = table
        table.execute.return_value = SimpleNamespace(data=[{"id": 1}])

        modal = FeedbackModal(supabase)
        modal.suggestion._value = "Please add more parking commands."
        interaction = make_interaction(display_name="Jordan")

        await modal.on_submit(interaction)

        supabase.table.assert_called_once_with("feedback")
        table.insert.assert_called_once_with(
            {
                "user_id": "1234",
                "user_name": "Jordan",
                "content": "Please add more parking commands.",
            }
        )
        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.followup.send.assert_awaited_once()


class FeedbackCogTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the feedback cog command surface."""

    @patch.dict(
        os.environ,
        {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_SERVICE_KEY": "test-key"},
        clear=False,
    )
    @patch("bot.cogs.feedback.create_client")
    async def test_feedback_command_opens_modal(self, create_client_mock):
        create_client_mock.return_value = MagicMock()
        cog = Feedback(bot=object())
        interaction = make_interaction()

        await Feedback.feedback.callback(cog, interaction)

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.await_args.args[0]
        self.assertIsInstance(modal, FeedbackModal)

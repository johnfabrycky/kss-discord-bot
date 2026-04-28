import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot.cogs import lates as lates_module
from bot.services.lates_service import LatesService


def make_query(result):
    """Create a fluent Supabase query mock returning the supplied data."""
    query = MagicMock()
    query.select.return_value = query
    query.delete.return_value = query
    query.insert.return_value = query
    query.eq.return_value = query
    query.in_.return_value = query
    query.execute = AsyncMock(return_value=SimpleNamespace(data=result))
    return query


def make_interaction(display_name="Tester", roles=None, user_id=1234):
    """Build a minimal interaction double with Discord-like response hooks."""
    user = SimpleNamespace(
        id=user_id,
        display_name=display_name,
        roles=roles or [],
    )
    return SimpleNamespace(
        user=user,
        response=SimpleNamespace(
            defer=AsyncMock(),
            send_message=AsyncMock(),
        ),
        followup=SimpleNamespace(send=AsyncMock()),
    )


class LatesCogTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests covering the late-plate cog command surface."""

    def setUp(self):
        patcher = patch("discord.ext.tasks.Loop.start")
        self.addCleanup(patcher.stop)
        patcher.start()
        self.cog = lates_module.Lates(bot=SimpleNamespace(supabase=MagicMock()))
        self.cog.service = MagicMock()
        self.cog.service.get_visible_lates = AsyncMock(return_value=[])
        self.cog.service.create_late = AsyncMock(return_value=(True, {}))
        self.cog.service.get_autocomplete_lates = AsyncMock(return_value=[])
        self.cog.service.clear_late = AsyncMock(return_value=False)
        self.cog.service.get_user_lates = AsyncMock(return_value=[])
        self.cog.service.perform_cleanup = AsyncMock(return_value=0)

    def test_get_user_house_returns_expected_house(self):
        self.cog.service.get_user_house.return_value = "koinonian"
        member = SimpleNamespace(roles=[SimpleNamespace(name="Koinonian"), SimpleNamespace(name="Resident")])

        self.assertEqual(self.cog._get_user_house(member), "koinonian")

    async def test_view_lates_rejects_user_without_house_role(self):
        self.cog.service.get_user_house.return_value = None
        interaction = make_interaction(roles=[SimpleNamespace(name="Guest")])

        await lates_module.Lates.view_lates.callback(self.cog, interaction, "Monday", "Lunch")

        # Now uses response.send_message instead of followup
        interaction.response.send_message.assert_awaited_once_with("❌ No house role detected.", ephemeral=True)

    async def test_view_lates_formats_visible_lates(self):
        self.cog.service.get_user_house.return_value = "koinonian"
        self.cog.service.get_visible_lates.return_value = [
            {"nickname": "Alice", "is_permanent": True},
            {"nickname": "Bob", "is_permanent": False},
        ]
        interaction = make_interaction(roles=[SimpleNamespace(name="Koinonian")])

        await lates_module.Lates.view_lates.callback(self.cog, interaction, "Monday", "Dinner")

        # Extracts embed from initial response, not followup
        embed = interaction.response.send_message.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "🍽️ Lates: Monday Dinner (2 total)")
        self.assertIn("**Alice**", embed.description)
        self.assertIn("**Bob**", embed.description)

    async def test_late_me_blocks_duplicate_requests(self):
        self.cog.service.get_user_house.return_value = "koinonian"
        self.cog.service.create_late.return_value = (False, "duplicate")
        interaction = make_interaction(roles=[SimpleNamespace(name="Koinonian")])

        await lates_module.Lates.late_me.callback(self.cog, interaction, "Monday", "Lunch", "False")

        # late_me still defers, so followup is correct
        interaction.followup.send.assert_awaited_once_with("❌ You already have a late for this meal.", ephemeral=True)

    async def test_late_me_inserts_new_request(self):
        self.cog.service.get_user_house.return_value = "suttonite"
        interaction = make_interaction(display_name="Casey", roles=[SimpleNamespace(name="Suttonite")], user_id=77)

        await lates_module.Lates.late_me.callback(self.cog, interaction, "Tuesday", "Dinner", "True")

        self.cog.service.create_late.assert_awaited_once_with(77, "Casey", "suttonite", "Tuesday", "Dinner", True)
        interaction.followup.send.assert_awaited_once_with(
            "✅ Late recorded for **Tuesday Dinner** (Suttonite).",
            ephemeral=True,
        )

    async def test_late_days_autocomplete_formats_existing_lates(self):
        self.cog.service.get_autocomplete_lates.return_value = [
            {"day_of_week": "Monday", "meal": "Lunch", "is_permanent": False},
            {"day_of_week": "Tuesday", "meal": "Dinner", "is_permanent": True},
        ]
        interaction = make_interaction()

        choices = await self.cog.late_days_autocomplete(interaction, "tue")

        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0].name, "Tuesday Dinner (permanent)")
        self.assertEqual(choices[0].value, "Tuesday|Dinner")

    async def test_clear_late_handles_invalid_selection(self):
        interaction = make_interaction()

        await lates_module.Lates.clear_late.callback(self.cog, interaction, "bad-selection")

        interaction.followup.send.assert_awaited_once_with("❌ Invalid selection.", ephemeral=True)

    async def test_my_lates_shows_active_requests(self):
        self.cog.service.get_user_lates.return_value = [
            {"day_of_week": "Wednesday", "meal": "Lunch", "is_permanent": False},
            {"day_of_week": "Thursday", "meal": "Dinner", "is_permanent": True},
        ]
        interaction = make_interaction()

        await lates_module.Lates.my_lates.callback(self.cog, interaction)

        # my_lates no longer defers, extract embed from response.send_message
        embed = interaction.response.send_message.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "📋 Your Registered Lates")
        self.assertIn("Wednesday Lunch", embed.description)
        self.assertIn("Thursday Dinner", embed.description)


class LatesServiceTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests for late-plate service rules and in-memory cache data access."""

    def setUp(self):
        self.supabase = MagicMock()
        self.service = LatesService(self.supabase)

    def test_get_user_house_returns_expected_house(self):
        member = SimpleNamespace(roles=[SimpleNamespace(name="Koinonian"), SimpleNamespace(name="Resident")])

        self.assertEqual(self.service.get_user_house(member), "koinonian")

    async def test_create_late_blocks_duplicate_request(self):
        # Seed the local cache to trigger the 0ms duplicate block
        self.service.lates_cache = [{"user_id": "1234", "day_of_week": "Monday", "meal": "Lunch"}]

        success, reason = await self.service.create_late(1234, "Tester", "koinonian", "Monday", "Lunch", False)

        self.assertFalse(success)
        self.assertEqual(reason, "duplicate")

    async def test_create_late_inserts_new_request_and_syncs_cache(self):
        # Empty cache means no duplicates found
        self.service.lates_cache = []
        insert_query = make_query([{"id": 2}])
        self.supabase.table.return_value = insert_query

        # Prevent the test from making a real DB call during the cache sync
        self.service.refresh_lates_cache = AsyncMock()

        success, payload = await self.service.create_late(77, "Casey", "suttonite", "Tuesday", "Dinner", True)

        self.assertTrue(success)
        self.assertEqual(payload["user_id"], "77")
        insert_query.insert.assert_called_once_with(
            {
                "user_id": "77",
                "nickname": "Casey",
                "role": "suttonite",
                "meal": "Dinner",
                "day_of_week": "Tuesday",
                "is_permanent": True,
            }
        )
        # Verify the service triggered a cache refresh after the successful write
        self.service.refresh_lates_cache.assert_awaited_once()

    async def test_get_visible_lates_uses_house_grouping(self):
        # Pre-populate the memory cache with test data
        self.service.lates_cache = [
            {"nickname": "Alice", "role": "koinonian", "day_of_week": "Monday", "meal": "Dinner", "is_permanent": True},
            {"nickname": "Bob", "role": "suttonite", "day_of_week": "Monday", "meal": "Dinner", "is_permanent": False},
            {"nickname": "Charlie", "role": "koinonian", "day_of_week": "Tuesday", "meal": "Dinner",
             "is_permanent": True}
        ]

        # Fetch koinonian lates for Monday Dinner
        rows = await self.service.get_visible_lates("koinonian", "Monday", "Dinner")

        # Should only find Alice (Bob is wrong house, Charlie is wrong day)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["nickname"], "Alice")
        self.assertTrue(rows[0]["is_permanent"])

import asyncio
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from bot.cogs import parking as parking_module
from bot.services.parking_service import ParkingService


def make_interaction(user_id=1234):
    """Build a minimal interaction double for parking command tests."""
    user = SimpleNamespace(id=user_id)
    return SimpleNamespace(
        user=user,
        response=SimpleNamespace(
            defer=AsyncMock(),
            send_message=AsyncMock(),
        ),
        followup=SimpleNamespace(send=AsyncMock()),
        channel=SimpleNamespace(send=AsyncMock()),
    )


def make_query(result):
    """Create a fluent Supabase query mock returning the supplied data."""
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.gt.return_value = query
    query.execute.return_value = SimpleNamespace(data=result)
    return query


class ParkingCogTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the active parking cog commands."""

    def setUp(self):
        service_patcher = patch("bot.cogs.parking.ParkingService")
        self.addCleanup(service_patcher.stop)
        self.service_cls = service_patcher.start()
        self.service = MagicMock()
        self.service.initialize_spots = AsyncMock()
        self.service.get_user_activity = AsyncMock()
        self.service.create_offers = AsyncMock()
        self.service.claim_resident_spot = AsyncMock()
        self.service.claim_staff_spot = AsyncMock()
        self.service.get_parking_data = AsyncMock()
        self.service.cancel_action = AsyncMock()
        self.service.get_guest_spot_list = AsyncMock()
        self.service.get_cancel_autocomplete_data = AsyncMock(return_value=([], []))
        self.service.parse_range = MagicMock()
        self.service.get_merged_availability = MagicMock()
        self.service_cls.return_value = self.service
        self.cog = parking_module.Parking(bot=object())

    async def test_initialize_parking_spots_delegates_to_service(self):
        await self.cog.initialize_parking_spots()
        self.service.initialize_spots.assert_awaited_once()

    async def test_offer_spot_rejects_invalid_spot(self):
        interaction = make_interaction()

        await parking_module.Parking.offer_spot.callback(
            self.cog,
            interaction,
            9999,
            SimpleNamespace(value=0),
            SimpleNamespace(value="1 PM"),
            SimpleNamespace(value=0),
            SimpleNamespace(value="3 PM"),
            1,
        )

        interaction.response.send_message.assert_awaited_once_with("❌ Spot 9999 is invalid.", ephemeral=True)

    async def test_offer_spot_creates_offer_for_valid_request(self):
        interaction = make_interaction()
        start = datetime(2026, 4, 6, 13, 0, tzinfo=parking_module.LOCAL_TZ)
        end = start + timedelta(hours=3)
        self.service.parse_range.return_value = (start, end, timedelta(hours=3))
        self.service.create_offers.return_value = (True, "created")

        await parking_module.Parking.offer_spot.callback(
            self.cog,
            interaction,
            10,
            SimpleNamespace(value=0),
            SimpleNamespace(value="1 PM"),
            SimpleNamespace(value=0),
            SimpleNamespace(value="4 PM"),
            2,
        )

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        self.service.create_offers.assert_awaited_once_with(1234, 10, start, end, 2)
        interaction.followup.send.assert_awaited_once_with("created", ephemeral=False)

    async def test_claim_spot_rejects_duration_outside_limits(self):
        interaction = make_interaction()
        start = datetime(2026, 4, 6, 13, 0, tzinfo=parking_module.LOCAL_TZ)
        end = start + timedelta(minutes=30)
        self.service.parse_range.return_value = (start, end, timedelta(minutes=30))

        await parking_module.Parking.claim_spot.callback(
            self.cog,
            interaction,
            SimpleNamespace(value=0),
            SimpleNamespace(value="1 PM"),
            SimpleNamespace(value=0),
            SimpleNamespace(value="2 PM"),
            10,
        )

        interaction.response.send_message.assert_awaited_once_with("❌ Must be between 2h and 7d.", ephemeral=True)

    async def test_claim_spot_autocomplete_filters_to_window_compatible_spots(self):
        start = datetime.fromisoformat("2026-04-02T16:00:00-05:00")
        end = datetime.fromisoformat("2026-04-05T12:00:00-05:00")
        self.service.parse_range.return_value = (start, end, timedelta(days=2, hours=20))
        guest_query = make_query([{"spot_number": 46}])
        offer_query = make_query(
            [
                {
                    "spot_number": 27,
                    "start_time": "2026-04-02T16:00:00-05:00",
                    "end_time": "2026-04-05T12:00:00-05:00",
                },
                {
                    "spot_number": 31,
                    "start_time": "2026-04-02T18:00:00-05:00",
                    "end_time": "2026-04-05T12:00:00-05:00",
                },
            ]
        )
        self.service.supabase = MagicMock()
        self.service.supabase.table.side_effect = [guest_query, offer_query]
        interaction = make_interaction()
        interaction.namespace = SimpleNamespace(
            start_day=SimpleNamespace(value=3),
            start_time=SimpleNamespace(value="4 PM"),
            end_day=SimpleNamespace(value=6),
            end_time=SimpleNamespace(value="12 PM"),
        )

        choices = await self.cog.claim_spot_autocomplete(interaction, "")

        self.assertEqual([choice.value for choice in choices], [27, 46])
        self.assertEqual([choice.name for choice in choices], ["Spot 27 (Offered)", "Spot 46 (Guest)"])

    async def test_my_parking_formats_offers_and_claims(self):
        interaction = make_interaction()
        self.service.get_user_activity.return_value = (
            [
                {
                    "spot_number": 10,
                    "start_time": "2026-04-06T13:00:00-05:00",
                    "end_time": "2026-04-06T15:00:00-05:00",
                }
            ],
            [
                {
                    "spot_number": 998,
                    "start_time": "2026-04-07T10:00:00-05:00",
                    "end_time": "2026-04-07T12:00:00-05:00",
                }
            ],
        )

        await parking_module.Parking.my_parking.callback(self.cog, interaction)

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "📋 My Parking Activity")
        self.assertIn("Spot 10", embed.fields[0].value)
        self.assertIn("Staff Spot", embed.fields[1].value)

    async def test_parking_status_builds_embed_from_service_data(self):
        interaction = make_interaction()
        tz = parking_module.LOCAL_TZ
        self.service.get_parking_data.return_value = (
            [
                {
                    "spot_number": 10,
                    "start_time": "2026-04-06T08:00:00-05:00",
                    "end_time": "2026-04-06T18:00:00-05:00",
                }
            ],
            [
                {
                    "spot_number": 998,
                    "start_time": "2026-04-06T10:00:00-05:00",
                    "end_time": "2026-04-06T12:00:00-05:00",
                }
            ],
            [46],
        )
        self.service.get_merged_availability.side_effect = [
            (
                "🟢 Available Now (until Mon 06PM)",
                [(datetime(2026, 4, 6, 8, 0, tzinfo=tz), datetime(2026, 4, 6, 18, 0, tzinfo=tz))],
            ),
            (
                "🟢 Available Now (until Thu 12PM)",
                [(datetime(2026, 4, 6, 8, 0, tzinfo=tz), datetime(2026, 4, 9, 12, 0, tzinfo=tz))],
            ),
        ]
        self.service.is_blackout.return_value = False

        await parking_module.Parking.parking_status.callback(self.cog, interaction)

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🚗 Parking Status (Next 7 Days)")
        self.assertIn("Spot 10", embed.fields[0].value)
        self.assertIn("Spot 46", embed.fields[0].value)
        self.assertIn("Free", embed.fields[1].value)

    async def test_cancel_rejects_manual_text(self):
        interaction = make_interaction()

        await parking_module.Parking.cancel.callback(self.cog, interaction, "manual-input")

        interaction.response.send_message.assert_awaited_once_with(
            "❌ Please select an option from the list.",
            ephemeral=True,
        )

    async def test_cancel_notifies_impacted_users(self):
        interaction = make_interaction()
        self.service.cancel_action.return_value = (True, "withdrawn", ["<@1>", "<@2>"])

        await parking_module.Parking.cancel.callback(self.cog, interaction, "sig_offer_test-id")

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.channel.send.assert_awaited_once_with("⚠️ **Attention <@1>, <@2>**: withdrawn")
        interaction.followup.send.assert_awaited_once_with("withdrawn", ephemeral=True)

    async def test_cancel_spot_autocomplete_formats_results(self):
        self.service.get_cancel_autocomplete_data.return_value = (
            [
                {
                    "id": "offer-1",
                    "spot_number": 27,
                    "start_time": "2026-04-02T16:00:00-05:00",
                    "end_time": "2026-04-05T12:00:00-05:00",
                }
            ],
            [
                {
                    "id": "claim-1",
                    "spot_number": 998,
                    "start_time": "2026-04-03T10:00:00-05:00",
                    "end_time": "2026-04-03T12:00:00-05:00",
                }
            ],
        )
        interaction = make_interaction()

        choices = await self.cog.cancel_spot_autocomplete(interaction, "")

        self.assertEqual(len(choices), 2)
        self.assertEqual(choices[0].value, "sig_offer_offer-1")
        self.assertEqual(choices[1].value, "sig_claim_claim-1")

    async def test_parking_help_sends_guide_embed(self):
        interaction = make_interaction()
        self.service.get_guest_spot_list.return_value = "46"

        await parking_module.Parking.parking_help.callback(self.cog, interaction)

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "🚗 Parking System Guide")
        self.assertIn("Guest Spot(s): 46", embed.fields[1].value)


class ParkingServiceTests(unittest.TestCase):
    """Unit tests for parking service time parsing and cancellation behavior."""

    @patch("bot.services.parking_service.create_client")
    @patch("bot.services.parking_service.datetime")
    def test_parse_range_treats_current_hour_as_this_week(self, datetime_mock, create_client_mock):
        create_client_mock.return_value = MagicMock()
        real_datetime = datetime
        current_time = real_datetime(2026, 4, 2, 16, 21, tzinfo=parking_module.LOCAL_TZ)
        datetime_mock.now.return_value = current_time
        datetime_mock.strptime.side_effect = lambda *args, **kwargs: real_datetime.strptime(*args, **kwargs)

        service = ParkingService()
        this_week_start, this_week_end, _ = service.parse_range(3, "4 PM", 6, "12 PM")

        self.assertEqual(this_week_start, real_datetime(2026, 4, 2, 16, 0, tzinfo=parking_module.LOCAL_TZ))
        self.assertEqual(this_week_end, real_datetime(2026, 4, 5, 12, 0, tzinfo=parking_module.LOCAL_TZ))

    @patch("bot.services.parking_service.create_client")
    @patch("bot.services.parking_service.datetime")
    def test_parse_range_treats_earlier_hour_as_next_week(self, datetime_mock, create_client_mock):
        create_client_mock.return_value = MagicMock()
        real_datetime = datetime
        current_time = real_datetime(2026, 4, 2, 16, 21, tzinfo=parking_module.LOCAL_TZ)
        datetime_mock.now.return_value = current_time
        datetime_mock.strptime.side_effect = lambda *args, **kwargs: real_datetime.strptime(*args, **kwargs)

        service = ParkingService()
        next_week_start, next_week_end, _ = service.parse_range(3, "3 PM", 6, "12 PM")

        self.assertEqual(next_week_start, real_datetime(2026, 4, 9, 15, 0, tzinfo=parking_module.LOCAL_TZ))
        self.assertEqual(next_week_end, real_datetime(2026, 4, 12, 12, 0, tzinfo=parking_module.LOCAL_TZ))

    @patch("bot.services.parking_service.create_client")
    def test_create_offers_returns_two_line_resolved_date_confirmation(self, create_client_mock):
        create_client_mock.return_value = MagicMock()
        service = ParkingService()
        service.supabase = MagicMock()
        table = MagicMock()
        service.supabase.table.return_value = table
        table.select.return_value = table
        table.eq.return_value = table
        table.lt.return_value = table
        table.gt.return_value = table
        table.insert.return_value = table
        table.execute.side_effect = [SimpleNamespace(data=[]), SimpleNamespace(data=[{"id": 1}])]

        start = datetime(2026, 4, 2, 16, 0, tzinfo=parking_module.LOCAL_TZ)
        end = datetime(2026, 4, 5, 12, 0, tzinfo=parking_module.LOCAL_TZ)

        success, message = asyncio.run(service.create_offers(1234, 27, start, end, 1))

        self.assertTrue(success)
        self.assertEqual(
            message,
            "📢 **Spot 27** listed\nStart: Thu Apr 2 at 4:00 PM\nEnd: Sun Apr 5 at 12:00 PM",
        )

    @patch("bot.services.parking_service.create_client")
    @patch("bot.services.parking_service.datetime")
    def test_cancel_action_removes_only_selected_offer_window(self, datetime_mock, create_client_mock):
        create_client_mock.return_value = MagicMock()
        real_datetime = datetime
        current_time = real_datetime(2026, 4, 1, 12, 0, tzinfo=parking_module.LOCAL_TZ)
        datetime_mock.now.return_value = current_time
        datetime_mock.strptime.side_effect = lambda *args, **kwargs: real_datetime.strptime(*args, **kwargs)
        datetime_mock.fromisoformat.side_effect = lambda *args, **kwargs: real_datetime.fromisoformat(*args, **kwargs)

        class FakeResponse:
            def __init__(self, data):
                self.data = data

        class FakeTable:
            def __init__(self, name, store):
                self.name = name
                self.store = store
                self.mode = "select"
                self.filters = []
                self.in_filters = []

            def select(self, *_args):
                self.mode = "select"
                return self

            def delete(self):
                self.mode = "delete"
                return self

            def eq(self, field, value):
                self.filters.append((field, value))
                return self

            def gt(self, field, value):
                self.filters.append((field, ("gt", value)))
                return self

            def execute(self):
                rows = list(self.store[self.name])
                for field, value in self.filters:
                    if isinstance(value, tuple) and value[0] == "gt":
                        rows = [row for row in rows if row[field] > value[1]]
                    else:
                        rows = [row for row in rows if row[field] == value]

                if self.mode == "delete":
                    ids_to_remove = {row["id"] for row in rows}
                    self.store[self.name] = [row for row in self.store[self.name] if row["id"] not in ids_to_remove]

                response = FakeResponse(rows)
                self.mode = "select"
                self.filters = []
                self.in_filters = []
                return response

        class FakeSupabase:
            def __init__(self, store):
                self.store = store

            def table(self, name):
                return FakeTable(name, self.store)

        store = {
            "parking_offers": [
                {
                    "id": "offer-1",
                    "spot_number": 27,
                    "owner_id": "1234",
                    "start_time": "2026-04-02T16:00:00-05:00",
                    "end_time": "2026-04-05T12:00:00-05:00",
                },
                {
                    "id": "offer-2",
                    "spot_number": 27,
                    "owner_id": "1234",
                    "start_time": "2026-04-02T18:00:00-05:00",
                    "end_time": "2026-04-05T12:00:00-05:00",
                },
                {
                    "id": "offer-3",
                    "spot_number": 27,
                    "owner_id": "1234",
                    "start_time": "2026-04-09T16:00:00-05:00",
                    "end_time": "2026-04-12T12:00:00-05:00",
                },
            ],
            "parking_reservations": [],
        }

        service = ParkingService()
        service.supabase = FakeSupabase(store)

        success, _message, pings = asyncio.run(service.cancel_action(1234, "offer", "offer-1"))

        self.assertTrue(success)
        self.assertEqual(pings, [])
        remaining_ids = [row["id"] for row in store["parking_offers"]]
        self.assertEqual(remaining_ids, ["offer-2", "offer-3"])

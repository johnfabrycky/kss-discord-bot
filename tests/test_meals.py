import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from bot.cogs import meals as meals_module
from bot.config import LOCAL_TZ
from bot.services.meals_service import MealsService
from bot.utils.meal_calendar import AcademicBreak, MealCalendarConfig


def make_interaction():
    """Create a minimal interaction object for meal command tests."""
    return SimpleNamespace(
        response=SimpleNamespace(
            send_message=AsyncMock(),
        )
    )


class MealsServiceTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the backend meal service logic and data processing."""

    def setUp(self):
        self.bot = SimpleNamespace(
            meal_cache=[
                {"week_number": 3, "day": "Monday", "meal_type": "lunch", "dish_name": "Tacos"},
                {"week_number": 3, "day": "Monday", "meal_type": "dinner", "dish_name": "Pasta"},
            ]
        )
        self.supabase = MagicMock()
        self.service = MealsService(self.bot, self.supabase)

        # Inject a mock config to test date calculations without calling Supabase
        self.service.calendar_config = MealCalendarConfig(
            semester_start=datetime(2026, 1, 19, tzinfo=LOCAL_TZ),
            rotation_length_weeks=4,
            breaks=[
                AcademicBreak(
                    name="Spring Break 🌸",
                    start=datetime(2026, 3, 14, tzinfo=LOCAL_TZ),
                    end=datetime(2026, 3, 22, 23, 59, tzinfo=LOCAL_TZ),
                    rotation_skip_days=7,
                )
            ],
        )

    def test_get_meal_from_cache_returns_matching_meal(self):
        meal = self.service.get_meal_from_cache(3, "Monday", "Lunch")
        self.assertEqual(meal, "Tacos")

    def test_get_active_break_name_returns_label_inside_break_window(self):
        current_date = datetime(2026, 3, 16, tzinfo=LOCAL_TZ)
        self.assertEqual(self.service.get_active_break_name(current_date), "Spring Break 🌸")

    def test_calculate_rotation_week_applies_configured_break_offset(self):
        current_date = datetime(2026, 3, 30, 12, 0, tzinfo=LOCAL_TZ)
        self.assertEqual(self.service.calculate_rotation_week(current_date), 2)

    async def test_refresh_calendar_config_loads_from_supabase(self):
        # Mock the chained Supabase response: table().select().eq().execute()
        mock_execute = self.supabase.table.return_value.select.return_value.eq.return_value.execute
        mock_execute.return_value = SimpleNamespace(
            data=[{
                "semester_start": "2026-01-19T00:00:00-06:00",
                "rotation_length_weeks": 4,
                "academic_breaks": [{
                    "name": "Spring Break 🌸",
                    "start_date": "2026-03-14T00:00:00-06:00",
                    "end_date": "2026-03-22T23:59:00-06:00",
                    "rotation_skip_days": 7
                }]
            }]
        )

        success = await self.service.refresh_calendar_config()

        self.assertTrue(success)
        self.assertEqual(self.service.calendar_config.rotation_length_weeks, 4)
        self.assertEqual(self.service.calendar_config.breaks[0].name, "Spring Break 🌸")


class MealsCogTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the Discord interaction layer of the meal schedule."""

    def setUp(self):
        # Initialize the cog with a mocked bot that has a mocked supabase client attached
        self.bot = SimpleNamespace(supabase=MagicMock())
        self.cog = meals_module.Meals(self.bot)

        # Replace the real service with a MagicMock to isolate testing to just the Cog UI
        self.cog.meals_service = MagicMock(spec=MealsService)
        self.cog.meals_service.calendar_config = True  # Ensure the service looks "loaded"

    @patch("bot.cogs.meals.datetime")
    async def test_today_returns_unavailable_if_config_missing(self, datetime_mock):
        # Simulate the service failing to load the configuration
        self.cog.meals_service.calendar_config = None
        interaction = make_interaction()

        await meals_module.Meals.today.callback(self.cog, interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "⚠️ Meal configuration is currently loading or unavailable. Please try again later.",
            ephemeral=True,
        )

    @patch("bot.cogs.meals.datetime")
    async def test_today_returns_break_message_during_break(self, datetime_mock):
        datetime_mock.now.return_value = datetime(2026, 3, 16, 12, 0, tzinfo=LOCAL_TZ)
        self.cog.meals_service.get_active_break_name.return_value = "Spring Break 🌸"
        interaction = make_interaction()

        await meals_module.Meals.today.callback(self.cog, interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "🏝️ **Enjoy your Spring Break 🌸!** No meals scheduled.",
            ephemeral=True,
        )

    @patch("bot.cogs.meals.datetime")
    async def test_today_builds_embed_from_service(self, datetime_mock):
        now = datetime(2026, 2, 2, 12, 0, tzinfo=LOCAL_TZ)
        datetime_mock.now.return_value = now
        datetime_mock.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # Configure the mock service to return standard non-break data
        self.cog.meals_service.get_active_break_name.return_value = None
        self.cog.meals_service.calculate_rotation_week.return_value = 3
        self.cog.meals_service.get_meal_from_cache.side_effect = (lambda week, day,
                                                                         meal: "Tacos" if meal == "lunch" else "Pasta")

        interaction = make_interaction()

        await meals_module.Meals.today.callback(self.cog, interaction)

        interaction.response.send_message.assert_awaited_once()
        embed = interaction.response.send_message.await_args.kwargs["embed"]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🍴 Menu for Monday")
        self.assertEqual(embed.description, "**Rotation: Week 3**")
        self.assertEqual(embed.fields[0].value, "Tacos")
        self.assertEqual(embed.fields[1].value, "Pasta")

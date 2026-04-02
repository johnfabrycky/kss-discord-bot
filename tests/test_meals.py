import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from cogs import meals as meals_module


def make_interaction():
    """Create a minimal interaction object for meal command tests."""
    return SimpleNamespace(
        response=SimpleNamespace(
            send_message=AsyncMock(),
        )
    )


class MealsCogTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the meal schedule cog."""

    def setUp(self):
        bot = SimpleNamespace(
            meal_cache=[
                {"week_number": 3, "day": "Monday", "meal_type": "lunch", "dish_name": "Tacos"},
                {"week_number": 3, "day": "Monday", "meal_type": "dinner", "dish_name": "Pasta"},
            ]
        )
        self.cog = meals_module.Meals(bot)

    def test_get_meal_from_cache_returns_matching_meal(self):
        meal = self.cog.get_meal_from_cache(3, "Monday", "Lunch")

        self.assertEqual(meal, "Tacos")

    def test_is_uiuc_break_returns_break_label_inside_break_window(self):
        current_date = datetime(2026, 3, 16, tzinfo=meals_module.local_tz)

        self.assertEqual(self.cog.is_uiuc_break(current_date), "Spring Break 🌸")

    @patch("cogs.meals.datetime")
    async def test_today_returns_break_message_during_break(self, datetime_mock):
        datetime_mock.now.return_value = datetime(2026, 3, 16, 12, 0, tzinfo=meals_module.local_tz)
        datetime_mock.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        interaction = make_interaction()

        await meals_module.Meals.today.callback(self.cog, interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "🏝️ **Enjoy your Spring Break 🌸!** No meals scheduled.",
            ephemeral=True,
        )

    @patch("cogs.meals.datetime")
    async def test_today_builds_embed_from_cached_meals(self, datetime_mock):
        datetime_mock.now.return_value = datetime(2026, 2, 2, 12, 0, tzinfo=meals_module.local_tz)
        datetime_mock.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        interaction = make_interaction()

        await meals_module.Meals.today.callback(self.cog, interaction)

        interaction.response.send_message.assert_awaited_once()
        embed = interaction.response.send_message.await_args.kwargs["embed"]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🍴 Menu for Monday")
        self.assertEqual(embed.fields[0].value, "Tacos")
        self.assertEqual(embed.fields[1].value, "Pasta")

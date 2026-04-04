from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import MEAL_CALENDAR
from bot.utils.constants import LOCAL_TZ


class Meals(commands.Cog):
    """Meal schedule commands backed by the bot's cached menu data."""

    def __init__(self, bot):
        """Store the bot reference used to access cached meals."""
        self.bot = bot

    def get_meal_from_cache(self, week, day, meal_type):
        """Filters the cached Supabase data for the specific meal."""
        meal_type = meal_type.lower()

        for meal in getattr(self.bot, "meal_cache", []):
            if (
                meal["week_number"] == week
                and meal["day"].strip() == day
                and meal["meal_type"] == meal_type
            ):
                return meal["dish_name"]

        return "No meal scheduled"

    def is_uiuc_break(self, current_date):
        """Return the current academic break label, if one is configured."""
        for break_window in MEAL_CALENDAR.breaks:
            if break_window.start <= current_date <= break_window.end:
                return break_window.name
        return None

    def get_rotation_week(self, current_date):
        """Return the active meal rotation week for the configured calendar."""
        days_since_start = (current_date - MEAL_CALENDAR.semester_start).days
        for break_window in MEAL_CALENDAR.breaks:
            if current_date > break_window.end:
                days_since_start -= break_window.rotation_skip_days

        return ((max(0, days_since_start) // 7) % MEAL_CALENDAR.rotation_length_weeks) + 1

    @app_commands.command(name="today", description="Get today's menu")
    async def today(self, interaction: discord.Interaction):
        """Show the current day's lunch and dinner from the rotating meal schedule."""
        now = datetime.now(LOCAL_TZ)

        break_name = self.is_uiuc_break(now)
        if break_name:
            return await interaction.response.send_message(
                f"🏝️ **Enjoy your {break_name}!** No meals scheduled.", ephemeral=True
            )

        current_week = self.get_rotation_week(now)
        day_name = now.strftime("%A")

        lunch = self.get_meal_from_cache(current_week, day_name, "lunch")
        dinner = self.get_meal_from_cache(current_week, day_name, "dinner")

        embed = discord.Embed(
            title=f"🍴 Menu for {day_name}",
            description=f"**Rotation: Week {current_week}**",
            color=discord.Color.gold(),
        )
        embed.add_field(name="☀️ Lunch", value=lunch, inline=False)
        embed.add_field(name="🌙 Dinner", value=dinner, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Register the meals cog with the bot."""
    await bot.add_cog(Meals(bot))

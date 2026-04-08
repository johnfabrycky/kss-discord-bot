from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import LOCAL_TZ
from bot.services.meals_service import MealsService


class Meals(commands.Cog):
    """Meal schedule commands backed by the bot's cached menu data."""

    def __init__(self, bot):
        self.bot = bot
        self.meals_service = MealsService(bot, bot.supabase)

    async def cog_load(self):
        """Fetch the active calendar configuration when the cog loads."""
        await self.meals_service.refresh_calendar_config()

    @app_commands.command(name="today", description="Get today's menu")
    @app_commands.checks.cooldown(1, 5.0, key=lambda interaction: interaction.user.id)
    async def today(self, interaction: discord.Interaction):
        """Show the current day's lunch and dinner from the rotating meal schedule."""

        # Check if the service has successfully loaded the config
        if not self.meals_service.calendar_config:
            return await interaction.response.send_message(
                "⚠️ Meal configuration is currently loading or unavailable. Please try again later.",
                ephemeral=True
            )

        now = datetime.now(LOCAL_TZ)

        # 1. Ask the service if we are on break
        break_name = self.meals_service.get_active_break_name(now)
        if break_name:
            return await interaction.response.send_message(
                f"🏝️ **Enjoy your {break_name}!** No meals scheduled.",
                ephemeral=True
            )

        # 2. Ask the service for the week and fetch the meals
        current_week = self.meals_service.calculate_rotation_week(now)
        day_name = now.strftime("%A")

        lunch = self.meals_service.get_meal_from_cache(current_week, day_name, "lunch")
        dinner = self.meals_service.get_meal_from_cache(current_week, day_name, "dinner")

        # 3. Handle the Discord UI
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

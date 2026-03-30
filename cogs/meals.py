from datetime import datetime

import discord
import pytz
from discord import app_commands
from discord.ext import commands

local_tz = pytz.timezone('America/Chicago')


class Meals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_meal_from_cache(self, week, day, meal_type):
        """Filters the cached Supabase data for the specific meal."""
        # Standardize casing to match your transform logic
        meal_type = meal_type.lower()

        # Search the list of dictionaries cached in on_ready
        for meal in getattr(self.bot, 'meal_cache', []):
            if (meal['week_number'] == week and
                    meal['day'].strip() == day and
                    meal['meal_type'] == meal_type):
                return meal['dish_name']

        return "No meal scheduled"

    def is_uiuc_break(self, current_date):
        # Spring Break 2026: March 14 to March 22
        spring_break_start = datetime(2026, 3, 14, tzinfo=local_tz)
        spring_break_end = datetime(2026, 3, 22, 23, 59, tzinfo=local_tz)
        if spring_break_start <= current_date <= spring_break_end:
            return "Spring Break 🌸"
        return None

    @app_commands.command(name="today", description="Get today's menu")
    async def today(self, interaction: discord.Interaction):
        now = datetime.now(local_tz)

        # 1. Check for breaks
        break_name = self.is_uiuc_break(now)
        if break_name:
            return await interaction.response.send_message(
                f"🏝️ **Enjoy your {break_name}!** No meals scheduled.", ephemeral=True
            )

        # 2. Calculate Week and Day
        semester_start = datetime(2026, 1, 19, tzinfo=local_tz)
        days_since_start = (now - semester_start).days
        # Account for spring break gap in week rotation
        if now > datetime(2026, 3, 22, tzinfo=local_tz):
            days_since_start -= 7

        current_week = ((max(0, days_since_start) // 7) % 4) + 1
        day_name = now.strftime("%A")

        # 3. Fetch from Cache
        lunch = self.get_meal_from_cache(current_week, day_name, "lunch")
        dinner = self.get_meal_from_cache(current_week, day_name, "dinner")

        # 4. Send Embed
        embed = discord.Embed(
            title=f"🍴 Menu for {day_name}",
            description=f"**Rotation: Week {current_week}**",
            color=discord.Color.gold()
        )
        embed.add_field(name="☀️ Lunch", value=lunch, inline=False)
        embed.add_field(name="🌙 Dinner", value=dinner, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Meals(bot))

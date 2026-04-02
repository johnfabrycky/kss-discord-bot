from datetime import datetime, timedelta

import discord
import pytz
from discord import app_commands
from discord.ext import commands

local_tz = pytz.timezone('America/Chicago')


class Movies(commands.Cog):
    """Track ad-hoc movie sessions announced in Discord."""

    def __init__(self, bot):
        """Initialize in-memory storage for active movie sessions."""
        self.bot = bot
        self.movie_sessions = {}

    @app_commands.command(name="watch", description="Record a movie session for others to see")
    @app_commands.describe(
        duration_mins="How long the movie is in minutes",
        location="Where you are watching (e.g. Living Room)",
        movie_name="The name of the film",
        start_time="Optional: HH:MM format (24hr). Leave blank to start now."
    )
    async def watch(self, interaction: discord.Interaction, duration_mins: int, location: str, movie_name: str,
                    start_time: str = None):
        """Record a movie session and announce where it is playing."""
        if start_time is None:
            start_dt = datetime.now(local_tz)
        else:
            try:
                input_time = datetime.strptime(start_time, "%H:%M").time()
                start_dt = datetime.now(local_tz).replace(
                    hour=input_time.hour, minute=input_time.minute, second=0, microsecond=0
                )
            except ValueError:
                # We use ephemeral=True here so the error message doesn't clutter the chat
                return await interaction.response.send_message("❌ Invalid time format! Please use HH:MM (e.g., 14:30).",
                                                               ephemeral=True)

        end_dt = start_dt + timedelta(minutes=duration_mins)
        self.movie_sessions[movie_name.lower()] = {
            "location": location,
            "end_time": end_dt,
            "original_name": movie_name
        }

        start_str = start_dt.strftime("%I:%M %p")

        # ephemeral=False (default) so everyone sees the announcement!
        await interaction.response.send_message(
            f"🎬 **{movie_name}** recorded! Starting at **{start_str}** in **{location}**.",
            ephemeral=False
        )

    @app_commands.command(name="where", description="Check what movies are currently playing")
    async def where(self, interaction: discord.Interaction):
        """List movie sessions that have not yet expired."""
        now = datetime.now(local_tz)
        active_movies = []

        for name, data in list(self.movie_sessions.items()):
            if now < data["end_time"]:
                active_movies.append(f"• **{data['original_name']}** is at **{data['location']}**")
            else:
                del self.movie_sessions[name]

        response = "🍿 **Current Movies Playing:**\n" + "\n".join(
            active_movies) if active_movies else "Currently, no movies are being watched."
        await interaction.response.send_message(content=response, ephemeral=True)


async def setup(bot):
    """Register the movies cog with the bot."""
    await bot.add_cog(Movies(bot))

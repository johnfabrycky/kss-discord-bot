import os

import discord
from discord import app_commands, ui
from discord.ext import commands
from supabase import create_client, Client


# --- MODAL FOR FEEDBACK ---
class FeedbackModal(ui.Modal, title='Improve Felipe'):
    """Modal used to collect free-form feedback and persist it to Supabase."""
    # A multi-line text input
    suggestion = ui.TextInput(
        label='What should we add or change?',
        style=discord.TextStyle.paragraph,
        placeholder='e.g. Add a way to trade parking spots, or fix the meal schedule formatting...',
        required=True,
        max_length=1000,
    )

    def __init__(self, supabase_client: Client):
        """Store the Supabase client used to save submitted feedback."""
        super().__init__()
        self.supabase = supabase_client

    async def on_submit(self, interaction: discord.Interaction):
        """Persist the submitted suggestion and acknowledge the user privately."""
        # Prepare data for Supabase
        payload = {
            "user_id": str(interaction.user.id),
            "user_name": interaction.user.display_name,
            "content": self.suggestion.value
        }

        # Insert into database
        self.supabase.table("feedback").insert(payload).execute()

        await interaction.response.send_message(
            f"Thanks {interaction.user.display_name}! Your feedback has been sent to the Gerald dev team. 🚀",
            ephemeral=True
        )


# --- THE COG ---
class Feedback(commands.Cog):
    """Slash command group for collecting user feedback."""

    def __init__(self, bot):
        """Initialize the cog and connect to Supabase."""
        self.bot = bot
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        self.supabase: Client = create_client(url, key)

    @app_commands.command(name="feedback",
                          description="Submit feedback to the Felipe dev team (hit enter, then a submission box will appear)")
    async def feedback(self, interaction: discord.Interaction):
        """Open the feedback modal for the requesting user."""
        # Open the popup modal
        await interaction.response.send_modal(FeedbackModal(self.supabase))


async def setup(bot):
    """Register the feedback cog with the bot."""
    await bot.add_cog(Feedback(bot))

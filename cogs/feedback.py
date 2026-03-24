import discord
from discord.ext import commands
from discord import app_commands, ui
from supabase import create_client, Client
import os

# --- MODAL FOR FEEDBACK ---
class FeedbackModal(ui.Modal, title='Improve Felipe'):
    # A multi-line text input
    suggestion = ui.TextInput(
        label='What should we add or change?',
        style=discord.TextStyle.paragraph,
        placeholder='e.g. Add a way to trade parking spots, or fix the meal schedule formatting...',
        required=True,
        max_length=1000,
    )

    def __init__(self, supabase_client: Client):
        super().__init__()
        self.supabase = supabase_client

    async def on_submit(self, interaction: discord.Interaction):
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
    def __init__(self, bot):
        self.bot = bot
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        self.supabase: Client = create_client(url, key)

    @app_commands.command(name="feedback", description="Submit a suggestion to improve the bot")
    async def feedback(self, interaction: discord.Interaction):
        # Open the popup modal
        await interaction.response.send_modal(FeedbackModal(self.supabase))

async def setup(bot):
    await bot.add_cog(Feedback(bot))
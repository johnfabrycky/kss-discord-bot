"""Bot application setup, command registration, and startup hooks."""

import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from supabase import create_client

from bot.config import GUILD_ID, INITIAL_EXTENSIONS, MY_GUILD
from bot.utils.discord_http_logging import install_discord_http_rate_limit_logging

load_dotenv()
logger = logging.getLogger(__name__)
install_discord_http_rate_limit_logging()


class Bot(commands.Bot):
    """Main Discord bot class responsible for startup, sync, and shared caches."""

    def __init__(self):
        """Configure intents, create shared clients, and initialize local caches."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        self.supabase = create_client(url, key)
        self.meal_cache = []

    async def setup_hook(self):
        """Load configured extensions and sync slash commands to the development guild."""
        for extension in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(extension)
                print(f"✅ Loaded {extension}")
            except Exception as e:
                print(f"❌ Failed to load {extension}: {e}")

        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"🌲 Tree synced to guild {GUILD_ID}")

    async def on_ready(self):
        """Cache startup data, initialize parking, and publish bot presence."""
        await self.change_presence(
            activity=discord.CustomActivity(name="Custom Status", state="Enter /help to see what I can do!")
        )

        try:
            response = self.supabase.table("meals").select("*").execute()
            self.meal_cache = response.data
            print(f"✅ Cached {len(self.meal_cache)} meals")
        except Exception as e:
            print(f"❌ Failed to cache meals: {e}")

        parking_cog = self.get_cog("Parking")
        if parking_cog:
            await parking_cog.initialize_parking_spots()
            print("✅ Parking spots initialized")

        print(f"🚀 {self.user.name} is online in Champaign!")


bot = Bot()


@bot.command()
@commands.is_owner()
async def sync_global(ctx):
    """Sync global slash commands for production-style rollout."""
    await bot.tree.sync()
    await ctx.send("🌍 Global slash commands synced (may take 1 hour).")


@bot.command()
@commands.is_owner()
async def clear_ghosts(ctx):
    """Clear globally registered commands to remove stale slash-command entries."""
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    await ctx.send("👻 Ghost commands cleared! The duplicate should vanish shortly.")


@bot.tree.command(name="help", description="List all available commands and bot info")
async def help_command(interaction: discord.Interaction):
    """Show a categorized summary of the bot's currently exposed commands."""
    embed = discord.Embed(
        title="🤖 Bot Command Center",
        description="I manage parking, late plates, meal schedules, and feedback!",
        color=discord.Color.green(),
    )

    sections = {
        "🚗 Parking": "`/offer_spot`, `/claim_spot`, `/claim_staff`, `/parking_status`, `/cancel`, `/parking_help`",
        "🍱 Lates": "`/late_me`, `/view_lates`, `/my_lates`, `/clear_late`",
        # "🎬 Movies": "`/watch`, `/where`",
        "🍽️ Meals": "`/today`",
        # "⚖️ Shifts": "`/offer_shift`, `/view_market`, `/claim_shift`, `/swap_shift`, /my_shifts`, `/cancel_shift`",
        "📝 Feedback": "`/feedback`",
    }

    for name, value in sections.items():
        embed.add_field(name=name, value=value, inline=False)

    embed.set_footer(text="Pro-tip: Slash commands show you exactly what to type as you go!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

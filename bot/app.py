"""Bot application setup, command registration, and startup hooks."""

import logging
import math
import os
import time

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from supabase import create_async_client, AsyncClient

from bot.config import GUILD_ID, EXTENSIONS, MY_GUILD
from bot.utils.database import ensure_tables_exist
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

        self.supabase: AsyncClient | None = None
        self.meal_cache = []
        self.sync_on_startup = os.environ.get("SYNC_ON_STARTUP", "").lower() == "true"
        self._ready_once = False

    async def setup_hook(self):
        """Load configured extensions and sync slash commands to the development guild."""
        db_url = os.environ.get("SUPABASE_DB_URL")
        if db_url:
            print("Verifying database schema...")
            await ensure_tables_exist(db_url)
        else:
            print("WARNING: SUPABASE_DB_URL not found. Skipping schema creation.")

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        self.supabase = await create_async_client(url, key)
        print("Async Supabase client initialized")

        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                print(f"Loaded {extension}")
            except Exception as e:
                print(f"Failed to load {extension}: {e}")

        if self.sync_on_startup:
            self.tree.copy_global_to(guild=MY_GUILD)
            await self.tree.sync(guild=MY_GUILD)
            print(f"Tree synced to guild {GUILD_ID}")
        else:
            print("Skipping slash-command sync on startup")

    async def on_ready(self):
        """Cache startup data, initialize parking, and publish bot presence."""
        if self._ready_once:
            print(f"Reconnected as {self.user.name}")
            return

        self._ready_once = True
        await self.change_presence(
            activity=discord.CustomActivity(name="Custom Status", state="Enter /help to see what I can do!")
        )

        try:
            response = await self.supabase.table("meals").select("*").execute()
            self.meal_cache = response.data
            print(f"Cached {len(self.meal_cache)} meals")
        except Exception as e:
            print(f"Failed to cache meals: {e}")

        parking_cog = self.get_cog("Parking")
        if parking_cog:
            await parking_cog.initialize_parking_spots()
            print("Parking spots initialized")

        print(f"{self.user.name} is online in Champaign!")


bot = Bot()


async def _send_ephemeral_app_error(interaction: discord.Interaction, message: str):
    """Send an ephemeral app-command error when the interaction is still usable."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        logger.warning(
            "Failed to send app command error response",
            extra={
                "command": getattr(getattr(interaction, "command", None), "name", None),
                "user_id": str(interaction.user.id),
            },
        )


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle slash-command cooldowns and Discord-side 429 failures consistently."""
    command_name = getattr(getattr(interaction, "command", None), "name", "unknown")
    user_id = str(interaction.user.id)

    if isinstance(error, app_commands.CommandOnCooldown):
        retry_after = max(1, math.ceil(error.retry_after))
        logger.info(
            "App command hit cooldown",
            extra={"command": command_name, "user_id": user_id, "retry_after_seconds": retry_after},
        )
        await _send_ephemeral_app_error(
            interaction,
            f"Please wait {retry_after}s before using `/{command_name}` again.",
        )
        return

    original = getattr(error, "original", error)
    if isinstance(original, discord.HTTPException) and original.status == 429:
        logger.warning(
            "Discord rate limited app command response",
            extra={
                "command": command_name,
                "user_id": user_id,
                "status": original.status,
                "discord_error_code": original.code,
            },
        )
        await _send_ephemeral_app_error(
            interaction,
            "Discord is rate limiting the bot right now. Please wait a few seconds and try again.",
        )
        return

    logger.error(
        "Unhandled app command error",
        extra={"command": command_name, "user_id": user_id},
        exc_info=(type(original), original, original.__traceback__),
    )
    await _send_ephemeral_app_error(
        interaction,
        "Something went wrong while running that command.",
    )


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


@bot.command(name="audit")
@commands.is_owner()  # Keeps this tool restricted to you
async def audit_latency(ctx):
    """Measures Gateway, REST, and Database latency in one sequence."""

    # 1. Gateway Latency (Heartbeat)
    gateway_lat = round(bot.latency * 1000)

    # 2. Database Latency (Supabase)
    # Crucial change: Using your bot's async supabase client
    db_start = time.perf_counter()
    try:
        if bot.supabase is None:
            raise ValueError("Supabase client not initialized")

        await bot.supabase.table("parking_offers").select("*").limit(1).execute()
        db_end = time.perf_counter()
        db_lat = round((db_end - db_start) * 1000)
        db_status = f"{db_lat}ms"
    except Exception as e:
        db_status = f"Error: {type(e).__name__}"
        db_lat = 0

    # 3. REST API Latency (Round-trip)
    rest_start = time.perf_counter()
    msg = await ctx.send("⚙️ Auditing system performance...")
    rest_end = time.perf_counter()
    rest_lat = round((rest_end - rest_start) * 1000)

    # 4. Displaying Results
    embed = discord.Embed(
        title="🛰️ System Audit",
        description="Performance check for database and API routing.",
        color=discord.Color.blue()
    )
    embed.add_field(name="Gateway (WS)", value=f"`{gateway_lat}ms`", inline=True)
    embed.add_field(name="REST API", value=f"`{rest_lat}ms`", inline=True)
    embed.add_field(name="Supabase DB", value=f"`{db_status}`", inline=True)

    total_latency = gateway_lat + rest_lat + db_lat
    embed.set_footer(text=f"Total perceived delay: ~{total_latency}ms")

    await msg.edit(content=None, embed=embed)


@bot.tree.command(name="help", description="List all available commands and bot info")
async def help_command(interaction: discord.Interaction):
    """Show a categorized summary of the bot's currently exposed commands."""
    embed = discord.Embed(
        title="🤖 Bot Command Center",
        description="I manage parking, late plates, meal schedules, and feedback!",
        color=discord.Color.green(),
    )

    sections = {
        "🚗 Parking": "`/parking_help`, `/offer_spot`, `/claim_spot`, `/claim_staff`, `/parking_status`, `/cancel`, `/my_parking`",
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

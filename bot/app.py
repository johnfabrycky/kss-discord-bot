"""Bot application setup, command registration, and startup hooks."""

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from supabase import AsyncClient, create_async_client

from bot.config import EXTENSIONS, GUILD_ID, MY_GUILD
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

        # Sync slash commands to the development guild. This is fast and safe.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"Tree synced to guild {GUILD_ID}")

    async def on_ready(self):
        """Cache startup data, initialize parking, and publish bot presence."""
        if self._ready_once:
            print(f"Reconnected as {self.user.name}")
            return

        self._ready_once = True
        await self.change_presence(
            activity=discord.CustomActivity(
                name="Custom Status", state="Enter /help to see what I can do!"
            )
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

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    """Handle slash-command cooldowns and Discord-side 429 failures consistently."""
    import math

    command_name = getattr(getattr(interaction, "command", None), "name", "unknown")
    user_id = str(interaction.user.id)
    message_to_send = "Something went wrong while running that command."  # Default

    if isinstance(error, app_commands.CommandOnCooldown):
        retry_after = max(1, math.ceil(error.retry_after))
        logger.info(
            "App command hit cooldown",
            extra={
                "command": command_name,
                "user_id": user_id,
                "retry_after_seconds": retry_after,
            },
        )
        message_to_send = f"Please wait {retry_after}s before using `/{command_name}` again."
    elif isinstance(
        original := getattr(error, "original", error), discord.HTTPException
    ) and original.status == 429:
        logger.warning(
            "Discord rate limited app command response",
            extra={
                "command": command_name,
                "user_id": user_id,
                "status": original.status,
                "discord_error_code": original.code,
            },
        )
        message_to_send = "Discord is rate limiting the bot right now. Please wait a few seconds and try again."
    else:  # Unhandled error
        logger.error(
            "Unhandled app command error",
            extra={"command": command_name, "user_id": user_id},
            exc_info=(
                type(original),
                original,
                original.__traceback__,
            ),
        )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message_to_send, ephemeral=True)
        else:
            await interaction.response.send_message(message_to_send, ephemeral=True)
    except discord.HTTPException:
        logger.warning(
            "Failed to send app command error response",
            extra={"command": command_name, "user_id": user_id},
        )
import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from supabase import Client, create_client

from bot.config import EXTENSIONS, GUILD_ID, MY_GUILD
from bot.utils.database import ensure_tables_exist

# Load environment variables from .env file
load_dotenv()

# Basic logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Felipe(commands.Bot):
    """A custom bot class to hold the Supabase client."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize Supabase client
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_SERVICE_KEY")
        self.supabase: Client = create_client(url, key)

    async def setup_hook(self):
        """This is called once when the bot logs in."""
        logger.info("Running setup hook...")
        # Load all extensions (cogs)
        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info(f"Successfully loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")

        # Sync commands to the guild
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        logger.info(f"Command tree synced to guild {GUILD_ID}")

    async def on_ready(self):
        """Called when the bot is fully connected and ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("------")


async def main():
    """The main entry point for the bot."""
    # --- Automatic Database Schema Setup ---
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        logger.warning("SUPABASE_DB_URL not found. Skipping automatic database schema setup.")
    else:
        await ensure_tables_exist(db_url)

    # --- Bot Initialization ---
    intents = discord.Intents.default()
    intents.members = True  # Required for getting member roles

    bot = Felipe(
        command_prefix="!",  # Prefix is not used for slash commands but is required
        intents=intents,
    )

    # Start the bot
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.critical("DISCORD_TOKEN environment variable not set. Bot cannot start.")
        return

    await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot is shutting down.")
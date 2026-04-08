"""Central runtime configuration for the Discord bot."""
from pathlib import Path

import discord

BASE_DIR = Path(__file__).resolve().parent.parent
GUILD_ID = 1401634963631247512
MY_GUILD = discord.Object(id=GUILD_ID)

INITIAL_EXTENSIONS = [
    "bot.cogs.meals",
    # "bot.cogs.movies",
    "bot.cogs.lates",
    "bot.cogs.parking",
    # "bot.cogs.shifts",
    "bot.cogs.feedback",
    # "bot.cogs.random_ping",
]

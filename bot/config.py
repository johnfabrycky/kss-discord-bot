"""Central runtime configuration for the Discord bot."""
from pathlib import Path

import discord
import pytz

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

LOCAL_TZ = pytz.timezone('America/Chicago')

VALID_SPOTS = list(range(1, 34)) + list(range(41, 47))
STAFF_SPOTS = [998, 999]
MINIMUM_RESERVATION_HOURS = 1
MAXIMUM_RESERVATION_DAYS = 3
MAXIMUM_RESERVATION_HOURS = MAXIMUM_RESERVATION_DAYS * 24

MINIMUM_OFFER_HOURS = 2
MAXIMUM_OFFER_DAYS = 7
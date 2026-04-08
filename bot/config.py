"""Central runtime configuration for the Discord bot."""
from pathlib import Path

import discord
import pytz
from dateutil.relativedelta import MO, TU, WE, TH, FR, SA, SU

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

# UI Display Name -> dateutil Object mapping
WEEKDAYS = [
    (MO, "Monday"),
    (TU, "Tuesday"),
    (WE, "Wednesday"),
    (TH, "Thursday"),
    (FR, "Friday"),
    (SA, "Saturday"),
    (SU, "Sunday")
]

VALID_SPOTS = list(range(1, 34)) + list(range(41, 47))
STAFF_SPOTS = [998, 999]

"""Central runtime configuration for the Discord bot."""
import os
from pathlib import Path

import discord
import pytz
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
GUILD_ID = os.getenv("GUILD_ID")
MY_GUILD = discord.Object(id=GUILD_ID)

EXTENSIONS = [
    "bot.cogs.meals",
    "bot.cogs.lates",
    "bot.cogs.parking",
    "bot.cogs.feedback",
]

LOCAL_TZ = pytz.timezone('America/Chicago')

PERMIT_SPOTS = list(range(1, 34)) + list(range(41, 47))
STAFF_SPOTS = [998, 999]

MINIMUM_RESERVATION_HOURS = 1
MAXIMUM_RESERVATION_DAYS = 3
MAXIMUM_RESERVATION_HOURS = MAXIMUM_RESERVATION_DAYS * 24

MINIMUM_OFFER_HOURS = 2
MAXIMUM_OFFER_DAYS = 7

CLAIM_SPOT_MAX_AUTOCOMPLETE_CHOICES = 5
CANCEL_SPOT_MAX_AUTOCOMPLETE_CHOICES = 25

BOT_NAME = "Felipe"

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

LOCAL_TZ = pytz.timezone("America/Chicago")

PERMIT_SPOTS = list(range(1, 34)) + list(range(41, 47))
STAFF_SPOTS = [998, 999]

# Blackout periods for staff parking reservations.
# Each tuple is (weekday, start_hour, end_hour), where end_hour is exclusive.
# Weekdays are Monday=0 to Sunday=6.
STAFF_PARKING_BLACKOUTS = [
    # Monday-Friday, before 5 PM (00:00 - 16:59)
    (0, 0, 17),
    (1, 0, 17),
    (2, 0, 17),
    (3, 0, 17),
    (4, 0, 17),
    # Sunday, 2 AM - 2 PM (02:00 - 13:59)
    (6, 2, 14),
]

MINIMUM_RESERVATION_HOURS = 1
MAXIMUM_RESERVATION_DAYS = 3
MAXIMUM_RESERVATION_HOURS = MAXIMUM_RESERVATION_DAYS * 24

MINIMUM_OFFER_HOURS = 2
MAXIMUM_OFFER_DAYS = 7

CLAIM_SPOT_MAX_AUTOCOMPLETE_CHOICES = 5
CANCEL_SPOT_MAX_AUTOCOMPLETE_CHOICES = 25

PARKING_STATUS_CACHE_TTL_SECONDS = 15

BOT_NAME = "Felipe"

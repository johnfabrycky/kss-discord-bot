"""Central runtime configuration for the Discord bot."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import discord

from bot.utils.constants import LOCAL_TZ


@dataclass(frozen=True)
class AcademicBreak:
    """A configured break window that may pause meal rotation."""

    name: str
    start: datetime
    end: datetime
    rotation_skip_days: int = 0


@dataclass(frozen=True)
class MealCalendarConfig:
    """Structured calendar configuration for rotating meal schedules."""

    semester_start: datetime
    rotation_length_weeks: int
    breaks: tuple[AcademicBreak, ...]


BASE_DIR = Path(__file__).resolve().parent.parent
GUILD_ID = 1401634963631247512
MY_GUILD = discord.Object(id=GUILD_ID)

MEAL_CALENDAR = MealCalendarConfig(
    semester_start=datetime(2026, 1, 19, tzinfo=LOCAL_TZ),
    rotation_length_weeks=4,
    breaks=(
        AcademicBreak(
            name="Spring Break 🌸",
            start=datetime(2026, 3, 14, tzinfo=LOCAL_TZ),
            end=datetime(2026, 3, 22, 23, 59, tzinfo=LOCAL_TZ),
            rotation_skip_days=7,
        ),
    ),
)

INITIAL_EXTENSIONS = [
    "bot.cogs.meals",
    # "bot.cogs.movies",
    "bot.cogs.lates",
    "bot.cogs.parking",
    # "bot.cogs.shifts",
    "bot.cogs.feedback",
    # "bot.cogs.random_ping",
]

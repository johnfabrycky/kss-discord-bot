from datetime import datetime

from supabase import AsyncClient

from bot.config import LOCAL_TZ
from bot.utils.meal_calendar import AcademicBreak, MealCalendarConfig


class MealsService:
    """Handles data fetching, caching, and business logic for the meal system."""

    def __init__(self, bot, supabase: AsyncClient):
        """Initialize the service with the bot reference and a shared Supabase client."""
        self.bot = bot
        self.supabase = supabase
        self.calendar_config = None

    async def refresh_calendar_config(self) -> bool:
        """Queries Supabase for the active meal calendar and caches it."""
        try:
            # Now using the injected client via self.supabase
            response = await self.supabase.table("meal_calendars").select(
                "*, academic_breaks(*)"
            ).eq("is_active", True).execute()

            if not response.data:
                print("Warning: No active meal calendar found in database.")
                return False

            active_cal = response.data[0]

            breaks = [
                AcademicBreak(
                    name=b["name"],
                    start=datetime.fromisoformat(b["start_date"]).astimezone(LOCAL_TZ),
                    end=datetime.fromisoformat(b["end_date"]).astimezone(LOCAL_TZ),
                    rotation_skip_days=b["rotation_skip_days"]
                )
                for b in active_cal.get("academic_breaks", [])
            ]

            self.calendar_config = MealCalendarConfig(
                semester_start=datetime.fromisoformat(active_cal["semester_start"]).astimezone(LOCAL_TZ),
                rotation_length_weeks=active_cal["rotation_length_weeks"],
                breaks=breaks
            )
            print("Successfully loaded Meal Calendar config from Supabase.")
            return True

        except Exception as e:
            print(f"Error fetching calendar config: {e}")
            return False

    def get_meal_from_cache(self, week: int, day: str, meal_type: str) -> str:
        """Filters the cached menu data for the specific meal."""
        meal_type = meal_type.lower()

        # Accessing the cache from the bot object where it's stored
        for meal in getattr(self.bot, "meal_cache", []):
            if (
                    meal["week_number"] == week
                    and meal["day"].strip() == day
                    and meal["meal_type"] == meal_type
            ):
                return meal["dish_name"]

        return "No meal scheduled"

    def get_active_break_name(self, current_date: datetime) -> str | None:
        """Return the current academic break label, if one is configured."""
        if not self.calendar_config:
            return None

        for break_window in self.calendar_config.breaks:
            if break_window.start <= current_date <= break_window.end:
                return break_window.name

        return None

    def calculate_rotation_week(self, current_date: datetime) -> int:
        """Return the active meal rotation week for the configured calendar."""
        if not self.calendar_config:
            return 1  # Fallback if DB fails to load

        days_since_start = (current_date - self.calendar_config.semester_start).days

        for break_window in self.calendar_config.breaks:
            if current_date > break_window.end:
                days_since_start -= break_window.rotation_skip_days

        return ((max(0, days_since_start) // 7) % self.calendar_config.rotation_length_weeks) + 1

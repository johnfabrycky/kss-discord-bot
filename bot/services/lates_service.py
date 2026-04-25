import asyncio
import logging
import os

import aiohttp

logger = logging.getLogger(__name__)


class LatesService:
    """Business logic and data access for late-plate commands."""

    def __init__(self, supabase):
        """Store the shared Supabase client used by late-plate operations."""
        self.supabase = supabase

    @staticmethod
    def get_user_house(member):
        """Return the caller's house role slug, if present."""
        role_names = [role.name.lower() for role in member.roles]
        if "koinonian" in role_names:
            return "koinonian"
        if "stratfordite" in role_names:
            return "stratfordite"
        if "suttonite" in role_names:
            return "suttonite"
        return None

    async def perform_cleanup(self, day_to_clean=None):
        """Delete temporary lates for a specific day or for all days."""
        try:
            query = self.supabase.table("lates").delete().eq("is_permanent", False)
            if day_to_clean:
                query = query.eq("day_of_week", day_to_clean)

            res = await query.execute()
            count = len(res.data) if res.data else 0

            ping_url = os.getenv("HEALTHCHECK_URL")
            if ping_url:
                async with aiohttp.ClientSession() as session:
                    await session.get(ping_url)

            return count
        except Exception:
            logger.exception("Late cleanup failed", extra={"day_to_clean": day_to_clean})
            return None

    async def get_visible_lates(self, house, day, meal):
        """Return lates visible to the caller's house grouping for one meal."""
        target_roles = ["koinonian"] if house == "koinonian" else ["stratfordite", "suttonite"]
        res = await self.supabase.table("lates") \
            .select("*") \
            .eq("day_of_week", day) \
            .eq("meal", meal) \
            .in_("role", target_roles) \
            .execute()

        return res.data or []

    async def create_late(self, user_id, display_name, house, day, meal, is_permanent):
        """Create a new late request unless the same request already exists."""
        existing = await self.supabase.table("lates") \
            .select("*") \
            .eq("user_id", str(user_id)) \
            .eq("day_of_week", day) \
            .eq("meal", meal) \
            .execute()

        if existing.data:
            return False, "duplicate"

        payload = {
            "user_id": str(user_id),
            "nickname": display_name,
            "role": house,
            "meal": meal,
            "day_of_week": day,
            "is_permanent": is_permanent,
        }
        await self.supabase.table("lates").insert(payload).execute()
        return True, payload

    async def get_autocomplete_lates(self, user_id):
        """Return a caller's lates for autocomplete display."""
        res = await self.supabase.table("lates") \
            .select("day_of_week", "meal", "is_permanent") \
            .eq("user_id", str(user_id)) \
            .execute()

        return res.data or []

    async def clear_late(self, user_id, day, meal):
        """Delete one late request for the caller."""
        res = await self.supabase.table("lates") \
            .delete() \
            .eq("user_id", str(user_id)) \
            .eq("day_of_week", day) \
            .eq("meal", meal) \
            .execute()

        return bool(res.data)

    async def get_user_lates(self, user_id):
        """Fetch all active late requests for one caller."""
        res = await self.supabase.table("lates") \
            .select("*") \
            .eq("user_id", str(user_id)) \
            .execute()

        return res.data or []

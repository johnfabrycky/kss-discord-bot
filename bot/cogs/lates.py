import asyncio
import logging
import os
from datetime import datetime, time

import aiohttp
import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks
from flask.cli import load_dotenv
from supabase import create_client

local_tz = pytz.timezone("America/Chicago")
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)
logger = logging.getLogger(__name__)


async def run_supabase(query, timeout=10):
    """Execute a blocking Supabase query off the event loop."""
    return await asyncio.wait_for(asyncio.to_thread(query.execute), timeout=timeout)


class Lates(commands.Cog):
    """Commands and scheduled cleanup for the late-plate system."""

    def __init__(self, bot):
        """Initialize the cog and start the nightly cleanup loop."""
        self.bot = bot
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        self.meals = ["Lunch", "Dinner"]
        self.cleanup_loop.start()

    def _get_user_house(self, member: discord.Member):
        """Return the caller's house role slug, if present."""
        role_names = [role.name.lower() for role in member.roles]
        if "koinonian" in role_names:
            return "koinonian"
        if "stratfordite" in role_names:
            return "stratfordite"
        if "suttonite" in role_names:
            return "suttonite"
        return None

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=local_tz))
    async def cleanup_loop(self):
        """Trigger nightly cleanup for the previous day's temporary lates."""
        from datetime import timedelta

        now_chicago = datetime.now(local_tz)
        yesterday = now_chicago - timedelta(days=1)
        yesterday_name = yesterday.strftime("%A")
        print(f"⏰ Midnight Cleanup Triggered. Cleaning up lates for: {yesterday_name}", flush=True)
        await self.perform_cleanup(day_to_clean=yesterday_name)

    async def perform_cleanup(self, day_to_clean: str = None):
        """Delete temporary lates for a specific day or for all days."""
        try:
            query = supabase.table("lates").delete().eq("is_permanent", False)
            if day_to_clean:
                query = query.eq("day_of_week", day_to_clean)

            res = await run_supabase(query, timeout=20)
            count = len(res.data) if res.data else 0
            scope = day_to_clean if day_to_clean else "ALL"
            print(f"🧹 Cleanup Complete: Removed {count} temp lates for {scope}.", flush=True)

            ping_url = os.getenv("HEALTHCHECK_URL")
            if ping_url:
                async with aiohttp.ClientSession() as session:
                    await session.get(ping_url)
                    print("Successfully pinged Healthchecks.io")

            return count
        except Exception:
            logger.exception("Late cleanup failed", extra={"day_to_clean": day_to_clean})
            return None

    @commands.command(name="force_cleanup")
    @commands.has_permissions(administrator=True)
    async def manual_cleanup(self, ctx):
        """Manually trigger a total wipe of all temporary lates."""
        await ctx.send("Deleting **all** temporary lates across all days... 🧹")
        count = await self.perform_cleanup()

        if count is not None:
            await ctx.send(f"✅ Success! Removed {count} temporary lates.")
        else:
            await ctx.send("❌ Cleanup failed. Check bot console for errors.")

    @app_commands.command(name="view_lates", description="See lates for your house")
    @app_commands.choices(
        day=[app_commands.Choice(name=day, value=day) for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
        meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")],
    )
    async def view_lates(self, interaction: discord.Interaction, day: str, meal: str):
        """Show late requests visible to the caller's house group for one meal."""
        await interaction.response.defer(ephemeral=True)

        house = self._get_user_house(interaction.user)
        if not house:
            return await interaction.followup.send("❌ No house role detected.", ephemeral=True)

        target_roles = ["koinonian"] if house == "koinonian" else ["stratfordite", "suttonite"]
        res = await run_supabase(
            supabase.table("lates").select("*").eq("day_of_week", day).eq("meal", meal).in_("role", target_roles)
        )

        filtered_list = []
        for info in res.data:
            status = "🔄" if info["is_permanent"] else "⏱️"
            filtered_list.append(f"{status} **{info['nickname']}**")

        total_count = len(filtered_list)
        if total_count == 0:
            return await interaction.followup.send(
                f"No lates recorded for **{day} {meal}** in your house group.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title=f"🍽️ Lates: {day} {meal} ({total_count} total)",
            description="\n".join(filtered_list),
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="late_me", description="Request food to be set aside")
    @app_commands.choices(
        day=[app_commands.Choice(name=day, value=day) for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
        meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")],
        duration=[app_commands.Choice(name="Permanent", value="True"), app_commands.Choice(name="Temporary", value="False")],
    )
    async def late_me(self, interaction: discord.Interaction, day: str, meal: str, duration: str):
        """Create a temporary or permanent late request for the caller."""
        await interaction.response.defer(ephemeral=True)

        house = self._get_user_house(interaction.user)
        if not house:
            return await interaction.followup.send("❌ You must have a house role to use this.", ephemeral=True)

        user_id = str(interaction.user.id)
        is_permanent = duration == "True"

        existing = await run_supabase(
            supabase.table("lates").select("*").eq("user_id", user_id).eq("day_of_week", day).eq("meal", meal)
        )
        if existing.data:
            return await interaction.followup.send("❌ You already have a late for this meal.", ephemeral=True)

        data = {
            "user_id": user_id,
            "nickname": interaction.user.display_name,
            "role": house,
            "meal": meal,
            "day_of_week": day,
            "is_permanent": is_permanent,
        }
        await run_supabase(supabase.table("lates").insert(data))
        await interaction.followup.send(f"✅ Late recorded for **{day} {meal}** ({house.capitalize()}).", ephemeral=True)

    async def late_days_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Return the caller's existing lates as autocomplete choices."""
        user_id = str(interaction.user.id)
        try:
            res = await run_supabase(
                supabase.table("lates").select("day_of_week", "meal", "is_permanent").eq("user_id", user_id),
                timeout=2.5,
            )
        except Exception:
            logger.exception("Late autocomplete failed", extra={"user_id": user_id, "current": current})
            return []

        choices = []
        for row in res.data:
            day = row["day_of_week"]
            meal = row["meal"]
            freq = "permanent" if row["is_permanent"] else "temporary"
            label = f"{day} {meal} ({freq})"
            value = f"{day}|{meal}"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=value))

        return choices[:25]

    @app_commands.command(name="clear_late", description="Select an existing late request to remove")
    @app_commands.autocomplete(selection=late_days_autocomplete)
    async def clear_late(self, interaction: discord.Interaction, selection: str):
        """Delete one late request selected from autocomplete."""
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        try:
            day, meal = selection.split("|")
        except ValueError:
            return await interaction.followup.send("❌ Invalid selection.", ephemeral=True)

        res = await run_supabase(
            supabase.table("lates").delete().eq("user_id", user_id).eq("day_of_week", day).eq("meal", meal)
        )

        if res.data:
            await interaction.followup.send(f"🗑️ Your {day} {meal} late has been cleared.", ephemeral=True)
        else:
            await interaction.followup.send(
                "❌ Could not find that late. It may have already been cleared.",
                ephemeral=True,
            )

    @app_commands.command(name="my_lates", description="See all the meals you've requested lates for")
    async def my_lates(self, interaction: discord.Interaction):
        """List every currently active late request owned by the caller."""
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        res = await run_supabase(supabase.table("lates").select("*").eq("user_id", user_id))

        if not res.data:
            return await interaction.followup.send("You don't have any active lates.", ephemeral=True)

        found_lates = [
            f"• **{row['day_of_week']} {row['meal']}**: {'🔄 Permanent' if row['is_permanent'] else '⏱️ This week'}"
            for row in res.data
        ]
        embed = discord.Embed(
            title="📋 Your Registered Lates",
            description="\n".join(found_lates),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    """Register the lates cog with the bot."""
    await bot.add_cog(Lates(bot))

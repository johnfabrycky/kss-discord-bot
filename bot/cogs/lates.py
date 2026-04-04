import logging
from datetime import datetime, time

import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks

from bot.services.lates_service import LatesService

local_tz = pytz.timezone("America/Chicago")
logger = logging.getLogger(__name__)


class Lates(commands.Cog):
    """Commands and scheduled cleanup for the late-plate system."""

    def __init__(self, bot):
        """Initialize the cog and start the nightly cleanup loop."""
        self.bot = bot
        self.service = LatesService(bot.supabase)
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        self.meals = ["Lunch", "Dinner"]
        self.cleanup_loop.start()

    def _get_user_house(self, member: discord.Member):
        """Return the caller's house role slug, if present."""
        return self.service.get_user_house(member)

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
        count = await self.service.perform_cleanup(day_to_clean)
        scope = day_to_clean if day_to_clean else "ALL"
        if count is not None:
            print(f"🧹 Cleanup Complete: Removed {count} temp lates for {scope}.", flush=True)
        return count

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
        day=[app_commands.Choice(name=day, value=day) for day in
             ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
        meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")],
    )
    async def view_lates(self, interaction: discord.Interaction, day: str, meal: str):
        """Show late requests visible to the caller's house group for one meal."""
        await interaction.response.defer(ephemeral=True)

        house = self._get_user_house(interaction.user)
        if not house:
            return await interaction.followup.send("❌ No house role detected.", ephemeral=True)

        filtered_list = []
        for info in await self.service.get_visible_lates(house, day, meal):
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
        day=[app_commands.Choice(name=day, value=day) for day in
             ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
        meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")],
        duration=[app_commands.Choice(name="Permanent", value="True"),
                  app_commands.Choice(name="Temporary", value="False")],
    )
    async def late_me(self, interaction: discord.Interaction, day: str, meal: str, duration: str):
        """Create a temporary or permanent late request for the caller."""
        await interaction.response.defer(ephemeral=True)

        house = self._get_user_house(interaction.user)
        if not house:
            return await interaction.followup.send("❌ You must have a house role to use this.", ephemeral=True)

        success, _result = await self.service.create_late(
            interaction.user.id,
            interaction.user.display_name,
            house,
            day,
            meal,
            duration == "True",
        )
        if not success:
            return await interaction.followup.send("❌ You already have a late for this meal.", ephemeral=True)

        await interaction.followup.send(f"✅ Late recorded for **{day} {meal}** ({house.capitalize()}).", ephemeral=True)

    async def late_days_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str,
    ) -> list[app_commands.Choice[str]]:
        """Return the caller's existing lates as autocomplete choices."""
        try:
            rows = await self.service.get_autocomplete_lates(interaction.user.id)
        except Exception:
            logger.exception("Late autocomplete failed", extra={"user_id": str(interaction.user.id), "current": current})
            return []

        choices = []
        for row in rows:
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

        if await self.service.clear_late(user_id, day, meal):
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

        rows = await self.service.get_user_lates(interaction.user.id)
        if not rows:
            return await interaction.followup.send("You don't have any active lates.", ephemeral=True)

        found_lates = [
            f"• **{row['day_of_week']} {row['meal']}**: {'🔄 Permanent' if row['is_permanent'] else '⏱️ This week'}"
            for row in rows
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

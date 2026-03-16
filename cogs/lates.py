import os
import discord
import pytz

from discord.ext import tasks
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from supabase import create_client
from flask.cli import load_dotenv
from datetime import time

local_tz = pytz.timezone('America/Chicago')
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

class Lates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        self.meals = ["Lunch", "Dinner"]

    def _get_user_house(self, member: discord.Member):
        """Returns 'koinonian', 'stratfordite', or 'suttonite' based on Discord roles."""
        # Convert all user role names to lowercase for matching
        role_names = [r.name.lower() for r in member.roles]

        if "koinonian" in role_names:
            return "koinonian"
        elif "stratfordite" in role_names:
            return "stratfordite"
        elif "suttonite" in role_names:
            return "suttonite"
        return None

    # Anchors the task to run every day at 11:00 PM
    @tasks.loop(time=time(hour=23, minute=0, second=0))
    async def cleanup_temporary_lates(self):
        """Deletes all temporary lates on Saturday night."""
        now = datetime.now(local_tz)

        # Check if today is Saturday (5)
        if now.weekday() == 5:
            try:
                res = supabase.table("lates").delete() \
                    .eq("is_permanent", False) \
                    .execute()

                count = len(res.data) if res.data else 0
                print(f"🧹 Saturday Night Cleanup: Removed {count} temporary lates.")
            except Exception as e:
                print(f"❌ Cleanup failed: {e}")

    @app_commands.command(name="view_lates", description="See lates for your house")
    @app_commands.choices(
        day=[app_commands.Choice(name=d, value=d) for d in
             ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
        meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")]
    )
    async def view_lates(self, interaction: discord.Interaction, day: str, meal: str):
        house = self._get_user_house(interaction.user)
        if not house:
            return await interaction.response.send_message("❌ No house role detected.", ephemeral=True)

        # Logic: Koinonian sees Koinonians; Stratford/Sutton see each other
        target_roles = ["koinonian"] if house == "koinonian" else ["stratfordite", "suttonite"]

        res = supabase.table("lates").select("*") \
            .eq("day_of_week", day) \
            .eq("meal", meal) \
            .in_("role", target_roles) \
            .execute()

        filtered_list = []
        for info in res.data:
            status = "🔄" if info["is_permanent"] else "⏱️"
            filtered_list.append(f"{status} **{info['nickname']}**")

        total_count = len(filtered_list)

        if total_count == 0:
            return await interaction.response.send_message(
                f"No lates recorded for **{day} {meal}** in your house group.", ephemeral=True)

        embed = discord.Embed(
            title=f"🍽️ Lates: {day} {meal} ({total_count} total)",
            description="\n".join(filtered_list),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="late_me", description="Request food to be set aside")
    @app_commands.choices(
        day=[app_commands.Choice(name=d, value=d) for d in
             ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
        meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")],
        duration = [app_commands.Choice(name="Permanent", value="True"), app_commands.Choice(name="Temporary", value="False")],
    )
    async def late_me(self, interaction: discord.Interaction, day: str, meal: str, duration: str):
        # Automatically determine role
        house = self._get_user_house(interaction.user)
        if not house:
            return await interaction.response.send_message(
                "❌ You must have a house role (Koinonian, Stratfordite, or Suttonite) to use this.", ephemeral=True)

        user_id = str(interaction.user.id)

        is_permanent = duration == "True"

        # Check for existing
        existing = supabase.table("lates").select("*").eq("user_id", user_id).eq("day_of_week", day).eq("meal",
                                                                                                        meal).execute()
        if existing.data:
            return await interaction.response.send_message("❌ You already have a late for this meal.", ephemeral=True)

        # Insert with automated house role
        data = {
            "user_id": user_id,
            "nickname": interaction.user.display_name,
            "role": house,  # Automated
            "meal": meal,
            "day_of_week": day,
            "is_permanent": is_permanent
        }
        supabase.table("lates").insert(data).execute()
        await interaction.response.send_message(f"✅ Late recorded for **{day} {meal}** ({house.capitalize()}).",
                                                ephemeral=True)

    async def late_days_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str,
    ) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)

        # Fetch all lates for this specific user
        res = supabase.table("lates").select("day_of_week", "meal").eq("user_id", user_id).execute()

        # Format the choices (e.g., "Monday - Dinner")
        choices = [
            app_commands.Choice(name=f"{row['day_of_week']} {row['meal']}", value=f"{row['day_of_week']}|{row['meal']}")
            for row in res.data
            if current.lower() in f"{row['day_of_week']} {row['meal']}".lower()
        ]

        return choices[:25]  # Discord limits autocomplete to 25 choices

    @app_commands.command(name="clear_late", description="Select an existing late request to remove")
    @app_commands.autocomplete(selection=late_days_autocomplete)
    async def clear_late(self, interaction: discord.Interaction, selection: str):
        user_id = str(interaction.user.id)

        # Split the value back into day and meal
        try:
            day, meal = selection.split("|")
        except ValueError:
            await interaction.response.send_message("❌ Invalid selection.", ephemeral=True)
            return

        # Perform the deletion
        res = (supabase.table("lates").delete()
            .eq("user_id", user_id)
            .eq("day_of_week", day)
            .eq("meal", meal)
            .execute())

        if res.data:
            await interaction.response.send_message(f"🗑️ Your {day} {meal} late has been cleared.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Could not find that late. It may have already been cleared.",
                                                    ephemeral=True)


    @app_commands.command(name="my_lates", description="See all the meals you've requested lates for")
    async def my_lates(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        res = (supabase
               .table("lates")
               .select("*")
               .eq("user_id", user_id)
               .execute())

        if not res.data:
            return await interaction.response.send_message("You don't have any active lates.", ephemeral=True)

        found_lates = []
        for info in res.data:
            status = "🔄 Permanent" if info["is_permanent"] else "⏱️ This week only"
            found_lates.append(f"• **{info['day_of_week']} {info['meal']}**: {status}")

        embed = discord.Embed(title="📋 Your Registered Lates", description="\n".join(found_lates),
                              color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Lates(bot))
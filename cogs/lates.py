from discord.ext import tasks
import discord
from discord.ext import commands
from discord import app_commands
import pandas as pd
import json
import os
import io
from datetime import datetime
from supabase import create_client
import pytz
from flask.cli import load_dotenv

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

    @tasks.loop(hours=24)
    async def cleanup_temporary_lates(self):
        """Deletes all temporary lates on Monday morning."""
        now = datetime.now(local_tz)
        if now.weekday() == 0:  # Monday
            supabase.table("lates").delete().eq("is_permanent", False).execute()
            print("🧹 Cleaned up weekly temporary lates.")

    # @app_commands.command(name="view_lates", description="See lates for your house")
    # @app_commands.choices(
    #     day=[app_commands.Choice(name=d, value=d) for d in
    #          ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
    #     meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")],
    #     my_role=[
    #         app_commands.Choice(name="Koinonian", value="koinonian"),
    #         app_commands.Choice(name="Stratfordite", value="stratfordite"),
    #         app_commands.Choice(name="Suttonite", value="suttonite")
    #     ]
    # )



    # async def view_lates(self, interaction: discord.Interaction, day: str, meal: str, my_role: str):
    #     target_roles = ["koinonian"] if my_role == "koinonian" else ["stratfordite", "suttonite"]
    #
    #     # Fetch only matching lates
    #     res = supabase.table("lates").select("*") \
    #         .eq("day_of_week", day) \
    #         .eq("meal", meal) \
    #         .in_("role", target_roles) \
    #         .execute()
    #
    #     filtered_list = []
    #     for info in res.data:
    #         status = "🔄" if info["is_permanent"] else "⏱️"
    #         filtered_list.append(f"{status} **{info['nickname']}**")
    #
    #     total_count = len(filtered_list)
    #
    #     if total_count == 0:
    #         return await interaction.response.send_message(
    #             f"No lates recorded for **{day} {meal}** in your house group.", ephemeral=True)
    #
    #     embed = discord.Embed(
    #         title=f"🍽️ Lates: {day} {meal} ({total_count} total)",
    #         description="\n".join(filtered_list),
    #         color=discord.Color.blue()
    #     )
    #     await interaction.response.send_message(embed=embed, ephemeral=True)

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

    # @app_commands.command(name="late_me", description="Request food to be set aside")
    # @app_commands.choices(
    #     day=[app_commands.Choice(name=d, value=d) for d in
    #          ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
    #     meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")],
    #     role=[
    #         app_commands.Choice(name="Koinonian", value="koinonian"),
    #         app_commands.Choice(name="Stratfordite", value="stratfordite"),
    #         app_commands.Choice(name="Suttonite", value="suttonite")
    #     ]
    # )

    # async def late_me(self, interaction: discord.Interaction, day: str, meal: str, role: str, permanent: bool = False):
    #     user_id = str(interaction.user.id)
    #
    #     # 1. Check for existing late for this specific day/meal
    #     existing = supabase.table("lates").select("*") \
    #         .eq("user_id", user_id).eq("day_of_week", day).eq("meal", meal).execute()
    #
    #     if existing.data:
    #         return await interaction.response.send_message("❌ You already have a late for this meal.", ephemeral=True)
    #
    #     # 2. Insert into Supabase
    #     data = {
    #         "user_id": user_id,
    #         "nickname": interaction.user.display_name,
    #         "role": role,
    #         "meal": meal,
    #         "day_of_week": day,
    #         "is_permanent": permanent
    #     }
    #     supabase.table("lates").insert(data).execute()
    #     await interaction.response.send_message(f"✅ Late recorded for **{day} {meal}**.", ephemeral=True)

    @app_commands.command(name="late_me", description="Request food to be set aside")
    @app_commands.choices(
        day=[app_commands.Choice(name=d, value=d) for d in
             ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
        meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")]
    )
    async def late_me(self, interaction: discord.Interaction, day: str, meal: str, permanent: bool = False):
        # Automatically determine role
        house = self._get_user_house(interaction.user)
        if not house:
            return await interaction.response.send_message(
                "❌ You must have a house role (Koinonian, Stratfordite, or Suttonite) to use this.", ephemeral=True)

        user_id = str(interaction.user.id)

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
            "is_permanent": permanent
        }
        supabase.table("lates").insert(data).execute()
        await interaction.response.send_message(f"✅ Late recorded for **{day} {meal}** ({house.capitalize()}).",
                                                ephemeral=True)

    @app_commands.command(name="clear_late", description="Remove your late request")
    @app_commands.choices(
        day=[app_commands.Choice(name=d, value=d) for d in
             ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
        meal=[app_commands.Choice(name="Lunch", value="Lunch"), app_commands.Choice(name="Dinner", value="Dinner")]
    )
    async def clear_late(self, interaction: discord.Interaction, day: str, meal: str):
        user_id = str(interaction.user.id)

        # Perform the deletion in Supabase directly
        res = supabase.table("lates").delete() \
            .eq("user_id", user_id) \
            .eq("day_of_week", day) \
            .eq("meal", meal) \
            .execute()

        if res.data:
            await interaction.response.send_message(f"🗑️ Your late for {day} {meal} has been cleared.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No late found to clear.", ephemeral=True)

    @app_commands.command(name="my_lates", description="See all the meals you've requested lates for")
    async def my_lates(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        res = supabase.table("lates").select("*").eq("user_id", user_id).execute()

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
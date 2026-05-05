import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class General(commands.Cog):
    """General purpose commands, including help and bot owner tools."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="List all available commands and bot info")
    async def help_command(self, interaction: discord.Interaction):
        """Show a categorized summary of the bot's currently exposed commands."""
        embed = discord.Embed(
            title="🤖 Bot Command Center",
            description="I manage parking, late plates, meal schedules, and feedback!",
            color=discord.Color.green(),
        )

        sections = {
            "🚗 Parking": "`/parking_help`, `/offer_spot`, `/claim_spot`, `/claim_staff`, `/parking_status`, `/cancel`, `/my_parking`",
            "🍱 Lates": "`/late_me`, `/view_lates`, `/my_lates`, `/clear_late`",
            "🍽️ Meals": "`/today`",
            "📝 Feedback": "`/feedback`",
        }

        for name, value in sections.items():
            embed.add_field(name=name, value=value, inline=False)

        embed.set_footer(
            text="Pro-tip: Slash commands show you exactly what to type as you go!"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="audit")
    @commands.is_owner()
    async def audit_latency(self, ctx: commands.Context):
        """Measures Gateway, REST, and Database latency in one sequence."""
        gateway_lat = round(self.bot.latency * 1000)

        db_start = time.perf_counter()
        try:
            if self.bot.supabase is None:
                raise ValueError("Supabase client not initialized")

            await self.bot.supabase.table("parking_offers").select("*").limit(1).execute()
            db_end = time.perf_counter()
            db_lat = round((db_end - db_start) * 1000)
            db_status = f"{db_lat}ms"
        except Exception as e:
            db_status = f"Error: {type(e).__name__}"
            db_lat = 0

        rest_start = time.perf_counter()
        msg = await ctx.send("⚙️ Auditing system performance...")
        rest_end = time.perf_counter()
        rest_lat = round((rest_end - rest_start) * 1000)

        embed = discord.Embed(
            title="🛰️ System Audit",
            description="Performance check for database and API routing.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Gateway (WS)", value=f"`{gateway_lat}ms`", inline=True)
        embed.add_field(name="REST API", value=f"`{rest_lat}ms`", inline=True)
        embed.add_field(name="Supabase DB", value=f"`{db_status}`", inline=True)

        total_latency = gateway_lat + rest_lat + db_lat
        embed.set_footer(text=f"Total perceived delay: ~{total_latency}ms")

        await msg.edit(content=None, embed=embed)

    @commands.command()
    @commands.is_owner()
    async def sync_global(self, ctx: commands.Context):
        """Sync global slash commands for production-style rollout."""
        await self.bot.tree.sync()
        await ctx.send("🌍 Global slash commands synced (may take 1 hour).")

    @commands.command()
    @commands.is_owner()
    async def clear_ghosts(self, ctx: commands.Context):
        """Clear globally registered commands to remove stale slash-command entries."""
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync()
        await ctx.send("👻 Ghost commands cleared! The duplicate should vanish shortly.")


async def setup(bot: commands.Bot):
    """Register the general cog with the bot."""
    await bot.add_cog(General(bot))
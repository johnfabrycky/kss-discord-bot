import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from keep_alive import keep_alive
from supabase import create_client

load_dotenv()

# --- Configuration ---
GUILD_ID = 1401634963631247512
MY_GUILD = discord.Object(id=GUILD_ID)

INITIAL_EXTENSIONS = [
    'cogs.meals',
    # 'cogs.movies',
    'cogs.lates',
    'cogs.parking',
    # 'cogs.shifts',
    'cogs.feedback',
]


# --- Bot Initialization ---
class GeraldBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents, help_command=None)

        # Initialize Supabase
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        self.supabase = create_client(url, key)
        self.meal_cache = []

    async def setup_hook(self):
        # 1. Load Extensions
        for extension in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(extension)
                print(f"✅ Loaded {extension}")
            except Exception as e:
                print(f"❌ Failed to load {extension}: {e}")

        # 2. Sync Slash Commands (Instant Guild Sync)
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"🌲 Tree synced to guild {GUILD_ID}")

    @bot.command()
    @commands.is_owner()
    async def clear_ghosts(ctx):
        # This tells Discord: "Delete every global command I ever made"
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        await ctx.send("👻 Ghost commands cleared! The duplicate should vanish shortly.")

    async def on_ready(self):
        # 3. Cache Initial Data
        # The 'state' is what actually shows up in the bubble
        await self.change_presence(
            activity=discord.CustomActivity(name="Custom Status", state="Enter /help to see what I can do!")
        )

        try:
            response = self.supabase.table("meals").select("*").execute()
            self.meal_cache = response.data
            print(f"✅ Cached {len(self.meal_cache)} meals")
        except Exception as e:
            print(f"❌ Failed to cache meals: {e}")

        # 4. Cog-specific Init
        parking_cog = self.get_cog("Parking")
        if parking_cog:
            await parking_cog.initialize_parking_spots()
            print("✅ Parking spots initialized")

        print(f"🚀 {self.user.name} is online in Champaign!")


bot = GeraldBot()


# --- Manual Sync Command (For Global Syncing if needed) ---
@bot.command()
@commands.is_owner()
async def sync_global(ctx):
    await bot.tree.sync()
    await ctx.send("🌍 Global slash commands synced (may take 1 hour).")


# --- Help Command ---
@bot.tree.command(name="help", description="List all available commands and bot info")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Bot Command Center",
        description="I manage parking, late plates, movie sessions, meal schedules, meal shifts, and feedback!",
        color=discord.Color.green()
    )

    sections = {
        "🚗 Parking": "`/offer_spot`, `/claim_spot`, `/claim_staff`, `/parking_status`, `/cancel`, `/parking_help`",
        "🍱 Lates": "`/late_me`, `/view_lates`, `/my_lates`, `/clear_late`",
        # "🎬 Movies": "`/watch`, `/where`",
        "🍽️ Meals": "`/today`",
        # "⚖️ Shifts": "`/offer_shift`, `/view_market`, `/claim_shift`, `/swap_shift`, /my_shifts`, `/cancel_shift`",
        "📝 Feedback": "`/feedback`",
    }

    for name, value in sections.items():
        embed.add_field(name=name, value=value, inline=False)

    embed.set_footer(text="Pro-tip: Slash commands show you exactly what to type as you go!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv('DISCORD_TOKEN'))

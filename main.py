import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from keep_alive import keep_alive
from supabase import create_client

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

# Define which cogs to load
INITIAL_EXTENSIONS = [
    'cogs.meals',
    'cogs.movies',
    'cogs.lates',
    'cogs.parking',
]

@bot.event
async def on_ready():
    for extension in INITIAL_EXTENSIONS:
        try:
            await bot.load_extension(extension)
            print(f"✅ Loaded {extension}")
        except Exception as e:
            print(f"❌ Failed to load {extension}: {e}")

    MY_GUILD_ID = 1401634963631247512
    MY_GUILD = discord.Object(id=MY_GUILD_ID)
    await bot.tree.sync(guild=MY_GUILD)
    await bot.tree.sync()

    # Fetch and cache Supabase data
    try:
        response = supabase.table("meals").select("*").execute()
        # Store as a list of dicts on the bot object for global access
        bot.meal_cache = response.data
        print(f"✅ Cached {len(bot.meal_cache)} meals from Supabase")
    except Exception as e:
        bot.meal_cache = []
        print(f"❌ Failed to cache Supabase data: {e}")

    parking_cog = bot.get_cog("Parking")

    if parking_cog:
        try:
            await parking_cog.initialize_parking_spots()
            print("✅ Parking spots initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize parking spots: {e}")
    else:
        print("⚠️ Could not find Parking Cog. Check if the class name is 'Parking'.")

    print(f"🚀 {bot.user.name} is ready for action in Champaign!")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("Slash commands synced")

@bot.tree.command(name="help", description="List all available commands and bot info")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Bot Command Center",
        #description="I manage movie sessions, UIUC meal schedules, and late plates!",
        description="I manage parking, movie sessions, meal schedules",
        color=discord.Color.green()
    )

    # Parking Section
    embed.add_field(
        name="🚗 Parking Utility",
        value=(
            "`/offer_spot` - List your parking spot as available.\n"
            "`/claim_spot` - Claim an offered spot or the guest spot (46).\n"
            "`/claim_staff` - Reserve a staff spot (subject to blackout hours).\n"
            "`/parking_status` - See which spots are currently free.\n"
            "`/cancel [spot]` - Reclaim your spot, unclaim a spot, or cancel staff.\n"
            "`/parking_help` - Detailed guide on rules and blackout times."
        ),
        inline=False
    )

    # Lates Section
    embed.add_field(
        name="🍱 Late Plates",
        value=(
            "`/late_me` - Request a late (Temporary or Permanent).\n"
            "`/view_lates` - See lates for your house group.\n"
            "`/my_lates` - View all your active late requests.\n"
            "`/clear_late` - Remove a specific late request."
        ),
        inline=False
    )

    # Movie Section (Updated to all Slash)
    embed.add_field(
        name="🎬 Movie Tracking",
        value=(
            "`/watch` - Start a session (Visible to everyone).\n"
            "`/where` - See what is playing now (Private)."
        ),
        inline=False
    )

    # Meals Section (Assuming these will eventually be slash too)
    embed.add_field(
        name="🍽️ Meal Schedule",
        value=(
            "`/today` - Automatically shows today's Lunch & Dinner.\n"
        ),
        inline=False
    )

    embed.set_footer(text="Pro-tip: Slash commands show you exactly what to type as you go!")

    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv('DISCORD_TOKEN'))
import time
import discord
from discord.ext import commands
from supabase import create_client, Client

# --- 1. CONFIGURATION ---
# Replace these with your actual credentials
TOKEN = 'YOUR_DISCORD_BOT_TOKEN'
SUPABASE_URL = 'YOUR_SUPABASE_URL'
SUPABASE_KEY = 'YOUR_SUPABASE_KEY'

# --- 2. INITIALIZATION ---
# Intents are required by Discord to read message content
intents = discord.Intents.default()
intents.message_content = True

# Initialize the bot instance FIRST so the @bot decorators work
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize the Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- 3. BOT EVENTS & COMMANDS ---

@bot.event
async def on_ready():
    print(f'System Online: Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


@bot.command(name="audit")
async def audit_latency(ctx):
    """Measures Gateway, REST, and Database latency in one sequence."""

    # 1. Gateway Latency (Heartbeat)
    gateway_lat = round(bot.latency * 1000)

    # 2. Database Latency (Supabase)
    db_start = time.perf_counter()
    try:
        # Testing connection speed by hitting the parking table directly
        supabase.table("parking").select("*", count='exact').limit(1).execute()
        db_end = time.perf_counter()
        db_lat = round((db_end - db_start) * 1000)
        db_status = f"{db_lat}ms"
    except Exception as e:
        db_status = f"Error: {type(e).__name__}"
        db_lat = 0

    # 3. REST API Latency (Round-trip)
    rest_start = time.perf_counter()
    msg = await ctx.send("⚙️ Auditing system performance...")
    rest_end = time.perf_counter()
    rest_lat = round((rest_end - rest_start) * 1000)

    # 4. Displaying Results
    embed = discord.Embed(
        title="🛰️ System Audit",
        description="Performance check for database and API routing.",
        color=discord.Color.blue()
    )
    embed.add_field(name="Gateway (WS)", value=f"`{gateway_lat}ms`", inline=True)
    embed.add_field(name="REST API", value=f"`{rest_lat}ms`", inline=True)
    embed.add_field(name="Supabase DB", value=f"`{db_status}`", inline=True)

    total_latency = gateway_lat + rest_lat + db_lat
    embed.set_footer(text=f"Total perceived delay: ~{total_latency}ms")

    await msg.edit(content=None, embed=embed)


@bot.command(name="spots")
async def check_spots(ctx):
    """Standard parking check command pulling live from the database."""
    db_start = time.perf_counter()
    try:
        response = supabase.table("parking").select("*").execute()
        db_lat = round((time.perf_counter() - db_start) * 1000)
        await ctx.send(f"✅ Found {len(response.data)} spots currently open. (Query took {db_lat}ms)")
    except Exception as e:
        await ctx.send(f"❌ Database error: {e}")


# --- 4. EXECUTION ---
if __name__ == "__main__":
    bot.run(TOKEN)
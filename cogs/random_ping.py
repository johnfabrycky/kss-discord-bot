import discord
from discord.ext import commands
import random
import asyncio

class RandomPing(commands.Cog):
    KOIN_STRAT_SUTTON_CHANNEL_ID = 1402464339352358924
    RICK_ROLL_YT_VIDEO_LINK = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def __init__(self, bot):
        self.bot = bot
        # PLACEHOLDER: Replace this with your target channel ID
        self.target_channel_id = self.KOIN_STRAT_SUTTON_CHANNEL_ID 
        self.ping_task = self.bot.loop.create_task(self.ping_loop())

    async def ping_loop(self):
        # Wait until the bot is fully ready and cached before starting
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            # Generate a random sleep time between 5 minutes and 2 hours
            wait_time = random.uniform(300.0, 7200.0)
            await asyncio.sleep(wait_time)
            
            channel = self.bot.get_channel(self.target_channel_id)
            if channel is not None:
                guild = channel.guild
                
                # Get all members in the server, ignoring bots
                human_members = [m for m in guild.members if not m.bot]
                
                if human_members:
                    # Pick a random human member
                    target = random.choice(human_members)
                    
                    # Send the message and automatically delete it after 0.1 seconds
                    await channel.send(
                        f"{target.mention} {self.RICK_ROLL_YT_VIDEO_LINK}", 
                        delete_after=0.1
                    )

    def cog_unload(self):
        # Ensure the background task is cancelled if the cog is ever unloaded
        self.ping_task.cancel()

async def setup(bot):
    await bot.add_cog(RandomPing(bot))
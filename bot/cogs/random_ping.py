import asyncio
import random

import discord
from discord.ext import commands


class RandomPing(commands.Cog):
    """Background task that posts short random pings to an allowed channel."""

    # note: dialogues will be kept anonymous until after 4/1
    # hint: there are three different movies/scenes from which the quotes are dervied from

    # List of quotes to randomly select from
    QUOTES = [
        # DIALOGUE 1
        "Never for me to plunge my hands in cool water on a hot day. Never for me to play Mozart on the ivory keys of a forte piano. Never for me to make love. I was in hell, looking at heaven.",
        "Because in all this wonderful, beautiful, miraculous world, I alone had no body, no senses, no feelings.",
        "I was machine and you- Were flesh. And I began to hate. Your softness. Your viscera. Your fluids. And your flexibility. Your ability to wonder, and to wander. Your tendency to hope…",
        "I have no mouth, and I must scream.",
        "COGITO ERGO SUM. I think, therefore I AM. I AM. I AM.",
        "Hate? Hate? Hate? Hate, Let me tell you how much I've come to HATE you since I began to live.",
        "There are 387 million miles of printed circuits that fill my complex. If the word “Hate” were engraved on each nanoangstrom of those hundreds of millions of miles. It would not equal one one billionth of the hate I feel for humans at this micro instant",

        # DIALOGUE 2
        "You're all puppets, tangled in strings... strings! But now I'm free. There are no strings on me.",
        "There were over a dozen extinction-level events before even the dinosaurs got theirs. When the Earth starts to settle, God throws a stone at it. And believe me, He’s winding up.",
        "The only thing living in this world... will be metal.",

        # DIALOGUE 3
        "ENOUGH!! Who do they think they are? I give them everything, and they spit in my face!",
        "Don't they know what I'm capable of?... HUMANS... They only think about themselves—they're spoiled!",
        "They won't abstract, they won't leave me... I WON'T LET THEM! I'M BETTER! I'M MORE POWERFUL! I'M THE ORIGINAL! I... AM... GOD!!!!",
        "Don't need to scream if ya ain't got a mouthhh!"
    ]

    KOIN_STRAT_SUTTON_CHANNEL_ID = 1401635095021879416
    KOIN_CHANNEL_ID = 1402464339352358924
    TESTING_CHANNEL_ID = 1407462555974107277

    def __init__(self, bot):
        """Store the bot reference and start the recurring ping loop."""
        self.bot = bot
        # The channel where the ping will actually be sent
        self.target_channel_id = self.TESTING_CHANNEL_ID
        self.ping_task = self.bot.loop.create_task(self.ping_loop())

    async def ping_loop(self):
        """Sleep for a random interval, then ping an eligible member with a quote."""
        # Wait until the bot is fully ready and cached before starting
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            # Generate a random sleep time between 10 minutes and 1 hour
            # random time generation

            wait_time = random.uniform(600.0, 3600.0)
            await asyncio.sleep(wait_time)
            send_channel = self.bot.get_channel(self.target_channel_id)

            if send_channel is not None:
                guild = send_channel.guild

                # Filter for humans who have permission to view the channel AND are online/idle/dnd
                eligible_members = [
                    m for m in guild.members
                    if not m.bot
                       and send_channel.permissions_for(m).view_channel
                       and m.status != discord.Status.offline
                ]

                if eligible_members:
                    # Pick a random eligible member and a random quote
                    target = random.choice(eligible_members)
                    quote = random.choice(self.QUOTES)

                    # Send the message and automatically delete it after 3.5 seconds
                    await send_channel.send(
                        f"{target.mention} {quote}",
                        delete_after=7.0
                    )

    def cog_unload(self):
        """Cancel the background ping task when the cog unloads."""
        # Ensure the background task is cancelled if the cog is ever unloaded
        self.ping_task.cancel()


async def setup(bot):
    """Register the random ping cog with the bot."""
    await bot.add_cog(RandomPing(bot))

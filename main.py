"""Thin runtime entrypoint for the Discord bot."""

import os

from bot.app import bot
from bot.web.keep_alive import keep_alive

if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv("DISCORD_TOKEN"))

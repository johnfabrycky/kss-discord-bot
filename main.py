"""Thin runtime entrypoint for the Discord bot."""

import os
import logging
from bot.app import bot
from bot.web.keep_alive import keep_alive

if __name__ == "__main__":
    # 1. Setup the logger before anything else starts
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
    )

    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(logging.DEBUG)  # Set to DEBUG for the handshake details
    discord_logger.addHandler(handler)

    # 2. Start the web server
    keep_alive()

    # 3. Run the bot
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("FATAL: DISCORD_TOKEN is missing from environment variables!")
    else:
        bot.run(
            token, log_handler=None
        )  # We set log_handler=None because we manually set it above

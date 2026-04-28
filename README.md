# KSS Discord Bot

A multi-functional Discord bot designed to automate community scheduling and operations for the KSS community.

[![Uptime Robot status](https://img.shields.io/uptimerobot/status/m802769392-700b320fddc46141dabd5b77)](https://stats.uptimerobot.com/xcdwYvPfdq)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/johnfabrycky/kss-discord-bot)

## 🚀 Features

This bot provides a suite of tools to streamline daily operations and community interactions:

- **Parking Management**: A comprehensive system for residents and staff to manage parking spots.
    - View real-time parking availability.
    - Offer and claim resident, guest, and staff spots.
    - Cancel existing offers and reservations.
- **Meal Coordination**:
    - Register temporary or permanent late plates for meals.
    - View the daily meal schedule.
    - Automated handling of academic breaks and rotating menus.
- **Feedback System**:
    - A direct channel for users to provide feedback to the development team.

## ⚙️ How It Works

The bot is built with a modular architecture that separates the command handling from the business logic. Here’s a look
at the data flow for two key features:

### Parking Management

The parking system uses a Supabase backend to manage all parking-related data. When a user issues a command like
`/offer_spot`, the bot:

1. Receives the interaction through the `parking` cog.
2. Validates the user's input and calls the `parking_service`.
3. The service then interacts with the Supabase database to create a new parking offer, ensuring there are no conflicts
   with existing reservations.
4. The result is returned to the cog, which formats a user-friendly response.

### Meal and Late Plate Coordination

The bot manages meal schedules and late plate requests by reading from and writing to a Supabase database. For example,
the `/today` command:

1. Is received by the `meals` cog.
2. The cog calls the `meals_service` to fetch the current day's menu.
3. The service queries the Supabase database, which stores the rotating meal schedule.
4. The menu is returned to the cog and displayed to the user.

The bot also handles dynamic data, such as reading from a `permanent_lates.json` file to manage recurring late plate
requests.

## 🛠️ Tech Stack

- **Backend**: Python, using the `discord.py` library for Discord API interaction.
- **Database**: Supabase (PostgreSQL) for all data storage.
- **Deployment**: Hosted on Render, with uptime monitoring from UptimeRobot.
- **Architecture**: The bot follows a modular, object-oriented design, with a clear separation between the
  command-handling layer (cogs) and the business logic layer (services).

## 🖼️ Visuals

*(Placeholder for screenshots or GIFs of the bot in action)*

## 📡 Deployment

For detailed instructions on how to deploy the bot, both locally and on the cloud, please see
the [Deployment Guide](docs/DEPLOYMENT.md).

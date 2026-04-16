# Architecture

This document provides a high-level overview of the Discord bot's architecture.

## Directory Structure

The project is organized into the following key directories:

- **`bot/`**: This is the main application directory containing the core logic.
    - **`cogs/`**: This directory holds the different modules of the bot, each representing a "cog" or a collection of
      related commands and features (e.g., `parking`, `meals`). Cogs are responsible for handling user interactions,
      parsing commands, and responding to users. They should not contain complex business logic.
    - **`services/`**: This directory contains the business logic for each feature. Services are responsible for
      interacting with the database and performing the core operations of the bot. They are called by the cogs and
      should not directly interact with the Discord API.
- **`tests/`**: This directory contains unit and integration tests for the bot, ensuring that the code is working as
  expected.

## Data Flow

The data flow for a typical command follows these steps:

1. A user issues a slash command in Discord.
2. The corresponding cog in the `cogs/` directory receives the interaction.
3. The cog validates the input and calls the appropriate service in the `services/` directory to perform the requested
   action.
4. The service interacts with the database (e.g., Supabase) to fetch or modify data.
5. The service returns the result to the cog.
6. The cog formats the result into a user-friendly response and sends it back to Discord.

This separation of concerns makes the bot easier to maintain and test, as the business logic is decoupled from the
Discord-facing components.

# Deployment & Setup Guide

This guide provides two paths for deploying the bot:

* **Cloud Deployment (Recommended):** The easiest way to get started. This involves forking the repository on GitHub and deploying directly to a cloud service like Render without needing to run any code on your own machine.
* **Local Development:** For users who want to run the bot on their own computer for testing or development purposes.

---

## Cloud Deployment (via Fork)

This method allows you to set up and run the bot without cloning the repository to your local machine.

### Step 1: Fork the Repository
Click the **Fork** button at the top-right of the GitHub repository page. This will create a personal copy of the project under your own GitHub account.

### Step 2: Set Up External Services
You will need credentials from **Discord** and **Supabase**.

#### 1. Discord Application
1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Click **New Application** and give it a name.
3.  Navigate to the **Bot** tab.
4.  Under **Privileged Gateway Intents**, enable the **Server Members Intent**. This is required for the bot to see member roles.
5.  Click **Reset Token** to generate a new bot token. **Copy this token immediately**; you will need it for your environment variables.

#### 2. Supabase Database:**
1. In your Supabase Dashboard, create a new project.
2. Once the project is ready, navigate to the **SQL Editor** from the sidebar.
3. Go to **Project Settings > Database**. Under **Connection string**, copy the **URI**. You will need this for the `SUPABASE_DB_URL` environment variable.
4. Go to **Project Settings > API**. Copy the **Project URL** and the **`service_role` Key**. You will need these for the `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` environment variables.
5. **Note:** The database tables will be created automatically when the bot starts for the first time.

### Step 3: Customize Core Bot Logic
This is a critical step. The bot's core business logic is defined in `bot/config.py`. You must edit this file in your forked repository to match your server's specific needs.

1.  Navigate to the `bot/config.py` file in your forked repo and click the **Edit** (pencil) icon.
2.  Carefully review and update the following sections:
    * `HOUSE_ROLE_CONFIG` and `LATES_VIEW_GROUPS`: Update the role names and visibility rules. **Note:** Role names must be lowercase and match the names of the roles in your Discord server.
    * `PERMIT_SPOTS` and `STAFF_SPOTS`: Define the parking spot numbers for your community.
    * `STAFF_PARKING_BLACKOUTS`: Adjust the blackout times for staff parking.
3.  **Commit the changes** directly to your main branch.

### Step 4: Deploy to Render
This project is configured for easy deployment on [Render](https://render.com/).

1.  On the Render dashboard, click **New > Web Service**.
2.  Connect your GitHub account and select your **forked repository**.
3.  Render will detect the `render.yaml` file and pre-fill most settings.
4.  Under **Environment**, you must add the environment variables from the `.env.example` file (e.g., `DISCORD_TOKEN`, `GUILD_ID`, `SUPABASE_URL`) using the credentials gathered in Step 2.
5.  Click **Create Web Service**. Render will automatically build and deploy your bot.

### Step 5: Invite the Bot and Keep it Alive
1.  **Invite the Bot:** In the Discord Developer Portal, go to **OAuth2 > URL Generator**. Select the `bot` and `applications.commands` scopes, then grant it "Send Messages", "Embed Links", and "Read Message History" permissions. Use

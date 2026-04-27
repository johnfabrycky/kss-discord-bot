# Deployment Guide

This guide explains how to deploy and run the Discord bot, both locally for development and on the cloud for production.

## Local Development Setup

### 1. Prerequisites

- Python 3.10 or higher
- A Discord bot token
- A Supabase project for the database

### 2. Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/your-repo-name.git
   cd your-repo-name
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the root of the project and add the following variables:
   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_KEY=your_supabase_service_key
   ```
   You can find the Supabase URL and service key in your Supabase project settings.

### 3. Running the Bot

Once the setup is complete, you can run the bot using the following command:

```bash
python main.py
```

The bot should now be online and ready to respond to commands in your Discord server.

---

## Cloud Deployment (Render)

### 1. Prerequisites

- A [Supabase](https://supabase.com/) account with access to the project's organization.
- A [Render](https://dashboard.render.com/) account.
- A [Healthchecks.io](https://healthchecks.io/) account for monitoring cron jobs.
- An [UptimeRobot](https://dashboard.uptimerobot.com/) account for keeping the service alive.

### 2. Setup

1. **Create a new Web Service on Render:**
    - Go to the Render dashboard and click "New Web Service".
    - Connect your GitHub account and select the repository for the bot.
    - Set the **Start Command** to `python main.py`.
    - Choose the free tier for hobby projects.

2. **Configure Environment Variables:**
   In the "Environment" section of your Render service, add the following variables:
    - `DISCORD_BOT_TOKEN`: Your Discord bot token.
    - `SUPABASE_URL`: Your Supabase project's API URL.
    - `SUPABASE_SERVICE_KEY`: Your Supabase project's service key.
    - `HEALTHCHECK_URL`: The URL for your "Midnight Cleanup" check from Healthchecks.io.

3. **Deploy the Bot:**
    - Go to the "Events" tab and click "Manual Deploy" -> "Deploy latest commit".
    - Monitor the logs to ensure the bot builds and starts successfully.

4. **Set up Uptime Monitoring:**
    - In Render, find the public URL for your service (e.g., `your-bot.onrender.com`).
    - In UptimeRobot, create a new monitor and set the "URL to monitor" to your Render service's URL.
    - Set the monitor interval to 5 minutes to keep the free service from spinning down.

Your bot is now deployed and will be kept online by UptimeRobot.

---

## 🚨 Troubleshooting

First, go to the [Render](https://dashboard.render.com/) page for the Discord Web Bot, go to Logs, and see if there are
any error logs that
indicate why the service may have gone down. If there are, use those to troubleshoot. If you lack the expertise
to fix the errors, you may at least be able to identify the functions that are causing issues and create a temporary
PR to remove that functionality so that the bot will function properly while the issue can be resolved.

If there are no error messages in the logs, find the monitor link (see "How to host the bot" below), and open
the link in a new tab. Wait for it to build properly. Once you can refresh the monitor link and there are no
building messages, but it just says "I'm alive", that indicates the service is back up.

Sometimes down events just happen, and often they can be easily resolved just by pinging the monitor link.

# Deployment & Setup Guide

This guide provides comprehensive instructions for setting up and deploying the bot, from a local development environment to a production cloud service.

## 1. Prerequisites

Before you begin, ensure you have the following:

- Python 3.8 or higher.
- A Discord account with permissions to create applications and add bots to a server.
- A free [Supabase](https://supabase.com/) account for the database.
- [Git](https://git-scm.com/downloads) installed on your machine.

## 2. Local Setup & Configuration

### Step 2.1: Clone the Repository

First, clone the project repository to your local machine:

```bash
git clone https://github.com/johnfabrycky/kss-discord-bot.git
cd kss-discord-bot
```

### Step 2.2: Install Dependencies

It's highly recommended to use a virtual environment to manage project dependencies.

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate

# Install the required packages
pip install -r requirements.txt
```

The bot should now be online and ready to respond to commands in your Discord server.

---

## Cloud Deployment (Render)

### 1. Prerequisites

- A [Supabase](https://supabase.com/) account with access to the project's organization.
- A [Render](https://dashboard.render.com/) account with a Web Service connected to your bot's GitHub repository.
- A [Healthchecks.io](https://healthchecks.io/) account for monitoring cron jobs.
- An [UptimeRobot](https://dashboard.uptimerobot.com/) account for keeping the service alive.

### 2. Ongoing Deployment

1. **Automatic Deploys:**
   By default, Render will automatically deploy any new commits pushed to your main branch.

2. **Manual Deploys:**
   If you need to redeploy an existing commit (e.g., after changing an environment variable), you can trigger a manual
   deploy from the Render dashboard by going to the "Events" tab and clicking "Manual Deploy" -> "Deploy latest commit".

3. **Configure Environment Variables:**
   Consult the env.example file to see the environment variables to add in the "Environment" section of your Render
   service.

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

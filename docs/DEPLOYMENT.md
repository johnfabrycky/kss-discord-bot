Deployment & Setup Guide
This guide provides two paths for deploying the bot:
•
Cloud Deployment (Recommended): The easiest way to get started. This involves forking the repository on GitHub and deploying directly to a cloud service like Render without needing to run any code on your own machine.
•
Local Development: For users who want to run the bot on their own computer for testing or development purposes.
Cloud Deployment (via Fork)
This method allows you to set up and run the bot without cloning the repository to your local machine.
Step 1: Fork the Repository
Click the "Fork" button at the top-right of the GitHub repository page. This will create a personal copy of the project under your own GitHub account.
Step 2: Set Up External Services
You will need credentials from Discord and Supabase.
1.
Discord Application:
◦
Go to the Discord Developer Portal.
◦
Click New Application and give it a name.
◦
Navigate to the Bot tab.
◦
Under Privileged Gateway Intents, enable the Server Members Intent. This is required for the bot to see member roles.
◦
Click Reset Token to generate a new bot token. Copy this token immediately; you will need it for your environment variables.
2.
Supabase Database:
◦
In your Supabase Dashboard, create a new project.
◦
Once the project is ready, navigate to the SQL Editor from the sidebar.
◦
The scripts/ directory in this repository contains several .sql files. You must run these to create the necessary database tables. Open each file, copy its contents, and execute it in the Supabase SQL Editor.
◦
After running the scripts, go to Project Settings > API. Copy the Project URL and the service_role Key. You will need these for your environment variables.
Step 3: Customize Core Bot Logic
This is a critical step. The bot's core business logic is defined in bot/config.py. You must edit this file in your forked repository to match your server's specific needs. You can do this directly on the GitHub website.
Navigate to the bot/config.py file in your forked repo and click the "Edit" (pencil) icon. Carefully review and update the following sections:
•
HOUSE_ROLE_CONFIG and LATES_VIEW_GROUPS: Update the role names and visibility rules for the late plate system. The role names must be lowercase and match the names of the roles in your Discord server.
•
PERMIT_SPOTS and STAFF_SPOTS: Define the parking spot numbers for your community.
•
STAFF_PARKING_BLACKOUTS: Adjust the blackout times for staff parking.
Commit the changes directly to your main branch.
Step 4: Deploy to Render
This project is configured for easy deployment on Render.
1.
On the Render dashboard, click New > Web Service.
2.
Connect your GitHub account and select your forked repository.
3.
Render will detect the render.yaml file and pre-fill most settings.
4.
Under Environment, you must add the environment variables from the .env.example file (DISCORD_TOKEN, GUILD_ID, SUPABASE_URL, etc.) using the credentials you gathered in Step 2.
5.
Click Create Web Service. Render will automatically build and deploy your bot.
Step 5: Invite the Bot and Keep it Alive
1.
Invite the Bot: In the Discord Developer Portal, go to OAuth2 > URL Generator. Select the bot and applications.commands scopes, then grant it "Send Messages", "Embed Links", and "Read Message History" permissions. Use the generated URL to add the bot to your server.
2.
Keep Alive (Free Tier): Render's free web services spin down after 15 minutes of inactivity. To keep the bot online 24/7, use a free service like UptimeRobot to create an HTTP(s) monitor that pings your Render service URL (e.g., your-bot.onrender.com) every 5-10 minutes.
Local Development Setup (Optional)
Follow these steps if you want to run the bot on your own computer for development or testing.
Step 1: Prerequisites
•
All prerequisites from the Cloud Deployment section.
•
Git installed on your machine.
Step 2: Clone and Configure
1.
Clone the repository:
Shell Script
git clone https://github.com/johnfabrycky/kss-discord-bot.git
cd kss-discord-bot
2.
Install dependencies in a virtual environment:
Shell Script
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
pip install -r requirements.txt
3.
Set up environment variables: Copy .env.example to a new file named .env and fill in the required values.
4.
Run the bot:
Shell Script
python main.py
🚨 Troubleshooting
If the bot fails to start, check the Logs tab in your Render service dashboard. This will usually contain error messages that can help you diagnose the problem. Common issues include:
•
Incorrect environment variables.
•
Forgetting to enable the Server Members Intent in the Discord Developer Portal.
•
Errors in the bot/config.py file.
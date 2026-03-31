# KSS Discord Bot

A multi-purpose utility bot for the KSS community, managing parking, meal schedules, late plates, and social movie
sessions.

# FOR APRIL FOOLS WE ARE GOING TO RANDOMLY PING SOMEONE EVERY 5-120 MINUTES FOR THE WHOLE 24 HOURS

## 🚀 Active Functionality

### 🚗 Parking Utility

* `/parking_status` — View all currently available resident and guest spots.
* `/parking_help` — View detailed instructions on parking instructions and how to use the parking commands.
* `/offer_spot` — List your resident spot as available for a specific timeframe.
* `/claim_spot` — Claim an offered spot for a specific time window.
* `/claim_staff` — Claim a staff spot for a specific time window.
* `/cancel` — Release a spot you previously claimed or cancel an offer you made.

### 🍱 Late Plates

* `/late_me` — Register a temporary or permanent late plate request.
* `/view_lates` — See all lates for your house group (Koinonian, Stratfordite, or Suttonite).
* `/my_lates` — Check your own active late requests.
* `/clear_late` — Remove a registered late.

### 🍴 Meal Schedule

* `/today` — Shows the Lunch and Dinner menu for the current UIUC academic week.
* Includes automated logic for UIUC Spring Break and 4-week rotating menus.

[//]: # (### 🎬 Movie Tracking)

[//]: # (* `/watch` — Publicly announce a movie session with location and duration.)

[//]: # (* `/where` — Privately check which movies are currently playing and where.)

[//]: # (### ⚖️ Shifts)

[//]: # (* `/offer_shift` — Put up a shift for swap or pay)

[//]: # (* `/view_market` — See current shifts being offered)

[//]: # (* `/claim_shift` — Take a shift)

[//]: # (* `/swap_shift` — Propose a swap with someone else's shift)

[//]: # (* `/my_shifts` — View your shifts)

[//]: # (* `/cancel_shift` — Take down a shift you offered that hasn't been claimed yet )

### 📝 Feedback

* `/feedback` — Offer feedback to the Felipe developers

---

## 🛠 To-Implement

## Add suggestions here

---

## 🌲 Development & Branching

The 'main' branch is PROTECTED. All new features or bug fixes must be developed on a dedicated branch and merged via
Pull Request.

**Contribution Workflow:**

1. Branching: For any improvements to current features, use a pre-existing branch (not main).
2. Create a new branch if building a new cog (e.g., git checkout -b feature-name).
2. Pull Requests: Submit a PR to 'main' once work is verified.
3. If you wish to preview the behavior of the PR, add [render preview] to the PR title.
   Then, make sure to deploy the felipe-dev bot on render and invite it to the server.
   Once done testing the bot, kick it from the server so that it's commands don't continue to appear alongside the
   commands for felipe-prod.
   Remember that the felipe-dev bot currently does not have an associated uptime robot checker so it will spin down
   after 15 minutes of inactivity.
4. Deployment: Merges occur during SCHEDULED MAINTENANCE to ensure stability.

---

## 🔧 Maintenance

**Database Maintenance**

Most persistent data is stored on [Supabase](https://supabase.com/dashboard/org/ejwmbmbydveoeffdnpox). To be added to
the group contact John Fabrycky (johnf8@illinois.edu) or
Trent Heller (trentheller25@illinois.edu). To have write access to the databases, ask to be given admin privilege.

The meals will need to be updated at least on a semesterly basis. It is simply under the "meals" table in Supabase.

The unclaimed parking spots for each semester should be marked in Supabase by finding the entry in the parking_spots
table and toggling the is_guest value to true. The is_guest value should be false for all claimed parking spots as well
as the staff spots (denoted as 998 and 999 in Supabase).

**Code Maintenance/Improvement**

There should be no need to alter the code to maintain the bot. Code alterations should only be necessary
for improving/changing the functionality, but not for maintaining the current use cases.

**Bot Hosting**

The bot is hosted on [Render](https://dashboard.render.com/) free tier, and is monitored via
[Uptime Robot](https://dashboard.uptimerobot.com/monitors) with checks every 5 minutes to keep the service up.
On free tier, the render service cannot be accessed by multiple accounts so John Fabrycky currently is the only person
with the ability to host the bot. This privilege should be soon given to others, such as future RAs of BHM, and more
importantly
the Koin/Strat/Sutton google profiles (ask an RA of BHM if you need the email addresses).

---

## 📡 How to host the bot

1. Create a free account on [Supabase](https://supabase.com/). Request to join "johnfabrycky's Org" on [Supabase](https://supabase.com/dashboard/org/ejwmbmbydveoeffdnpox) and to be
   given admin privileges so that you have the authority to perform CRUD operations on the database.
2. Create a free account with [Healthchecks.io](https://healthchecks.io/projects/2cbc36e8-0a97-4fbb-b655-0016d22acf42/checks/).
   Ask the current owner (John Fabrycky as of 3/31/26) to give you team access and if necessary 
    <img width="591" height="846" alt="image" src="https://github.com/user-attachments/assets/50575de7-1281-4d6d-9f9d-5c657b35b6ea" />
   transfer ownership to you.
5. Create a free account with [Uptime Robot](https://dashboard.uptimerobot.com/monitors).
6. Create a free account on [Render](https://dashboard.render.com/), go to the home page and select "New Web Service"
   under "Web Services"
7. Choose "Github" as your provider
8. Find the "felipe" git repository and select it.
9. Use most of the default entries. For Start Command, replace the default with "python main.py".
10. Use the free tier, under "For hobby projects".
11. Under environment, you need to add three environment variables. They will be named DISCORD_TOKEN,
   SUPABASE_SERVICE_KEY, HEALTHCHECK_URL, and SUPABASE_URL.
   Under the environment tab, click edit on the "Environment Variables" Section. In the bottom left of the box,
   click "+Add Variable". Where the placeholder text reads "NAME_OF_VARIABLE", put the variable name. Do this
   for each of the variables named above. 
    1. DISCORD_TOKEN - First option: find whoever is currently hosting the bot (John Fabrycky as of 3/31/26) and ask them to share the token with you.
       Otherwise, go to the discord developer [portal](https://discord.com/developers/home). Select the Felipe bot, then
       select
       the Bot tab, then under Token, press Reset Token. ONLY do this if you are unable to contact the person who
       currently
       has the Token because it will invalidate the current Token. Place the token in the box to the right of where
       you put the name "DISCORD_TOKEN" and save.
    2. HEALTHCHECK_URL - On the "Midnight Cleanup" Healthcheck in Healthchecks.io, under "How to Ping" on the main page,
       click on the URL that begins with "https://" to copy it to your clipboard. Then enter that URL into Render associated
       with HEALTHCHECK_URL in the environment tab.
    4. SUPABASE_URL - Go to Supabase and select the "kss discord bot". Then go to Integrations -> DATA API -> API URL.
       Copy
       the API URL. Paste it in the appropriate box corresponding to "SUPABASE_URL" in the Render environment page.
    5. SUPABASE_SERVICE_KEY - On Supabase, go to Settings -> Configuration -> API Keys, then under "Secret Keys", find
       the
       default key, press the "copy" icon to put it on your clipboard, then return to render environment and paste it into the appropriate box.
12. Select the Events tab, then find the "Manual Deploy" button, click it and select "Deploy latest commit".
13. Go to Monitor -> Logs. It should build in under 5 minutes, with the success message "==> Your service is live 🎉",
    and no error messages.
14. Go to Events. ON the top bar towards the bottom there will be a purple link with a copy symbol next to it, that
    ends in "onrender.com".
    <img width="1611" height="541" alt="Felipe_ping_instr_picture" src="https://github.com/user-attachments/assets/8f8181ee-beb3-49f4-bdcf-f808ed7aabc3" />
    Copy the link (a.k.a monitor) to your clipboard.
15. On UptimeRobot, create a new Monitor. Under "URL to monitor", enter the monitor from your clipboard. Under
    "How will we notify you?", select your preferred means of notification for a down event. Under "Monitor interval",
    leave it at 5m. Then click "Create monitor".
16. Congratulations, you have fully configured the discord bot to run on a hosted service for free 🎉🎺🎉🎺.

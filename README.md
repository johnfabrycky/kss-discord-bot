# KSS Discord Bot

A multi-purpose utility bot for the KSS community, managing parking, meal schedules, late plates, and social movie sessions.

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

### 🎬 Movie Tracking
* `/watch` — Publicly announce a movie session with location and duration.
* `/where` — Privately check which movies are currently playing and where.

### ⚖️ Shifts
* `/offer_shift` — Put up a shift for swap or pay
* `/view_market` — See current shifts being offered
* `/claim_shift` — Take a shift
* `/swap_shift` — Propose a swap with someone else's shift
* `/my_shifts` — View your shifts
* `/cancel_shift` — Take down a shift you offered that hasn't been claimed yet 

### 📝 Feedback
* `/feedback` — Offer feedback to the Felipe developers
---

## 🛠 To-Implement

## Add suggestions here

---

## 🌲 Development & Branching

The 'main' branch is PROTECTED. All new features or bug fixes must be developed on a dedicated branch and merged via Pull Request.

**Contribution Workflow:**
1. Branching: For any improvements to current features, use a pre-existing branch (not main). 
2. Create a new branch if building a new cog (e.g., git checkout -b feature-name).
2. Pull Requests: Submit a PR to 'main' once work is verified.
3. If you wish to preview the behavior of the PR, add [render preview] to the PR title. 
Then, make sure to deploy the felipe-dev bot on render and invite it to the server. 
Once done testing the bot, kick it from the server so that it's commands don't continue to appear alongside the commands for felipe-prod. 
Remember that the felipe-dev bot currently does not have an associated uptime robot checker so it will spin down after 15 minutes of inactivity. 
4. Deployment: Merges occur during SCHEDULED MAINTENANCE to ensure stability.


---
## 🔧 Maintenance

**Database Maintenance**

Most persistent data is stored on [Supabase](https://supabase.com/dashboard/org/ejwmbmbydveoeffdnpox). To be added to the group contact John Fabrycky (johnf8@illinois.edu) or 
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
with the ability to host the bot. This privilege should be soon given to others, such as future RAs of BHM, and more importantly
the Koin/Strat/Sutton google profiles (ask an RA of BHM if you need the email addresses). 

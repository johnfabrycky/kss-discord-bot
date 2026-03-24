# KSS Discord Bot

A multi-purpose utility bot for the KSS community, managing parking, meal schedules, late plates, and social movie sessions.

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

Most persistent data is stored on Supabase. To be added to the group contact John Fabrycky (johnf8@illinois.edu) or 
Trent Heller (trentheller25@illinois.edu). To have write access to the databases, ask to be given admin privilege. 

The meals will need to be updated at least on a semesterly basis. It is simply under the "meals" table in Supabase.

**Code Maintenance/Improvement**

Currently, the parking spot 46 is set as open inside the parking.py cog. A future improvement would be to remove that and
add a is_free column to the spots table in supabase, and set it to false for all spots that are being rented out by BHM
and to true for any open spots (such as 46 as of 3/3/2026) and the staff spots, which are never rented to residents.

**Bot Hosting**

The bot is hosted on render free tier, and is monitored via uptime robot with checks every 5 minutes to keep the service up.
On free tier, the render service cannot be accessed by multiple accounts so John Fabrycky currently is the only person
with the ability to host the bot. This privilege should be soon given to others, such as future RAs of BHM, and more importantly
the Koin/Strat/Sutton google profiles (i.e. koinonia308@gmail.com, stratford310@gmail.com, suttonhouse2010@gmail.com).
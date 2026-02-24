# KSS Discord Bot

A multi-purpose utility bot for the KSS community, managing parking, meal schedules, late plates, and social movie sessions.

# FOR APRIL FOOLS WE ARE GOING TO RANDOMLY PING SOMEONE EVERY 3-6 MINUTES FOR THE WHOLE 24 HOURS

## 🚀 Active Functionality

### 🚗 Parking Utility
* `/parking_status` — View all currently available resident and guest spots.
* `/offer_spot` — List your resident spot as available for a specific timeframe.
* `/claim_spot` — Claim an offered spot until a specified time.
* `/unclaim_spot` — Relinquish a spot you previously claimed.
* `/reclaim_spot` — For owners to withdraw an offer or prompt a claimer to move.

### 🍱 Late Plates (Current Development)
* `/late_me` — Register a temporary or permanent late plate request.
* `/view_lates` — See all lates for your specific house (Koinonian, Stratfordite, or Suttonite).
* `/my_lates` — Check your own active late requests.
* `/clear_late` — Remove a registered late.
* `/import_koinonia_lates` — (Admin Only) Batch import permanent lates from CSV.

### 🍴 Meal Schedule
* `/today` — Shows the Lunch and Dinner menu for the current UIUC academic week.
* Includes automated logic for UIUC Spring Break and 4-week rotating menus.

### 🎬 Movie Tracking
* `/watch` — Publicly announce a movie session with location and duration.
* `/where` — Privately check which movies are currently playing and where.

---

## 🛠 To-Implement

### Movie Tracking
[ ] View current queue of upcoming movies.

[ ] Remove movies from the queue.

### Meal Schedule
[ ] !meal <week> <day> <type> — Lookup a specific meal in the 4-week rotation.

### Other
[ ] Branding: Beautify the bot profile and finalize documentation.

[ ] Integration: Fully enable and test the Late Plate Cog within the main bot loop.

---

## 🌲 Development & Branching

The 'main' branch is PROTECTED. All new features or bug fixes must be developed on a dedicated branch and merged via Pull Request.

Current Branches:
* main (Production-ready)
* meals
* movies
* parking
* lates
* readme

**Contribution Workflow:**
1. Branching: For any improvements to current features, use a pre-existing branch (not main). Create a new branch if building a new cog (e.g., git checkout -b feature-name).
2. Pull Requests: Submit a PR to 'main' once work is verified.
3. Deployment: Merges occur during SCHEDULED MAINTENANCE to ensure stability.

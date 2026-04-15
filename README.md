# KSS Discord Bot

A multi-purpose utility bot for the KSS community, managing parking, meal schedules, late plates, and social movie
sessions.

[![Uptime Robot status](https://img.shields.io/uptimerobot/status/m802769392-700b320fddc46141dabd5b77)](https://stats.uptimerobot.com/xcdwYvPfdq)

## 📖 Table of Contents

1. [Active Functionality](#-active-functionality)
    * [Parking Utility](#-parking-utility)
    * [Late Plates](#-late-plates)
    * [Meal Schedule](#-meal-schedule)
    * [Feedback](#-feedback)
2. [Deployment](#-deployment)
3. [Troubleshooting](#-troubleshooting)
4. [Maintenance](#-maintenance)
5. [Architecture](docs/ARCHITECTURE.md)
6. [Contributing](docs/CONTRIBUTING.md)
7. [Changelog](docs/CHANGELOG.md)
8. [Security](docs/SECURITY.md)


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

## 📡 Deployment

For detailed instructions on how to deploy the bot, both locally and on the cloud, please see the [Deployment Guide](docs/DEPLOYMENT.md).

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

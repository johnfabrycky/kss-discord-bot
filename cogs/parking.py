import os
from collections import Counter
from datetime import datetime, timedelta

import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks
from flask.cli import load_dotenv
from supabase import create_client

local_tz = pytz.timezone('America/Chicago')
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)


class Parking(commands.Cog):
    DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_choices = [app_commands.Choice(name=d.capitalize(), value=d) for d in DAYS]
    time_choices = [app_commands.Choice(name=f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}",
                                        value=f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}") for i in range(24)]

    def __init__(self, bot):
        self.bot = bot
        self.valid_spots = list(range(1, 34)) + list(range(41, 46))
        self.total_staff_spots = 2

    # --- INTERNAL UTILITIES ---
    def _parse_range(self, s_day, s_time, e_day, e_time):
        now = datetime.now(local_tz).replace(minute=0, second=0, microsecond=0)

        def to_dt(d_str, t_str, reference_date):
            target_day = self.DAYS.index(d_str.lower())
            # Calculate days ahead relative to the reference_date provided
            days_ahead = (target_day - reference_date.weekday() + 7) % 7
            t_obj = datetime.strptime(t_str.strip().upper(), "%I %p").time()

            dt = (reference_date + timedelta(days=days_ahead)).replace(hour=t_obj.hour)

            # If the day is 'today' relative to the reference but the hour passed, push forward
            if days_ahead == 0 and dt < reference_date:
                dt += timedelta(days=7)
            return dt

        # 1. Calculate start relative to NOW
        start = to_dt(s_day, s_time, now)

        # 2. Calculate end relative to the START time
        # This ensures the end is always the FIRST occurrence of that day/time AFTER the start.
        end = to_dt(e_day, e_time, start)

        # 3. Final safety check: if start and end are identical (e.g., Mon 10am to Mon 10am)
        # assume they mean exactly one week later.
        if end == start:
            end += timedelta(days=7)

        duration = end - start
        return start, end, duration

    def _is_blackout(self, start, end):
        """Checks if range hits: Mon-Fri < 5PM or Sun 2AM-2PM."""
        curr = start
        while curr < end:
            d, h = curr.weekday(), curr.hour
            if (d < 5 and h < 17) or (d == 6 and 2 <= h < 14): return True
            curr += timedelta(hours=1)
        return False

    async def initialize_parking_spots(self):
        """Ensures all valid spots are registered in the Supabase parent table."""
        # Define the full list of spots to ensure exist
        all_spot_configs = []

        # Resident spots: 1-33 and 41-45
        for s in self.valid_spots:
            all_spot_configs.append({"spot_number": s, "spot_type": "resident"})

        # Permanent Guest spot: 46
        # all_spot_configs.append({"spot_number": 46, "spot_type": "guest"})

        # Staff spots: 998 and 999
        all_spot_configs.append({"spot_number": 998, "spot_type": "staff"})
        all_spot_configs.append({"spot_number": 999, "spot_type": "staff"})

        try:
            # 'upsert' prevents 'duplicate key' errors by updating if it exists
            # or inserting if it doesn't.
            supabase.table("parking_spots").upsert(
                all_spot_configs,
                on_conflict="spot_number"
            ).execute()
            print("✅ Parking spots table synchronized.")
        except Exception as e:
            print(f"⚠️ Error initializing parking spots: {e}")

    @app_commands.command(name="my_parking", description="View your active offers and reservations")
    async def my_parking(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        now = datetime.now(local_tz)
        iso_now = now.isoformat()

        embed = discord.Embed(
            title="📋 My Parking Activity",
            color=discord.Color.green(),
            timestamp=now
        )

        # 1. Fetch spots the user has OFFERED (where they are the owner)
        # We only care about offers that haven't expired yet
        offers_res = supabase.table("parking_offers") \
            .select("*") \
            .eq("owner_id", user_id) \
            .gt("end_time", iso_now) \
            .execute()

        offer_groups = Counter()
        for off in offers_res.data:
            start = datetime.fromisoformat(off['start_time']).astimezone(local_tz)
            end = datetime.fromisoformat(off['end_time']).astimezone(local_tz)
            # Create a unique key based on the day of week and time (ignoring the specific date)
            time_key = f"**Spot {off['spot_number']}**: {start.strftime('%a %I%p')} — {end.strftime('%a %I%p')}"
            offer_groups[time_key] += 1

        offer_lines = [f"{key} (x{count})" if count > 1 else key for key, count in offer_groups.items()]
        embed.add_field(name="📤 My Offers", value="\n".join(offer_lines) or "No active offers.", inline=False)

        # 2. Fetch spots the user has CLAIMED (Resident, Guest, or Staff)
        claims_res = supabase.table("parking_reservations") \
            .select("*") \
            .eq("claimer_id", user_id) \
            .gt("end_time", iso_now) \
            .execute()

        claim_groups = Counter()

        for c in claims_res.data:
            start = datetime.fromisoformat(c['start_time']).astimezone(local_tz)
            end = datetime.fromisoformat(c['end_time']).astimezone(local_tz)
            spot_label = "Staff Spot" if c['spot_number'] in [998, 999] else f"Spot {c['spot_number']}"
            time_key = f"**{spot_label}**: {start.strftime('%a %I%p')} — {end.strftime('%a %I%p')}"
            claim_groups[time_key] += 1

        claim_lines = [f"{key} (x{count})" if count > 1 else key for key, count in claim_groups.items()]
        embed.add_field(
            name="📥 My Reservations",
            value="\n".join(claim_lines) or "No active reservations.",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="offer_spot", description="List your spot as available")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def offer_spot(self, interaction: discord.Interaction, spot: int,
                         start_day: app_commands.Choice[str], start_time: app_commands.Choice[str],
                         end_day: app_commands.Choice[str], end_time: app_commands.Choice[str],
                         weeks: int = 1):
        if spot not in self.valid_spots:
            return await interaction.response.send_message(f"❌ Spot {spot} is invalid.", ephemeral=True)

        if weeks < 1 or weeks > 12:  # Cap it so someone doesn't book for 5 years
            return await interaction.response.send_message("❌ Please choose between 1 and 12 weeks.", ephemeral=True)

        base_start, base_end, duration = self._parse_range(start_day.value, start_time.value, end_day.value,
                                                           end_time.value)
        user_id = str(interaction.user.id)

        # --- IMMEDIATE VALIDATION ---
        if duration < timedelta(hours=2):
            return await interaction.response.send_message(
                "❌ Offers must be at least **2 hours** long.", ephemeral=True
            )

        all_offers = []

        for i in range(weeks):
            start = base_start + timedelta(weeks=i)
            end = base_end + timedelta(weeks=i)

            existing_check = supabase.table("parking_offers") \
                .select("*") \
                .eq("spot_number", spot) \
                .lt("start_time", end.isoformat()) \
                .gt("end_time", start.isoformat()) \
                .execute()

            if not existing_check.data:
                all_offers.append({
                    "spot_number": spot,
                    "owner_id": user_id,
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat()
                })

            # 1. Prepare data for Supabase
            offer_data = {
                "spot_number": spot,
                "owner_id": user_id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat()
            }

        if not all_offers:
            return await interaction.response.send_message(f"❌ Spot {spot} is already offered during those times.",
                                                           ephemeral=True)

        # 2. Insert into Supabase
        try:
            supabase.table("parking_offers").insert(all_offers).execute()
            recur_msg = f" for the next **{weeks} weeks**" if weeks > 1 else ""
            await interaction.response.send_message(
                f"📢 **Spot {spot}** listed{recur_msg}: {base_start.strftime('%a %I%p')} — {base_end.strftime('%a %I%p')}",
                ephemeral=False
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Database error: {e}", ephemeral=True)

    @app_commands.command(name="claim_spot", description="Reserve a resident or guest spot")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def claim_spot(self, interaction: discord.Interaction, spot: int,
                         start_day: str, start_time: str, end_day: str, end_time: str):
        c_start, c_end, duration = self._parse_range(start_day, start_time, end_day, end_time)

        # --- IMMEDIATE VALIDATION ---
        if duration < timedelta(hours=2):
            return await interaction.response.send_message(
                "❌ Reservations must be at least **2 hours** long.", ephemeral=True
            )

        if duration > timedelta(days=7):
            return await interaction.response.send_message(
                "❌ You cannot reserve a spot for more than **7 days**.", ephemeral=True
            )

        # 2. Fetch spot type from Database
        spot_query = supabase.table("parking_spots").select("is_guest").eq("spot_number", spot).execute()

        if not spot_query.data:
            return await interaction.response.send_message(f"❌ Spot {spot} is not registered in the system.",
                                                           ephemeral=True)

        is_guest_spot = spot_query.data[0]['is_guest']

        # 1. SQL Overlap Check: See if any existing reservation hits this timeframe
        # Logic: (StartA < EndB) AND (EndA > StartB)
        conflict = supabase.table("parking_reservations") \
            .select("*") \
            .eq("spot_number", spot) \
            .lt("start_time", c_end.isoformat()) \
            .gt("end_time", c_start.isoformat()) \
            .execute()

        if conflict.data:
            return await interaction.response.send_message(f"❌ Spot {spot} is already reserved then.", ephemeral=True)

        # 4. Logic: If NOT a guest spot, verify a Resident Offer exists
        target_offer_id = None
        if not is_guest_spot:
            offer = supabase.table("parking_offers") \
                .select("*") \
                .eq("spot_number", spot) \
                .lte("start_time", c_start.isoformat()) \
                .gte("end_time", c_end.isoformat()) \
                .execute()

            if not offer.data:
                return await interaction.response.send_message(
                    f"❌ No resident is offering Spot {spot} for that full window.", ephemeral=True)

            target_offer_id = offer.data[0]['id']

        # 3. Commit Claim
        claim_data = {
            "spot_number": spot,
            "claimer_id": str(interaction.user.id),
            "start_time": c_start.isoformat(),
            "end_time": c_end.isoformat(),
            "offer_id": target_offer_id,
        }
        supabase.table("parking_reservations").insert(claim_data).execute()

        await interaction.response.send_message(f"✅ **Spot {spot}** reserved for {c_start.strftime('%a %I%p')}!",
                                                ephemeral=False)

    @app_commands.command(name="claim_staff", description="Reserve a staff spot")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def claim_staff(self, interaction: discord.Interaction,
                          start_day: app_commands.Choice[str], start_time: app_commands.Choice[str],
                          end_day: app_commands.Choice[str], end_time: app_commands.Choice[str]):

        c_start, c_end, duration = self._parse_range(start_day.value, start_time.value, end_day.value, end_time.value)

        # 1. Blackout Validation
        if self._is_blackout(c_start, c_end):
            return await interaction.response.send_message("❌ Blackout hours active (Mon-Fri < 5PM or Sun 2AM-2PM).",
                                                           ephemeral=True)

        # --- IMMEDIATE VALIDATION ---
        if duration < timedelta(hours=2):
            return await interaction.response.send_message(
                "❌ Reservations must be at least **2 hours** long.", ephemeral=True
            )

        if duration > timedelta(days=7):
            return await interaction.response.send_message(
                "❌ You cannot reserve a spot for more than **7 days**.", ephemeral=True
            )

        # 2. Check Database for overlapping staff claims (Spots 998 and 999)
        try:
            conflict_res = supabase.table("parking_reservations") \
                .select("spot_number") \
                .in_("spot_number", [998, 999]) \
                .lt("start_time", c_end.isoformat()) \
                .gt("end_time", c_start.isoformat()) \
                .execute()

            occupied_spots = [row['spot_number'] for row in conflict_res.data]

            if len(occupied_spots) >= self.total_staff_spots:
                return await interaction.response.send_message("❌ Staff spots are full for this timeframe.",
                                                               ephemeral=True)

            # 3. Assign an available virtual spot ID
            assigned_spot = 998 if 998 not in occupied_spots else 999

            # 4. Commit to Supabase
            claim_data = {
                "spot_number": assigned_spot,
                "claimer_id": str(interaction.user.id),
                "start_time": c_start.isoformat(),
                "end_time": c_end.isoformat(),
                "offer_id": None,
            }

            supabase.table("parking_reservations").insert(claim_data).execute()

            await interaction.response.send_message(
                f"✅ Staff Spot reserved: {c_start.strftime('%a %I%p')} — {c_end.strftime('%a %I%p')}", ephemeral=False)

        except Exception as e:
            await interaction.response.send_message(f"❌ Database error: {e}", ephemeral=True)

    @app_commands.command(name="parking_status", description="View available parking spots")
    async def parking_status(self, interaction: discord.Interaction):
        now = datetime.now(local_tz).replace(minute=0, second=0, microsecond=0)
        # Define the one-week cutoff
        one_week_later = now + timedelta(days=7)

        iso_now = now.isoformat()
        iso_cutoff = one_week_later.isoformat()
        lines = []

        guest_res = supabase.table("parking_spots").select("spot_number").eq("is_guest", True).execute()
        guest_spot_list = [r['spot_number'] for r in guest_res.data]

        # 1. Fetch data: Only get records within the next 7 days
        offers_res = supabase.table("parking_offers") \
            .select("*") \
            .gt("end_time", iso_now) \
            .lt("start_time", iso_cutoff) \
            .execute()

        claims_res = supabase.table("parking_reservations") \
            .select("*") \
            .gt("end_time", iso_now) \
            .lt("start_time", iso_cutoff) \
            .execute()

        # 2. Organize OFFERS (identical to your current logic)
        offers_db = {}
        for row in offers_res.data:
            s = row['spot_number']
            offers_db.setdefault(s, []).append({
                "start": datetime.fromisoformat(row['start_time']).astimezone(local_tz),
                "end": datetime.fromisoformat(row['end_time']).astimezone(local_tz)
            })

        # 3. Organize CLAIMS
        claims_db = {}
        for row in claims_res.data:
            s = row['spot_number']
            claims_db.setdefault(s, []).append({
                "start": datetime.fromisoformat(row['start_time']).astimezone(local_tz),
                "end": datetime.fromisoformat(row['end_time']).astimezone(local_tz)
            })

        # 4. Process Spots
        all_spots = sorted(set(list(offers_db.keys()) + guest_spot_list))

        for s in all_spots:
            if s in guest_spot_list:
                windows = [{"start": now.replace(hour=0), "end": one_week_later}]
            else:
                # Sort and filter offers to ensure they don't exceed the 1-week window
                windows = sorted(offers_db[s], key=lambda x: x['start'])

            spot_claims = sorted(claims_db.get(s, []), key=lambda x: x['start'])
            blocks = []

            for w in windows:
                # Clamp window to exactly 7 days from now
                w_start = max(w["start"], now)
                w_end = min(w["end"], one_week_later)

                if w_start >= w_end:
                    continue

                ptr = w_start
                relevant_claims = [c for c in spot_claims if not (c['end'] <= w_start or c['start'] >= w_end)]

                for c in relevant_claims:
                    c_start = max(c['start'], w_start)
                    if (c_start - ptr) >= timedelta(hours=2):
                        blocks.append((ptr, c_start))
                    ptr = max(ptr, c['end'])

                if (w_end - ptr) >= timedelta(hours=2):
                    blocks.append((ptr, w_end))

            # Status Formatting
            current_claim = next((c for c in spot_claims if c["start"] <= now < c["end"]), None)
            # header = f"🔴 Busy until {current_claim['end'].strftime('%a %I%p')}" if current_claim else "🟢 Available Now"
            if current_claim:
                header = f"🔴 Busy until {current_claim['end'].strftime('%a %I%p')}"
            else:
                # Find the next upcoming claim
                upcoming = next((c for c in spot_claims if c["start"] > now), None)
                next_up = f" (until {upcoming['start'].strftime('%a %I%p')})" if upcoming else ""
                header = f"🟢 Available Now{next_up}"

            detail = " | ".join(
                [f"{'🟢' if b[0] <= now < b[1] else '📅'} {b[0].strftime('%a %I%p')}-{b[1].strftime('%a %I%p')}"
                 for b in blocks])

            lines.append(f"**Spot {s}**: {header}\n└ *Free:* {detail or '❌ Fully Booked'}")

        # 5. Staff Logic (Unchanged but using claims_db)
        is_blk = (now.weekday() < 5 and now.hour < 17) or (now.weekday() == 6 and 2 <= now.hour < 14)
        staff_claims = claims_db.get(998, []) + claims_db.get(999, [])
        active_staff_count = len([t for t in staff_claims if t["start"] <= now < t["end"]])
        staff_status = "❌ Closed" if is_blk else f"✅ {self.total_staff_spots - active_staff_count}/{self.total_staff_spots} Free"

        embed = discord.Embed(title="🚗 Parking Status (Next 7 Days)", color=discord.Color.blue())
        embed.add_field(name="Resident/Guest", value="\n".join(lines) or "No spots offered", inline=False)
        embed.add_field(name="Staff Spots", value=staff_status)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tasks.loop(minutes=1)
    async def parking_monitor(self):
        """Silent cleanup: Removes expired data so the status stays accurate."""
        now = datetime.now(local_tz)

        # 1. Cleanup Resident/Guest Claims
        for spot in list(self.active_claims.keys()):
            # Only keep claims that haven't ended yet
            self.active_claims[spot] = [c for c in self.active_claims[spot] if c["end"] > now]
            # Remove the spot key if no claims remain
            if not self.active_claims[spot]:
                del self.active_claims[spot]

        # 2. Cleanup Staff Claims
        self.staff_claims = [sc for sc in self.staff_claims if sc["end"] > now]

        # 3. Cleanup Offers
        # If an owner's offer window has passed, remove it from the list
        self.offers = {s: off for s, off in self.offers.items() if off["end"] > now}

    async def cancel_spot_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        choices = []
        now_dt = datetime.now(local_tz)
        now_iso = now_dt.isoformat()

        try:
            # 1. Fetch User's Offers
            offers_res = supabase.table("parking_offers").select("*").eq("owner_id", user_id).gt("end_time",
                                                                                                 now_iso).execute()
            offer_seen = set()

            # Check if data exists before iterating
            if offers_res.data:
                for off in offers_res.data:
                    start = datetime.fromisoformat(off['start_time']).astimezone(local_tz)
                    end = datetime.fromisoformat(off['end_time']).astimezone(local_tz)

                    sig = f"sig_offer_{off['spot_number']}_{start.weekday()}_{start.hour}_{end.hour}"
                    label = f"Withdraw ALL: Spot {off['spot_number']} {start.strftime('%a %I%p')}-{end.strftime('%I%p')}"

                    if sig not in offer_seen and current.lower() in label.lower():
                        choices.append(app_commands.Choice(name=label, value=sig))
                        offer_seen.add(sig)

            # 2. Fetch User's Claims
            claims_res = supabase.table("parking_reservations").select("*").eq("claimer_id", user_id).gt("end_time",
                                                                                                         now_iso).execute()
            claim_seen = set()

            if claims_res.data:
                for c in claims_res.data:
                    start = datetime.fromisoformat(c['start_time']).astimezone(local_tz)
                    end = datetime.fromisoformat(c['end_time']).astimezone(local_tz)
                    spot_label = "Staff" if c['spot_number'] in [998, 999] else f"Spot {c['spot_number']}"

                    sig = f"sig_claim_{c['spot_number']}_{start.weekday()}_{start.hour}_{end.hour}"
                    label = f"Cancel ALL: {spot_label} {start.strftime('%a %I%p')}-{end.strftime('%I%p')}"

                    if sig not in claim_seen and current.lower() in label.lower():
                        choices.append(app_commands.Choice(name=label, value=sig))
                        claim_seen.add(sig)

        except Exception as e:
            print(f"Autocomplete Error: {e}")
            return []  # Return empty list on error to prevent crash

        # Always return a list, even if it's empty
        return choices[:25]

    @app_commands.command(name="cancel", description="Cancel all future recurring slots for a specific time")
    @app_commands.autocomplete(spot=cancel_spot_autocomplete)
    async def cancel(self, interaction: discord.Interaction, spot: str):
        user_id = str(interaction.user.id)
        now_iso = datetime.now(local_tz).isoformat()

        if not spot.startswith("sig_"):
            # Fallback for old single-UUID logic if needed, but here we expect the signature
            return await interaction.response.send_message("❌ Please select an option from the list.", ephemeral=True)

        # Parse signature: sig_type_spot_weekday_starthour_endhour
        parts = spot.split("_")
        action_type = parts[1]  # 'offer' or 'claim'
        spot_num = int(parts[2])
        weekday = int(parts[3])
        start_h = int(parts[4])
        end_h = int(parts[5])

        if action_type == "offer":
            # 1. Identify all matching offers
            targets = supabase.table("parking_offers").select("*").eq("owner_id", user_id).eq("spot_number",
                                                                                              spot_num).gt("end_time",
                                                                                                           now_iso).execute()

            ids_to_del = []
            for row in targets.data:
                st = datetime.fromisoformat(row['start_time']).astimezone(local_tz)
                et = datetime.fromisoformat(row['end_time']).astimezone(local_tz)
                if st.weekday() == weekday and st.hour == start_h and et.hour == end_h:
                    ids_to_del.append(row['id'])

            if not ids_to_del:
                return await interaction.response.send_message("❌ No matching records found.", ephemeral=True)

            # 2. Find and delete linked claims FIRST to avoid ForeignKey violation
            claims_res = supabase.table("parking_reservations").select("id", "claimer_id").in_("offer_id",
                                                                                               ids_to_del).execute()

            if claims_res.data:
                claim_ids = [c['id'] for c in claims_res.data]
                # Delete the 'child' records first
                supabase.table("parking_reservations").delete().in_("id", claim_ids).execute()

            # 3. Now delete the 'parent' offers safely
            supabase.table("parking_offers").delete().in_("id", ids_to_del).execute()

            # Notify users if claims were wiped out
            if claims_res.data:
                pings = ", ".join(list(set([f"<@{c['claimer_id']}>" for c in claims_res.data])))
                return await interaction.response.send_message(
                    f"⚠️ **Attention {pings}**: Multiple recurring offers for **Spot {spot_num}** were withdrawn. Your claims were cancelled.",
                    ephemeral=False)

            return await interaction.response.send_message(f"🔄 Recurring offers for Spot {spot_num} withdrawn.",
                                                           ephemeral=True)

        elif action_type == "claim":
            # Simplified: Delete all future reservations for this user matching the time signature
            all_user_claims = supabase.table("parking_reservations").select("*").eq("claimer_id", user_id).eq(
                "spot_number", spot_num).gt("end_time", now_iso).execute()

            ids_to_del = [
                c['id'] for c in all_user_claims.data
                if datetime.fromisoformat(c['start_time']).astimezone(local_tz).weekday() == weekday
                   and datetime.fromisoformat(c['start_time']).astimezone(local_tz).hour == start_h
            ]

            if ids_to_del:
                supabase.table("parking_reservations").delete().in_("id", ids_to_del).execute()
                return await interaction.response.send_message(
                    f"🔄 Your reservation for Spot {spot_num} at that time cancelled.", ephemeral=True)

        await interaction.response.send_message("❌ No matching active records found.", ephemeral=True)

    @app_commands.command(name="parking_help", description="How to use the parking system")
    async def parking_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🚗 Parking System Guide",
            description="Manage resident, guest, and staff parking spots efficiently.",
            color=discord.Color.blue()
        )

        # Basic Commands
        embed.add_field(
            name="📍 General Commands",
            value=(
                "`/parking_status` - View all currently available and reserved spots.\n"
                "`/cancel [spot]` - Cancel your reservation or withdraw your offer.\n"
                "   *Leave [spot] blank to cancel Staff reservations.*"
            ),
            inline=False
        )

        # Resident/Guest Section
        embed.add_field(
            name="🏠 Resident & Guest Spots",
            value=(
                "**Spot 46 (Guest):** Always available to claim up to 7 days in advance.\n"
                "**Resident Spots (1-33, 41-45):** Must be offered by the owner first.\n\n"
                "`/offer_spot` - Owners list their spot for others to use.\n"
                "`/claim_spot` - Reserve an offered resident spot or the guest spot.\n"
                "   *Note: Claims must be between 2 hours and 7 days long.*"
            ),
            inline=False
        )

        # Staff Section
        embed.add_field(
            name="⛪ Staff Parking",
            value=(
                "`/claim_staff` - Reserve one of the 2 available staff spots.\n"
                "**Blackout Rules:** Staff spots cannot be reserved during:\n"
                "• Mon-Fri: Before 5:00 PM\n"
                "• Sunday: 2:00 AM - 2:00 PM"
            ),
            inline=False
        )

        embed.set_footer(text="All times are in America/Chicago (CST/CDT)")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Parking(bot))

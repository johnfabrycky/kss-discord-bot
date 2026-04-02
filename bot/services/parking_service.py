import os
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from supabase import create_client

from bot.utils.constants import GUEST_SPOTS, LOCAL_TZ, STAFF_SPOTS, VALID_SPOTS


class ParkingService:
    """Database-backed business logic for the parking system."""

    def __init__(self):
        """Create the shared Supabase client used by parking commands."""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        self.supabase = create_client(url, key)

    def parse_range(self, s_day_int, s_time_str, e_day_int, e_time_str):
        """Convert weekday and hour choices into the next matching start/end datetimes."""
        now = datetime.now(LOCAL_TZ).replace(minute=0, second=0, microsecond=0)

        from dateutil.relativedelta import FR, MO, SA, SU, TH, TU, WE

        day_map = {0: MO, 1: TU, 2: WE, 3: TH, 4: FR, 5: SA, 6: SU}

        def to_dt(day_val, time_str, reference_date):
            t_obj = datetime.strptime(time_str.strip().upper(), "%I %p").time()
            real_day = day_map[int(day_val)]

            dt = reference_date + relativedelta(
                weekday=real_day,
                hour=t_obj.hour,
                minute=0,
                second=0,
                microsecond=0,
            )

            if dt < reference_date:
                dt += relativedelta(weeks=1)
            return dt

        start = to_dt(s_day_int, s_time_str, now)
        end = to_dt(e_day_int, e_time_str, start)

        if end == start:
            end += relativedelta(weeks=1)

        return start, end, end - start

    def _format_datetime_label(self, value):
        """Format a datetime as a human-readable weekday/date/time label."""
        hour = value.hour % 12 or 12
        am_pm = "AM" if value.hour < 12 else "PM"
        return f"{value.strftime('%a %b')} {value.day} at {hour}:{value.strftime('%M')} {am_pm}"

    async def initialize_spots(self):
        """Synchronize the database parking spot table with the configured constants."""
        all_configs = []
        for s in VALID_SPOTS:
            all_configs.append(
                {
                    "spot_number": s,
                    "spot_type": "resident",
                    "is_guest": s in GUEST_SPOTS,
                }
            )

        for s in STAFF_SPOTS:
            all_configs.append(
                {
                    "spot_number": s,
                    "spot_type": "staff",
                    "is_guest": False,
                }
            )

        try:
            self.supabase.table("parking_spots").upsert(all_configs, on_conflict="spot_number").execute()
        except Exception as e:
            print(f"⚠️ Service Error initializing spots: {e}")

    def is_blackout(self, start, end):
        """Return whether any hour in the requested window falls inside staff blackout time."""
        curr = start
        while curr < end:
            d, h = curr.weekday(), curr.hour
            if (d < 5 and h < 17) or (d == 6 and 2 <= h < 14):
                return True
            curr += timedelta(hours=1)
        return False

    async def get_parking_data(self, now, cutoff):
        """Fetch all raw parking data needed to build the status view."""
        offers = (
            self.supabase.table("parking_offers")
            .select("*")
            .gt("end_time", now.isoformat())
            .lt("start_time", cutoff.isoformat())
            .execute()
        )
        claims = (
            self.supabase.table("parking_reservations")
            .select("*")
            .gt("end_time", now.isoformat())
            .lt("start_time", cutoff.isoformat())
            .execute()
        )
        guests = self.supabase.table("parking_spots").select("spot_number").eq("is_guest", True).execute()
        return offers.data, claims.data, [r["spot_number"] for r in guests.data]

    async def create_offers(self, user_id, spot, base_start, base_end, weeks):
        """Create one or more weekly parking offers and return a user-facing confirmation."""
        all_offers = []
        for i in range(weeks):
            start = base_start + timedelta(weeks=i)
            end = base_end + timedelta(weeks=i)

            existing = (
                self.supabase.table("parking_offers")
                .select("*")
                .eq("spot_number", spot)
                .lt("start_time", end.isoformat())
                .gt("end_time", start.isoformat())
                .execute()
            )

            if not existing.data:
                all_offers.append(
                    {
                        "spot_number": spot,
                        "owner_id": str(user_id),
                        "start_time": start.isoformat(),
                        "end_time": end.isoformat(),
                    }
                )

        if not all_offers:
            return False, "❌ This spot is already offered for those times."

        try:
            self.supabase.table("parking_offers").insert(all_offers).execute()

            start_label = self._format_datetime_label(base_start)
            end_label = self._format_datetime_label(base_end)
            recur_msg = f" for the next **{weeks} weeks**" if weeks > 1 else ""
            success_msg = (
                f"📢 **Spot {spot}** listed{recur_msg}\n"
                f"Start: {start_label}\n"
                f"End: {end_label}"
            )

            return True, success_msg
        except Exception as e:
            return False, f"❌ Database error: {e}"

    async def claim_resident_spot(self, user_id, spot, start, end):
        """Reserve a guest spot or a resident spot covered by an existing offer."""
        conflict = (
            self.supabase.table("parking_reservations")
            .select("*")
            .eq("spot_number", spot)
            .lt("start_time", end.isoformat())
            .gt("end_time", start.isoformat())
            .execute()
        )
        if conflict.data:
            return False, f"❌ Spot {spot} is already reserved."

        offer_id = None
        if spot not in GUEST_SPOTS:
            offer = (
                self.supabase.table("parking_offers")
                .select("id")
                .eq("spot_number", spot)
                .lte("start_time", start.isoformat())
                .gte("end_time", end.isoformat())
                .execute()
            )
            if not offer.data:
                return False, f"❌ Spot {spot} isn't offered for that window."
            offer_id = offer.data[0]["id"]

        self.supabase.table("parking_reservations").insert(
            {
                "spot_number": spot,
                "claimer_id": str(user_id),
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "offer_id": offer_id,
            }
        ).execute()
        return True, f"✅ **Spot {spot}** reserved!"

    async def claim_staff_spot(self, user_id, start, end):
        """Assign the first available staff spot for a requested window."""
        if self.is_blackout(start, end):
            return False, "❌ Blackout hours active."

        conflicts = (
            self.supabase.table("parking_reservations")
            .select("spot_number")
            .in_("spot_number", STAFF_SPOTS)
            .lt("start_time", end.isoformat())
            .gt("end_time", start.isoformat())
            .execute()
        )
        occupied = [row["spot_number"] for row in conflicts.data]

        if len(occupied) >= len(STAFF_SPOTS):
            return False, "❌ Staff spots are full."

        assigned = STAFF_SPOTS[0] if STAFF_SPOTS[0] not in occupied else STAFF_SPOTS[1]
        self.supabase.table("parking_reservations").insert(
            {
                "spot_number": assigned,
                "claimer_id": str(user_id),
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }
        ).execute()
        return True, f"✅ Staff Spot reserved ({start.strftime('%a %I%p')})."

    async def cancel_action(self, user_id, action_type, spot_num, weekday, start_h, end_h):
        """Cancel matching recurring offers or reservations and return any affected user mentions."""
        now_iso = datetime.now(LOCAL_TZ).isoformat()
        if action_type == "offer":
            targets = (
                self.supabase.table("parking_offers")
                .select("*")
                .eq("owner_id", str(user_id))
                .eq("spot_number", spot_num)
                .gt("end_time", now_iso)
                .execute()
            )
            ids = [
                r["id"]
                for r in targets.data
                if datetime.fromisoformat(r["start_time"]).astimezone(LOCAL_TZ).weekday() == weekday
            ]
            if not ids:
                return False, "No matching offers.", None

            claims = self.supabase.table("parking_reservations").select("claimer_id").in_("offer_id", ids).execute()
            self.supabase.table("parking_reservations").delete().in_("offer_id", ids).execute()
            self.supabase.table("parking_offers").delete().in_("id", ids).execute()
            pings = list({f"<@{c['claimer_id']}>" for c in claims.data})
            return True, f"🔄 Spot {spot_num} offers withdrawn.", pings

        targets = (
            self.supabase.table("parking_reservations")
            .select("*")
            .eq("claimer_id", str(user_id))
            .eq("spot_number", spot_num)
            .gt("end_time", now_iso)
            .execute()
        )
        ids = [
            r["id"]
            for r in targets.data
            if datetime.fromisoformat(r["start_time"]).astimezone(LOCAL_TZ).weekday() == weekday
        ]
        if not ids:
            return False, "No matching claims.", None
        self.supabase.table("parking_reservations").delete().in_("id", ids).execute()
        return True, f"🔄 Reservation for Spot {spot_num} cancelled.", None

    async def get_user_activity(self, user_id):
        """Fetch active offers and reservations for a specific user."""
        now_iso = datetime.now(LOCAL_TZ).isoformat()

        offers = (
            self.supabase.table("parking_offers")
            .select("*")
            .eq("owner_id", str(user_id))
            .gt("end_time", now_iso)
            .execute()
        )

        claims = (
            self.supabase.table("parking_reservations")
            .select("*")
            .eq("claimer_id", str(user_id))
            .gt("end_time", now_iso)
            .execute()
        )

        return offers.data, claims.data

    async def get_guest_spot_list(self) -> str:
        """Fetch guest spot numbers and return a formatted string."""
        try:
            response = self.supabase.table("parking_spots").select("spot_number").eq("is_guest", True).execute()
            guest_spots = [str(r["spot_number"]) for r in response.data]
            return ", ".join(guest_spots) if guest_spots else "None"
        except Exception as e:
            print(f"⚠️ Service Error fetching guest spots for help: {e}")
            return "Error loading spots"

    def get_merged_availability(self, now, cutoff, raw_offers, raw_claims, is_guest=False):
        """Merge offer windows, subtract claims, and return a status header plus free blocks."""
        if is_guest:
            merged_windows = [{"start": now.replace(hour=0), "end": cutoff}]
        else:
            raw_sorted = sorted(raw_offers, key=lambda x: x["start"])
            if not raw_sorted:
                merged_windows = []
            else:
                merged_windows = []
                curr = raw_sorted[0].copy()
                for next_w in raw_sorted[1:]:
                    if next_w["start"] <= curr["end"]:
                        curr["end"] = max(curr["end"], next_w["end"])
                    else:
                        merged_windows.append(curr)
                        curr = next_w.copy()
                merged_windows.append(curr)

        blocks = []
        for w in merged_windows:
            w_start, w_end = max(w["start"], now), min(w["end"], cutoff)
            if w_start >= w_end:
                continue

            ptr = w_start
            relevant_claims = sorted(
                [c for c in raw_claims if not (c["end"] <= w_start or c["start"] >= w_end)],
                key=lambda x: x["start"],
            )

            for c in relevant_claims:
                c_start = max(c["start"], w_start)
                if (c_start - ptr) >= timedelta(hours=2):
                    blocks.append((ptr, c_start))
                ptr = max(ptr, c["end"])

            if (w_end - ptr) >= timedelta(hours=2):
                blocks.append((ptr, w_end))

        current_claim = next((c for c in raw_claims if c["start"] <= now < c["end"]), None)
        active_block = next((b for b in blocks if b[0] <= now < b[1]), None)
        next_block = next((b for b in blocks if b[0] > now), None)

        if active_block:
            header = f"🟢 Available Now (until {active_block[1].strftime('%a %I%p')})"
        elif current_claim:
            if next_block:
                header = f"🔴 Busy (Next: {next_block[0].strftime('%a %I%p')})"
            else:
                header = f"🔴 Busy until {current_claim['end'].strftime('%a %I%p')}"
        elif next_block:
            header = f"🕒 Unavailable (Next: {next_block[0].strftime('%a %I%p')})"
        else:
            header = "❌ Not Offered"

        return header, blocks

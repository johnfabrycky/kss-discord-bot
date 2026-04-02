import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from supabase import create_client
from constants import LOCAL_TZ, STAFF_SPOTS, GUEST_SPOTS


class ParkingService:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        self.supabase = create_client(url, key)

    def parse_range(self, s_day_int, s_time_str, e_day_int, e_time_str):
        now = datetime.now(LOCAL_TZ).replace(minute=0, second=0, microsecond=0)

        def to_dt(day_val, time_str, reference_date):
            t_obj = datetime.strptime(time_str.strip().upper(), "%I %p").time()
            dt = reference_date + relativedelta(
                weekday=day_val, hour=t_obj.hour, minute=0, second=0, microsecond=0
            )
            if dt <= reference_date:
                dt += relativedelta(weeks=1)
            return dt

        start = to_dt(s_day_int, s_time_str, now)
        end = to_dt(e_day_int, e_time_str, start)
        if end == start:
            end += relativedelta(weeks=1)
        return start, end, end - start

    def is_blackout(self, start, end):
        curr = start
        while curr < end:
            d, h = curr.weekday(), curr.hour
            if (d < 5 and h < 17) or (d == 6 and 2 <= h < 14): return True
            curr += timedelta(hours=1)
        return False

    async def get_parking_data(self, now, cutoff):
        """Fetches all raw data for status reporting."""
        offers = self.supabase.table("parking_offers").select("*").gt("end_time", now.isoformat()).lt("start_time",
                                                                                                      cutoff.isoformat()).execute()
        claims = self.supabase.table("parking_reservations").select("*").gt("end_time", now.isoformat()).lt(
            "start_time", cutoff.isoformat()).execute()
        guests = self.supabase.table("parking_spots").select("spot_number").eq("is_guest", True).execute()
        return offers.data, claims.data, [r['spot_number'] for r in guests.data]

    async def create_offers(self, user_id, spot, base_start, base_end, weeks):
        all_offers = []
        for i in range(weeks):
            start = base_start + timedelta(weeks=i)
            end = base_end + timedelta(weeks=i)
            # Check for existing offer overlap
            existing = self.supabase.table("parking_offers").select("*").eq("spot_number", spot).lt("start_time",
                                                                                                    end.isoformat()).gt(
                "end_time", start.isoformat()).execute()

            if not existing.data:
                all_offers.append({
                    "spot_number": spot, "owner_id": str(user_id),
                    "start_time": start.isoformat(), "end_time": end.isoformat()
                })

        if not all_offers:
            return False, "❌ Spot already offered for those times."

        self.supabase.table("parking_offers").insert(all_offers).execute()
        return True, f"📢 **Spot {spot}** listed for {weeks} week(s)!"

    async def claim_resident_spot(self, user_id, spot, start, end):
        conflict = self.supabase.table("parking_reservations").select("*").eq("spot_number", spot).lt("start_time",
                                                                                                      end.isoformat()).gt(
            "end_time", start.isoformat()).execute()
        if conflict.data: return False, f"❌ Spot {spot} is already reserved."

        offer_id = None
        if spot not in GUEST_SPOTS:
            offer = self.supabase.table("parking_offers").select("id").eq("spot_number", spot).lte("start_time",
                                                                                                   start.isoformat()).gte(
                "end_time", end.isoformat()).execute()
            if not offer.data: return False, f"❌ Spot {spot} isn't offered for that window."
            offer_id = offer.data[0]['id']

        self.supabase.table("parking_reservations").insert({
            "spot_number": spot, "claimer_id": str(user_id), "start_time": start.isoformat(),
            "end_time": end.isoformat(), "offer_id": offer_id
        }).execute()
        return True, f"✅ **Spot {spot}** reserved!"

    async def claim_staff_spot(self, user_id, start, end):
        if self.is_blackout(start, end): return False, "❌ Blackout hours active."

        conflicts = self.supabase.table("parking_reservations").select("spot_number").in_("spot_number",
                                                                                          STAFF_SPOTS).lt("start_time",
                                                                                                          end.isoformat()).gt(
            "end_time", start.isoformat()).execute()
        occupied = [row['spot_number'] for row in conflicts.data]

        if len(occupied) >= len(STAFF_SPOTS): return False, "❌ Staff spots are full."

        assigned = STAFF_SPOTS[0] if STAFF_SPOTS[0] not in occupied else STAFF_SPOTS[1]
        self.supabase.table("parking_reservations").insert({
            "spot_number": assigned, "claimer_id": str(user_id), "start_time": start.isoformat(),
            "end_time": end.isoformat()
        }).execute()
        return True, f"✅ Staff Spot reserved ({start.strftime('%a %I%p')})."

    async def cancel_action(self, user_id, action_type, spot_num, weekday, start_h, end_h):
        now_iso = datetime.now(LOCAL_TZ).isoformat()
        if action_type == "offer":
            targets = self.supabase.table("parking_offers").select("*").eq("owner_id", str(user_id)).eq("spot_number",
                                                                                                        spot_num).gt(
                "end_time", now_iso).execute()
            ids = [r['id'] for r in targets.data if
                   datetime.fromisoformat(r['start_time']).astimezone(LOCAL_TZ).weekday() == weekday]
            if not ids: return False, "No matching offers.", None

            # Wipe linked claims first
            claims = self.supabase.table("parking_reservations").select("claimer_id").in_("offer_id", ids).execute()
            self.supabase.table("parking_reservations").delete().in_("offer_id", ids).execute()
            self.supabase.table("parking_offers").delete().in_("id", ids).execute()
            pings = list(set([f"<@{c['claimer_id']}>" for c in claims.data]))
            return True, f"🔄 Spot {spot_num} offers withdrawn.", pings

        else:  # claim
            targets = self.supabase.table("parking_reservations").select("*").eq("claimer_id", str(user_id)).eq(
                "spot_number", spot_num).gt("end_time", now_iso).execute()
            ids = [r['id'] for r in targets.data if
                   datetime.fromisoformat(r['start_time']).astimezone(LOCAL_TZ).weekday() == weekday]
            if not ids: return False, "No matching claims.", None
            self.supabase.table("parking_reservations").delete().in_("id", ids).execute()
            return True, f"🔄 Reservation for Spot {spot_num} cancelled.", None

    def get_merged_availability(self, now, cutoff, raw_offers, raw_claims, is_guest=False):
        """
        Pure Logic: Consolidates offers, subtracts claims, and returns (header, blocks).
        """
        # 1. Merge Windows
        if is_guest:
            merged_windows = [{"start": now.replace(hour=0), "end": cutoff}]
        else:
            raw_sorted = sorted(raw_offers, key=lambda x: x['start'])
            if not raw_sorted:
                merged_windows = []
            else:
                merged_windows = []
                curr = raw_sorted[0].copy()
                for next_w in raw_sorted[1:]:
                    if next_w['start'] <= curr['end']:
                        curr['end'] = max(curr['end'], next_w['end'])
                    else:
                        merged_windows.append(curr)
                        curr = next_w.copy()
                merged_windows.append(curr)

        # 2. Calculate Gaps (Free Blocks)
        blocks = []
        for w in merged_windows:
            w_start, w_end = max(w["start"], now), min(w["end"], cutoff)
            if w_start >= w_end: continue

            ptr = w_start
            relevant_claims = sorted([c for c in raw_claims if not (c['end'] <= w_start or c['start'] >= w_end)],
                                     key=lambda x: x['start'])

            for c in relevant_claims:
                c_start = max(c['start'], w_start)
                if (c_start - ptr) >= timedelta(hours=2):
                    blocks.append((ptr, c_start))
                ptr = max(ptr, c['end'])

            if (w_end - ptr) >= timedelta(hours=2):
                blocks.append((ptr, w_end))

        # 3. Determine Header Status
        is_offered_now = any(w["start"] <= now < w["end"] for w in merged_windows)
        current_claim = next((c for c in raw_claims if c["start"] <= now < c["end"]), None)

        if current_claim:
            header = f"🔴 Busy until {current_claim['end'].strftime('%a %I%p')}"
        elif not is_offered_now:
            upcoming = next((w for w in merged_windows if w["start"] > now), None)
            header = f"🕒 Unavailable (Next: {upcoming['start'].strftime('%a %I%p')})" if upcoming else "❌ Not Offered"
        else:
            limit = next((w["end"] for w in merged_windows if w["start"] <= now < w["end"]), cutoff)
            upcoming_claim = next((c for c in raw_claims if c["start"] > now), None)
            if upcoming_claim and upcoming_claim['start'] < limit:
                limit = upcoming_claim['start']
            header = f"🟢 Available Now (until {limit.strftime('%a %I%p')})"

        return header, blocks
import asyncio
import logging
import os
import time
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from supabase import create_client

from bot.config import LOCAL_TZ, STAFF_SPOTS, VALID_SPOTS

try:
    import httpx
except ImportError:  # pragma: no cover - httpx is provided transitively in production.
    httpx = None

logger = logging.getLogger(__name__)


class ParkingService:
    """Database-backed business logic for the parking system."""

    AUTOCOMPLETE_CACHE_TTL_SECONDS = 5
    AUTOCOMPLETE_TIMEOUT_SECONDS = 2

    def __init__(self, supabase=None):
        """Use the shared Supabase client, falling back to direct creation when needed."""
        if supabase is None:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY")
            supabase = create_client(url, key)
        self.supabase = supabase
        self._claim_autocomplete_cache = None
        self._cancel_autocomplete_cache = {}

        # In-memory cache for guest spots loaded on startup
        self.guest_spots_cache = set()

    @staticmethod
    def _build_log_context(log_context=None, **extra_fields):
        """Merge contextual log fields without mutating the caller's payload."""
        merged = dict(log_context or {})
        merged.update({key: value for key, value in extra_fields.items() if value is not None})
        return merged

    @staticmethod
    def _is_remote_protocol_error(exc):
        """Detect the HTTP protocol termination errors raised by the Supabase stack."""
        if httpx is not None and isinstance(exc, httpx.RemoteProtocolError):
            return True
        return exc.__class__.__name__ == "RemoteProtocolError"

    @staticmethod
    def _is_transport_error(exc):
        """Detect broader HTTP transport failures from the Supabase/PostgREST client."""
        if httpx is not None and isinstance(exc, httpx.TransportError):
            return True
        return exc.__class__.__name__.endswith(("ProtocolError", "TransportError", "NetworkError"))

    async def _run_blocking(self, func, *args, timeout=15, log_context=None):
        """Run a blocking Supabase operation off the event loop with timeout/logging."""
        try:
            return await asyncio.wait_for(asyncio.to_thread(func, *args), timeout=timeout)
        except asyncio.TimeoutError:
            logger.exception(
                "Parking service operation timed out",
                extra=self._build_log_context(log_context, error_type="TimeoutError"),
            )
            raise
        except Exception as exc:
            extra = self._build_log_context(
                log_context,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            if self._is_remote_protocol_error(exc):
                logger.exception(
                    "Parking service Supabase/PostgREST connection terminated during request",
                    extra=extra,
                )
            elif self._is_transport_error(exc):
                logger.exception(
                    "Parking service Supabase/PostgREST transport error",
                    extra=extra,
                )
            else:
                logger.exception("Parking service operation failed", extra=extra)
            raise

    def _get_cached_value(self, cache_entry):
        """Return a cached autocomplete payload when it is still fresh."""
        if not cache_entry:
            return None

        cached_at, payload = cache_entry
        if (time.monotonic() - cached_at) <= self.AUTOCOMPLETE_CACHE_TTL_SECONDS:
            return payload
        return None

    def _store_cache_value(self, cache_name, key, payload):
        """Persist a short-lived autocomplete payload in memory."""
        entry = (time.monotonic(), payload)
        if cache_name == "claim":
            self._claim_autocomplete_cache = entry
            return

        self._cancel_autocomplete_cache[key] = entry

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

    def _load_cache_sync(self):
        """Fetch the current guest spots from the DB to populate the cache."""
        response = self.supabase.table("parking_spots").select("spot_number").eq("is_guest", True).execute()
        self.guest_spots_cache = {row["spot_number"] for row in response.data}

    async def load_cache(self):
        """Load mostly-static data into memory to reduce database hits."""
        try:
            await self._run_blocking(self._load_cache_sync, log_context={"operation": "load_cache"})
            logger.info(f"Loaded {len(self.guest_spots_cache)} guest spots into cache.")
        except Exception:
            logger.exception("Failed to load parking spot cache.")

    def _initialize_spots_sync(self):
        # Fetch existing spots so we don't accidentally wipe is_guest status during upsert
        existing_spots_response = self.supabase.table("parking_spots").select("spot_number, is_guest").execute()
        existing_guest_spots = {
            row["spot_number"] for row in existing_spots_response.data if row.get("is_guest")
        }

        # Update the local cache while we have the fresh data
        self.guest_spots_cache = existing_guest_spots

        all_configs = []
        for spot in VALID_SPOTS:
            all_configs.append(
                {
                    "spot_number": spot,
                    "spot_type": "resident",
                    "is_guest": spot in existing_guest_spots,
                }
            )

        for spot in STAFF_SPOTS:
            all_configs.append(
                {
                    "spot_number": spot,
                    "spot_type": "staff",
                    "is_guest": False,
                }
            )

        self.supabase.table("parking_spots").upsert(all_configs, on_conflict="spot_number").execute()

    async def initialize_spots(self):
        """Synchronize the database parking spot table with the configured constants."""
        try:
            await self._run_blocking(self._initialize_spots_sync, timeout=20,
                                     log_context={"operation": "initialize_spots"})
        except Exception:
            logger.exception("Parking spot initialization failed")

    def is_blackout(self, start, end):
        """Return whether any hour in the requested window falls inside staff blackout time."""
        curr = start
        while curr < end:
            d, h = curr.weekday(), curr.hour
            if (d < 5 and h < 17) or (d == 6 and 2 <= h < 14):
                return True
            curr += timedelta(hours=1)
        return False

    def _get_parking_data_sync(self, now, cutoff):
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
        # Using the cache instead of a database round trip
        return offers.data, claims.data, list(self.guest_spots_cache)

    async def get_parking_data(self, now, cutoff):
        """Fetch all raw parking data needed to build the status view."""
        return await self._run_blocking(
            self._get_parking_data_sync,
            now,
            cutoff,
            log_context={"operation": "get_parking_data"},
        )

    def _create_offers_sync(self, user_id, username, spot, base_start, base_end, weeks):
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
                        "owner_discord_username": username,
                        "start_time": start.isoformat(),
                        "end_time": end.isoformat(),
                    }
                )

        if not all_offers:
            return False, "❌ This spot is already offered for those times."

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

    async def create_offers(self, user_id, username, spot, base_start, base_end, weeks):
        """Create one or more weekly parking offers and return a user-facing confirmation."""
        try:
            return await self._run_blocking(
                self._create_offers_sync,
                user_id,
                username,
                spot,
                base_start,
                base_end,
                weeks,
                log_context={"operation": "create_offers", "user_id": str(user_id), "username": username, "spot": spot},
            )
        except Exception as e:
            return False, f"❌ Database error: {e}"

    def _claim_resident_spot_sync(self, user_id, username, spot, start, end):
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
        # Checking memory cache instead of querying Supabase
        if spot not in self.guest_spots_cache:
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
                "claimer_discord_username": username,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "offer_id": offer_id,
            }
        ).execute()

        start_label = self._format_datetime_label(start)
        end_label = self._format_datetime_label(end)

        return True, f"✅ **Spot {spot}** reserved!\nStart: {start_label}\nEnd: {end_label}"

    async def claim_resident_spot(self, user_id, username, spot, start, end):
        """Reserve a guest spot or a resident spot covered by an existing offer."""
        return await self._run_blocking(
            self._claim_resident_spot_sync,
            user_id,
            username,
            spot,
            start,
            end,
            log_context={"operation": "claim_resident_spot", "user_id": str(user_id), "username": username,
                         "spot": spot},
        )

    def _claim_staff_spot_sync(self, user_id, username, start, end):
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
                "claimer_discord_username": username,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }
        ).execute()

        start_label = self._format_datetime_label(start)
        end_label = self._format_datetime_label(end)

        return True, f"✅ Staff Spot reserved!\nStart: {start_label}\nEnd: {end_label}"

    async def claim_staff_spot(self, user_id, username, start, end):
        """Assign the first available staff spot for a requested window."""
        return await self._run_blocking(
            self._claim_staff_spot_sync,
            user_id,
            username,
            start,
            end,
            log_context={"operation": "claim_staff_spot", "user_id": str(user_id), "username": username},
        )

    def _cancel_action_sync(self, user_id, action_type, record_id):
        now_iso = datetime.now(LOCAL_TZ).isoformat()

        if action_type == "offer":
            target = (
                self.supabase.table("parking_offers")
                .select("*")
                .eq("owner_id", str(user_id))
                .eq("id", str(record_id))
                .gt("end_time", now_iso)
                .execute()
            )
            if not target.data:
                logger.warning(
                    "Parking cancel found no matching offer",
                    extra={"user_id": str(user_id), "action_type": action_type, "record_id": str(record_id)},
                )
                return False, "No matching offers.", None

            offer = target.data[0]
            claims = self.supabase.table("parking_reservations").select("claimer_id").eq("offer_id",
                                                                                         str(record_id)).execute()
            self.supabase.table("parking_reservations").delete().eq("offer_id", str(record_id)).execute()
            self.supabase.table("parking_offers").delete().eq("id", str(record_id)).execute()
            pings = list({f"<@{c['claimer_id']}>" for c in claims.data})
            return True, f"🔄 Spot {offer['spot_number']} offer withdrawn.", pings

        target = (
            self.supabase.table("parking_reservations")
            .select("*")
            .eq("claimer_id", str(user_id))
            .eq("id", str(record_id))
            .gt("end_time", now_iso)
            .execute()
        )
        if not target.data:
            logger.warning(
                "Parking cancel found no matching reservation",
                extra={"user_id": str(user_id), "action_type": action_type, "record_id": str(record_id)},
            )
            return False, "No matching claims.", None

        reservation = target.data[0]
        self.supabase.table("parking_reservations").delete().eq("id", str(record_id)).execute()
        return True, f"🔄 Reservation for Spot {reservation['spot_number']} cancelled.", None

    async def cancel_action(self, user_id, action_type, record_id):
        """Cancel one selected offer or reservation and return any affected user mentions."""
        return await self._run_blocking(
            self._cancel_action_sync,
            user_id,
            action_type,
            record_id,
            timeout=15,
            log_context={"operation": "cancel_action", "user_id": str(user_id), "action_type": action_type,
                         "record_id": str(record_id)},
        )

    def _get_user_activity_sync(self, user_id):
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

    async def get_user_activity(self, user_id):
        """Fetch active offers and reservations for a specific user."""
        return await self._run_blocking(
            self._get_user_activity_sync,
            user_id,
            log_context={"operation": "get_user_activity", "user_id": str(user_id)},
        )

    def _get_cancel_autocomplete_data_sync(self, user_id, now_iso):
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

    async def get_cancel_autocomplete_data(self, user_id, now):
        """Fetch active offers and reservations for cancel autocomplete."""
        cached = self._get_cached_value(self._cancel_autocomplete_cache.get(str(user_id)))
        if cached is not None:
            return cached

        try:
            payload = await self._run_blocking(
                self._get_cancel_autocomplete_data_sync,
                user_id,
                now.isoformat(),
                timeout=self.AUTOCOMPLETE_TIMEOUT_SECONDS,
                log_context={"operation": "get_cancel_autocomplete_data", "user_id": str(user_id)},
            )
            self._store_cache_value("cancel", str(user_id), payload)
            return payload
        except Exception:
            return [], []

    def _get_claim_autocomplete_data_sync(self, now_iso):
        offers = (
            self.supabase.table("parking_offers")
            .select("spot_number,start_time,end_time")
            .gt("end_time", now_iso)
            .execute()
        )
        claims = (
            self.supabase.table("parking_reservations")
            .select("spot_number,start_time,end_time")
            .gt("end_time", now_iso)
            .execute()
        )

        # Build payload directly from cache
        guest_spots = [{"spot_number": spot} for spot in self.guest_spots_cache]
        return guest_spots, offers.data, claims.data

    async def get_claim_autocomplete_data(self, now):
        """Fetch guest spots, active offers, and active claims for claim autocomplete."""
        cached = self._get_cached_value(self._claim_autocomplete_cache)
        if cached is not None:
            return cached

        try:
            payload = await self._run_blocking(
                self._get_claim_autocomplete_data_sync,
                now.isoformat(),
                timeout=self.AUTOCOMPLETE_TIMEOUT_SECONDS,
                log_context={"operation": "get_claim_autocomplete_data"},
            )
            self._store_cache_value("claim", None, payload)
            return payload
        except Exception:
            return [], [], []

    async def get_guest_spot_list(self) -> str:
        """Return the formatted string directly from the local cache."""
        if not self.guest_spots_cache:
            return "None"
        # Sort them numerically/alphabetically before joining for cleaner display
        return ", ".join(map(str, sorted(self.guest_spots_cache)))

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
                for next_window in raw_sorted[1:]:
                    if next_window["start"] <= curr["end"]:
                        curr["end"] = max(curr["end"], next_window["end"])
                    else:
                        merged_windows.append(curr)
                        curr = next_window.copy()
                merged_windows.append(curr)

        blocks = []
        for window in merged_windows:
            window_start, window_end = max(window["start"], now), min(window["end"], cutoff)
            if window_start >= window_end:
                continue

            pointer = window_start
            relevant_claims = sorted(
                [claim for claim in raw_claims if not (claim["end"] <= window_start or claim["start"] >= window_end)],
                key=lambda x: x["start"],
            )

            for claim in relevant_claims:
                claim_start = max(claim["start"], window_start)
                if (claim_start - pointer) >= timedelta(hours=2):
                    blocks.append((pointer, claim_start))
                pointer = max(pointer, claim["end"])

            if (window_end - pointer) >= timedelta(hours=2):
                blocks.append((pointer, window_end))

        current_claim = next((claim for claim in raw_claims if claim["start"] <= now < claim["end"]), None)
        active_block = next((block for block in blocks if block[0] <= now < block[1]), None)
        next_block = next((block for block in blocks if block[0] > now), None)

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

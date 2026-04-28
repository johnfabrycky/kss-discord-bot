import asyncio
import logging
import time
from collections import Counter
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import LOCAL_TZ, STAFF_SPOTS, PERMIT_SPOTS, MINIMUM_RESERVATION_HOURS, MAXIMUM_RESERVATION_DAYS, \
    MINIMUM_OFFER_HOURS, BOT_NAME
from bot.services.parking_service import ParkingService
from bot.utils.constants import WEEKDAYS

logger = logging.getLogger(__name__)
STATUS_CACHE_TTL_SECONDS = 15


class Parking(commands.Cog):
    """Slash commands for offering, claiming, and viewing parking availability."""

    day_choices = [app_commands.Choice(name=name, value=obj.weekday) for obj, name in WEEKDAYS]
    time_choices = [
        app_commands.Choice(
            name=f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}",
            value=f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}",
        )
        for i in range(24)
    ]

    def __init__(self, bot):
        """Initialize the parking cog and its shared service layer."""
        self.bot = bot
        self.service = ParkingService(bot.supabase)
        self._parking_status_cache = None
        self._parking_status_cache_expires_at = 0.0
        self._parking_status_lock = asyncio.Lock()

    @staticmethod
    def _clone_embed(embed):
        """Create a detached embed copy safe to reuse across interactions."""
        return discord.Embed.from_dict(embed.to_dict())

    def _get_cached_parking_status_embed(self):
        """Return the cached parking-status embed while it is still fresh."""
        if self._parking_status_cache is None or time.monotonic() >= self._parking_status_cache_expires_at:
            return None
        return self._clone_embed(self._parking_status_cache)

    def _store_cached_parking_status_embed(self, embed):
        """Store a short-lived parking-status embed to absorb burst traffic."""
        self._parking_status_cache = self._clone_embed(embed)
        self._parking_status_cache_expires_at = time.monotonic() + STATUS_CACHE_TTL_SECONDS

    @staticmethod
    def _mark_autocomplete_responded(response):
        """Mark an autocomplete interaction as handled to avoid duplicate sends."""
        if hasattr(response, "_response_type") and getattr(response, "_response_type", None) is None:
            response._response_type = discord.InteractionResponseType.autocomplete_result

    async def _finalize_autocomplete(self, interaction, choices, *, handler_name, log_context):
        """Send autocomplete results directly when possible and swallow stale-response errors."""
        response = getattr(interaction, "response", None)
        if response is None or not hasattr(response, "autocomplete") or not hasattr(response, "is_done"):
            return choices

        if response.is_done():
            return []

        try:
            await response.autocomplete(choices)
        except discord.InteractionResponded:
            logger.warning("%s autocomplete was already acknowledged", handler_name, extra=log_context)
            self._mark_autocomplete_responded(response)
        except discord.HTTPException as exc:
            if exc.code in {40060, 10062}:
                logger.warning(
                    "%s autocomplete response was stale",
                    handler_name,
                    extra={**log_context, "discord_error_code": exc.code},
                )
                self._mark_autocomplete_responded(response)
            else:
                raise

        return []

    async def initialize_parking_spots(self):
        """Ensure the configured parking spots exist in the backing database."""
        await self.service.initialize_spots()

    @app_commands.command(name="my_parking", description="View your active offers and reservations")
    async def my_parking(self, interaction: discord.Interaction):
        """Show the caller's active offers and reservations in one ledger."""
        user_id = str(interaction.user.id)
        now = datetime.now(LOCAL_TZ)
        raw_offers, raw_claims = await self.service.get_user_activity(user_id)

        embed = discord.Embed(title="📋 My Parking Activity", color=discord.Color.green(), timestamp=now)

        offer_groups = Counter()
        for off in raw_offers or []:
            start = datetime.fromisoformat(off["start_time"]).astimezone(LOCAL_TZ)
            end = datetime.fromisoformat(off["end_time"]).astimezone(LOCAL_TZ)
            time_key = f"**Spot {off['spot_number']}**: {start.strftime('%a %I%p')} — {end.strftime('%a %I%p')}"
            offer_groups[time_key] += 1

        offer_lines = [f"{key} (x{count})" if count > 1 else key for key, count in offer_groups.items()]
        embed.add_field(name="📤 My Offers", value="\n".join(offer_lines) or "No active offers.", inline=False)

        claim_groups = Counter()
        for claim in raw_claims or []:
            start = datetime.fromisoformat(claim["start_time"]).astimezone(LOCAL_TZ)
            end = datetime.fromisoformat(claim["end_time"]).astimezone(LOCAL_TZ)
            spot_label = "Staff Spot" if claim["spot_number"] in STAFF_SPOTS else f"Spot {claim['spot_number']}"
            time_key = f"**{spot_label}**: {start.strftime('%a %I%p')} — {end.strftime('%a %I%p')}"
            claim_groups[time_key] += 1

        claim_lines = [f"{key} (x{count})" if count > 1 else key for key, count in claim_groups.items()]
        embed.add_field(name="📥 My Reservations", value="\n".join(claim_lines) or "No active reservations.",
                        inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="offer_spot", description="List your spot as available")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def offer_spot(
            self,
            interaction: discord.Interaction,
            spot: int,
            start_day: app_commands.Choice[int],
            start_time: app_commands.Choice[str],
            end_day: app_commands.Choice[int],
            end_time: app_commands.Choice[str],
            weeks: app_commands.Range[int, 1, 12] = 1,
    ):
        """Offer a resident parking spot for a recurring weekly time window."""
        if spot not in PERMIT_SPOTS:
            return await interaction.response.send_message(f"❌ Spot {spot} is invalid.", ephemeral=True)

        start, end, duration = self.service.parse_range(start_day.value, start_time.value, end_day.value,
                                                        end_time.value)
        if duration < timedelta(hours=MINIMUM_OFFER_HOURS):
            return await interaction.response.send_message(f"❌ Offers must be at least {MINIMUM_OFFER_HOURS} hours.",
                                                           ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        success, msg = await self.service.create_offers(interaction.user.id, interaction.user.name, spot, start, end,
                                                        weeks)

        if not success:
            await interaction.followup.send(msg)
            return None

        await self.service.save_offer_spot_preference(interaction.user.id, interaction.user.name, spot)
        await interaction.channel.send(f"<@{interaction.user.id}> offered spot {spot}!\n{msg}")

        await interaction.delete_original_response()
        return None

    async def claim_spot_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str,
    ) -> list[app_commands.Choice[int]]:
        """Suggest claimable spots that appear to cover the selected time window."""
        log_context = {"user_id": str(interaction.user.id), "current": current}

        try:
            namespace = interaction.namespace
            required_fields = ("start_day", "start_time", "end_day", "end_time")
            if not all(
                    hasattr(namespace, field) and getattr(namespace, field) is not None for field in required_fields):
                return await self._finalize_autocomplete(
                    interaction,
                    [],
                    handler_name="Parking claim_spot",
                    log_context=log_context,
                )

            start_day = getattr(namespace.start_day, "value", namespace.start_day)
            start_time = getattr(namespace.start_time, "value", namespace.start_time)
            end_day = getattr(namespace.end_day, "value", namespace.end_day)
            end_time = getattr(namespace.end_time, "value", namespace.end_time)
            start, end, duration = self.service.parse_range(start_day, start_time, end_day, end_time)

            if duration < timedelta(hours=2) or duration > timedelta(days=7):
                return await self._finalize_autocomplete(
                    interaction,
                    [],
                    handler_name="Parking claim_spot",
                    log_context=log_context,
                )

            now = datetime.now(LOCAL_TZ)
            guest_spots, offered_spots, claims = await self.service.get_claim_autocomplete_data(now)

            # Pre-process claims into a dictionary for efficient lookups
            claims_by_spot = {}
            for row in claims or []:
                claims_by_spot.setdefault(row["spot_number"], []).append(
                    (
                        datetime.fromisoformat(row["start_time"]).astimezone(LOCAL_TZ),
                        datetime.fromisoformat(row["end_time"]).astimezone(LOCAL_TZ),
                    )
                )

            def has_overlapping_claim(spot_num):
                for claim_start, claim_end in claims_by_spot.get(spot_num, []):
                    if claim_start < end and claim_end > start:  # Check for overlap
                        return True
                return False

            available_spots = {}
            for row in guest_spots or []:
                if not has_overlapping_claim(row["spot_number"]):
                    available_spots[row["spot_number"]] = "Guest"

            for row in offered_spots or []:
                offer_start = datetime.fromisoformat(row["start_time"]).astimezone(LOCAL_TZ)
                offer_end = datetime.fromisoformat(row["end_time"]).astimezone(LOCAL_TZ)
                if offer_start <= start and offer_end >= end and not has_overlapping_claim(row["spot_number"]):
                    available_spots.setdefault(row["spot_number"], "Offered")

            choices = []
            for spot_num, label in sorted(available_spots.items()):
                name = f"Spot {spot_num} ({label})"
                if current.lower() in name.lower():
                    choices.append(app_commands.Choice(name=name, value=spot_num))
        except Exception:
            logger.exception("Parking claim_spot autocomplete failed", extra=log_context)
            choices = []

        return await self._finalize_autocomplete(
            interaction,
            choices[:25],
            handler_name="Parking claim_spot",
            log_context=log_context,
        )

    @app_commands.command(name="claim_spot", description="Reserve a resident or guest spot")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    @app_commands.autocomplete(spot=claim_spot_autocomplete)
    async def claim_spot(
            self,
            interaction: discord.Interaction,
            start_day: app_commands.Choice[int],
            start_time: app_commands.Choice[str],
            end_day: app_commands.Choice[int],
            end_time: app_commands.Choice[str],
            spot: int,
    ):
        """Reserve an offered resident spot or a designated guest spot."""
        if spot not in PERMIT_SPOTS:
            return await interaction.response.send_message("Invalid spot.", ephemeral=True)

        start, end, duration = self.service.parse_range(start_day.value, start_time.value, end_day.value,
                                                        end_time.value)
        if duration < timedelta(hours=1) or duration > timedelta(days=3):
            return await interaction.response.send_message(
                f"❌ Must be between {MINIMUM_RESERVATION_HOURS} hour and {MAXIMUM_RESERVATION_DAYS} days.",
                ephemeral=True)

        # 1. Defer privately. Any errors from here out will be hidden.
        await interaction.response.defer(ephemeral=True)

        # 2. Wait for the database
        success, msg = await self.service.claim_resident_spot(interaction.user.id, interaction.user.name, spot, start,
                                                              end)

        if not success:
            # 3a. If it failed, send the error privately via the followup webhook
            await interaction.followup.send(msg)
            return None

        # 3b. If it succeeded, send a PUBLIC message directly to the channel
        # This requires the bot to have the "Send Messages" permission in this channel.
        await interaction.channel.send(f"<@{interaction.user.id}> claimed spot {spot}!\n{msg}")

        # 4. You MUST still resolve the interaction for the user, otherwise
        # it will say "The application did not respond" on their screen.
        await interaction.delete_original_response()
        return None

    @app_commands.command(name="claim_staff", description="Reserve a staff spot")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def claim_staff(
            self,
            interaction: discord.Interaction,
            start_day: app_commands.Choice[int],
            start_time: app_commands.Choice[str],
            end_day: app_commands.Choice[int],
            end_time: app_commands.Choice[str],
    ):
        """Reserve one of the rotating staff spots if blackout rules allow it."""
        start, end, _duration = self.service.parse_range(start_day.value, start_time.value, end_day.value,
                                                         end_time.value)
        await interaction.response.defer(ephemeral=True)

        success, msg = await self.service.claim_staff_spot(interaction.user.id, interaction.user.name, start, end)

        if not success:
            await interaction.followup.send(msg)
            return None

        await interaction.channel.send(f"<@{interaction.user.id}> claimed a staff spot!\n{msg}")
        await interaction.delete_original_response()
        return None

    @app_commands.command(name="parking_status", description="View available parking spots")
    @app_commands.checks.cooldown(1, 10.0, key=lambda interaction: interaction.user.id)
    async def parking_status(self, interaction: discord.Interaction):
        """Summarize resident, guest, and staff parking availability."""
        cached_embed = self._get_cached_parking_status_embed()
        if cached_embed is not None:
            await interaction.response.send_message(embed=cached_embed, ephemeral=True)
            return

        async with self._parking_status_lock:
            cached_embed = self._get_cached_parking_status_embed()
            if cached_embed is not None:
                await interaction.response.send_message(embed=cached_embed, ephemeral=True)
                return

            now = datetime.now(LOCAL_TZ).replace(minute=0, second=0, microsecond=0)
            resident_cutoff = now + timedelta(days=7)
            raw_offers, raw_claims, guest_spots = await self.service.get_parking_data(now, resident_cutoff)

            offers_db = {}
            for row in raw_offers:
                spot_num = row["spot_number"]
                offers_db.setdefault(spot_num, []).append(
                    {
                        "start": datetime.fromisoformat(row["start_time"]).astimezone(LOCAL_TZ),
                        "end": datetime.fromisoformat(row["end_time"]).astimezone(LOCAL_TZ),
                    }
                )

            claims_db = {}
            for row in raw_claims:
                spot_num = row["spot_number"]
                claims_db.setdefault(spot_num, []).append(
                    {
                        "start": datetime.fromisoformat(row["start_time"]).astimezone(LOCAL_TZ),
                        "end": datetime.fromisoformat(row["end_time"]).astimezone(LOCAL_TZ),
                    }
                )

            lines = []
            all_spots = sorted(set(list(offers_db.keys()) + guest_spots))
            for spot_num in all_spots:
                spot_offers = offers_db.get(spot_num, [])
                spot_claims = sorted(claims_db.get(spot_num, []), key=lambda x: x["start"])
                is_guest = spot_num in guest_spots
                is_resident = not (spot_num == 998 or spot_num == 999)

                header, blocks = self.service.get_merged_availability(now, resident_cutoff, spot_offers, spot_claims,
                                                                      is_guest, is_resident)

                if not is_guest and header == "❌ Not Offered":
                    continue

                if blocks is None:
                    lines.append(f"**Spot {spot_num}**: {header}")
                    continue

                # Filter out the currently active block so it doesn't duplicate the header
                future_blocks = [block for block in blocks if not (block[0] <= now < block[1])]

                if not future_blocks:
                    lines.append(f"**Spot {spot_num}**: {header}")
                else:
                    detail = "\n".join(
                        [f"- NEXT {block[0].strftime('%a %I%p')}-{block[1].strftime('%a %I%p')}" for block in
                         future_blocks]
                    )
                    lines.append(f"**Spot {spot_num}**: {header}\n{detail}")

            # Determine staff cutoff (2 AM for Fri/Sat, 12 AM otherwise)
            is_weekend = now.weekday() in {4, 5}
            staff_cutoff = now.replace(hour=2, minute=0) + timedelta(days=1) if is_weekend else now.replace(hour=0,
                                                                                                            minute=0) + timedelta(
                days=1)

            staff_lines = []
            staff_offers = self.service.get_staff_availability_windows(now, staff_cutoff)
            for i, spot_num in enumerate(STAFF_SPOTS):
                spot_claims = sorted(claims_db.get(spot_num, []), key=lambda x: x["start"])
                header, blocks = self.service.get_merged_availability(now, staff_cutoff, staff_offers, spot_claims,
                                                                      is_resident=False)

                if not blocks:
                    staff_lines.append(f"**Spot {i + 1}**: {header}")
                    continue

                # Filter out the currently active block for staff as well
                future_blocks = [block for block in blocks if not (block[0] <= now < block[1])]

                if not future_blocks:
                    staff_lines.append(f"**Spot {i + 1}**: {header}")
                else:
                    detail = "\n".join(
                        [f"- NEXT {block[0].strftime('%I%p')}-{block[1].strftime('%I%p')}" for block in future_blocks]
                    )
                    staff_lines.append(f"**Spot {i + 1}**: {header}\n{detail}")

            embed = discord.Embed(
                title="Parking Status",
                color=discord.Color.blue(),
                timestamp=datetime.now(LOCAL_TZ),
            )
            res_value = "\n".join(lines) if lines else "No spots currently offered."
            if len(res_value) > 1024:
                res_value = res_value[:1020] + "..."

            staff_value = "\n".join(staff_lines)
            if len(staff_value) > 1024:
                staff_value = staff_value[:1020] + "..."

            embed.add_field(name="Resident/Guest Spots (Next 7 Days)", value=res_value, inline=False)
            embed.add_field(name="Staff Parking (Today)", value=staff_value, inline=False)
            embed.set_footer(text=f"{BOT_NAME} Parking System - Chicago Time")
            self._store_cached_parking_status_embed(embed)

        await interaction.response.send_message(embed=self._clone_embed(embed), ephemeral=True)

    async def cancel_spot_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str,
    ) -> list[app_commands.Choice[str]]:
        """Build autocomplete options for the caller's cancellable offers and reservations."""
        user_id = str(interaction.user.id)
        now = datetime.now(LOCAL_TZ)
        log_context = {"user_id": user_id, "current": current}

        try:
            offers, claims = await self.service.get_cancel_autocomplete_data(user_id, now)
            choices = []

            for offer in offers or []:
                start = datetime.fromisoformat(offer["start_time"]).astimezone(LOCAL_TZ)
                end = datetime.fromisoformat(offer["end_time"]).astimezone(LOCAL_TZ)
                label = (
                    f"Withdraw: Spot {offer['spot_number']} "
                    f"{start.strftime('%a %b')} {start.day} {start.strftime('%I:%M %p')}"
                    f" - {end.strftime('%a %b')} {end.day} {end.strftime('%I:%M %p')}"
                )
                if current.lower() in label.lower():
                    choices.append(app_commands.Choice(name=label, value=f"sig_offer_{offer['id']}"))

            for claim in claims or []:
                start = datetime.fromisoformat(claim["start_time"]).astimezone(LOCAL_TZ)
                end = datetime.fromisoformat(claim["end_time"]).astimezone(LOCAL_TZ)
                spot_label = "Staff" if claim["spot_number"] in STAFF_SPOTS else f"Spot {claim['spot_number']}"
                label = (
                    f"Cancel: {spot_label} "
                    f"{start.strftime('%a %b')} {start.day} {start.strftime('%I:%M %p')}"
                    f" - {end.strftime('%a %b')} {end.day} {end.strftime('%I:%M %p')}"
                )
                if current.lower() in label.lower():
                    choices.append(app_commands.Choice(name=label, value=f"sig_claim_{claim['id']}"))
        except Exception:
            logger.exception(
                "Parking cancel autocomplete failed",
                extra=log_context,
            )
            choices = []

        return await self._finalize_autocomplete(
            interaction,
            choices[:25],
            handler_name="Parking cancel",
            log_context=log_context,
        )

    @app_commands.command(name="cancel", description="Cancel your reservations or withdraw offers")
    @app_commands.autocomplete(spot=cancel_spot_autocomplete)
    async def cancel(self, interaction: discord.Interaction, spot: str):
        """Cancel the selected reservation or offered spot window."""
        if not spot.startswith("sig_"):
            return await interaction.response.send_message("❌ Please select an option from the list.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            _, action_type, record_id = spot.split("_", 2)
            success, msg, pings = await self.service.cancel_action(interaction.user.id, action_type, record_id)
        except asyncio.TimeoutError:
            logger.exception(
                "Parking cancel timed out in command handler",
                extra={"user_id": str(interaction.user.id), "spot_token": spot},
            )
            return await interaction.followup.send("❌ Cancel timed out. Please try again in a moment.", ephemeral=True)
        except Exception:
            logger.exception(
                "Parking cancel failed in command handler",
                extra={"user_id": str(interaction.user.id), "spot_token": spot},
            )
            return await interaction.followup.send(
                "❌ Something went wrong while canceling that entry.",
                ephemeral=True,
            )

        if pings:
            try:
                await interaction.channel.send(f"⚠️ **Attention {', '.join(pings)}**: {msg}")
            except Exception:
                logger.exception(
                    "Parking cancel notification ping failed",
                    extra={"user_id": str(interaction.user.id), "spot_token": spot, "pings": pings},
                )

        await interaction.followup.send(msg, ephemeral=True)

    @app_commands.command(name="parking_help", description="How to use the parking system")
    async def parking_help(self, interaction: discord.Interaction):
        """Send an overview of parking commands, rules, and guest spot details."""
        guest_list_str = await self.service.get_guest_spot_list()

        embed = discord.Embed(
            title="🚗 Parking System Guide",
            description="Manage resident, guest, and staff parking spots efficiently.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📍 General Commands",
            value=(
                "`/parking_status` - View all currently available and reserved spots.\n"
                "`/my_parking` - View your active offers and reservations.\n"
                "`/cancel [spot]` - Cancel your reservation or withdraw your offer."
            ),
            inline=False,
        )
        embed.add_field(
            name="🏠 Resident & Guest Spots",
            value=(
                f"**Guest Spot(s): {guest_list_str}**\n"
                "Always available to claim up to 7 days in advance.\n\n"
                "**All parking spots are 1-33 and 41-46.**\n"
                "Spots currently marked as guest spots can be claimed directly.\n"
                "Any spot not marked as a guest spot must be offered by the owner first.\n\n"
                "`/offer_spot` - Owners list their spot for others to use.\n"
                "`/claim_spot` - Reserve an offered resident spot or the guest spot.\n"
                f"   *Note: Claims must be between {MINIMUM_RESERVATION_HOURS} hours and {MAXIMUM_RESERVATION_DAYS} days long.* "
            ),
            inline=False,
        )
        embed.add_field(
            name="⛪ Staff Parking",
            value=(
                "`/claim_staff` - Reserve one of the 2 available staff spots.\n"
                "**Blackout Rules:** Staff spots cannot be reserved during:\n"
                "• Mon-Fri: Before 5:00 PM\n"
                "• Sunday: 2:00 AM - 2:00 PM"
            ),
            inline=False,
        )
        embed.set_footer(text=f"{BOT_NAME} Parking System - Chicago Time")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Register the parking cog with the bot."""
    await bot.add_cog(Parking(bot))

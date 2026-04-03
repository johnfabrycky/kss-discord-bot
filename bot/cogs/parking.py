from collections import Counter
import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.parking_service import ParkingService
from bot.utils.constants import LOCAL_TZ, STAFF_SPOTS, VALID_SPOTS, WEEKDAYS

logger = logging.getLogger(__name__)


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
        self.service = ParkingService()

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
        embed.add_field(name="📥 My Reservations", value="\n".join(claim_lines) or "No active reservations.", inline=False)

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
        if spot not in VALID_SPOTS:
            return await interaction.response.send_message(f"❌ Spot {spot} is invalid.", ephemeral=True)

        start, end, duration = self.service.parse_range(start_day.value, start_time.value, end_day.value, end_time.value)
        if duration < timedelta(hours=2):
            return await interaction.response.send_message("❌ Offers must be at least 2 hours.", ephemeral=True)

        success, msg = await self.service.create_offers(interaction.user.id, spot, start, end, weeks)
        await interaction.response.send_message(msg, ephemeral=not success)

    @app_commands.command(name="claim_spot", description="Reserve a resident or guest spot")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def claim_spot(
        self,
        interaction: discord.Interaction,
        spot: int,
        start_day: app_commands.Choice[int],
        start_time: app_commands.Choice[str],
        end_day: app_commands.Choice[int],
        end_time: app_commands.Choice[str],
    ):
        """Reserve an offered resident spot or a designated guest spot."""
        if spot not in VALID_SPOTS:
            return await interaction.response.send_message("Invalid spot.", ephemeral=True)

        start, end, duration = self.service.parse_range(start_day.value, start_time.value, end_day.value, end_time.value)
        if duration < timedelta(hours=2) or duration > timedelta(days=7):
            return await interaction.response.send_message("❌ Must be between 2h and 7d.", ephemeral=True)

        success, msg = await self.service.claim_resident_spot(interaction.user.id, spot, start, end)
        await interaction.response.send_message(msg, ephemeral=not success)

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
        start, end, _duration = self.service.parse_range(start_day.value, start_time.value, end_day.value, end_time.value)
        success, msg = await self.service.claim_staff_spot(interaction.user.id, start, end)
        await interaction.response.send_message(msg, ephemeral=not success)

    @app_commands.command(name="parking_status", description="View available parking spots")
    async def parking_status(self, interaction: discord.Interaction):
        """Summarize resident, guest, and staff parking availability for the next week."""
        now = datetime.now(LOCAL_TZ).replace(minute=0, second=0, microsecond=0)
        cutoff = now + timedelta(days=7)
        raw_offers, raw_claims, guest_spots = await self.service.get_parking_data(now, cutoff)

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

            header, blocks = self.service.get_merged_availability(now, cutoff, spot_offers, spot_claims, is_guest)
            detail = " | ".join(
                [
                    f"{'🟢' if block[0] <= now < block[1] else '📅'} "
                    f"{block[0].strftime('%a %I%p')}-{block[1].strftime('%a %I%p')}"
                    for block in blocks
                ]
            )
            lines.append(f"**Spot {spot_num}**: {header}\n└ *Free:* {detail or '❌ Fully Booked'}")

        is_blk = self.service.is_blackout(now, now + timedelta(hours=1))
        staff_claims = claims_db.get(STAFF_SPOTS[0], []) + claims_db.get(STAFF_SPOTS[1], [])
        active_staff = len([claim for claim in staff_claims if claim["start"] <= now < claim["end"]])
        if is_blk:
            staff_status = "❌ Closed (Blackout)"
        else:
            free_count = len(STAFF_SPOTS) - active_staff
            staff_status = f"✅ {free_count}/{len(STAFF_SPOTS)} Free"

        embed = discord.Embed(
            title="🚗 Parking Status (Next 7 Days)",
            color=discord.Color.blue(),
            timestamp=datetime.now(LOCAL_TZ),
        )
        res_value = "\n".join(lines) if lines else "No spots currently offered."
        if len(res_value) > 1024:
            res_value = res_value[:1020] + "..."

        embed.add_field(name="Resident/Guest Spots", value=res_value, inline=False)
        embed.add_field(name="Staff Parking", value=staff_status, inline=False)
        embed.set_footer(text="Gerald Parking System • Chicago Time")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cancel_spot_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Build autocomplete options for the caller's cancellable offers and reservations."""
        user_id = str(interaction.user.id)
        choices = []
        now = datetime.now(LOCAL_TZ)

        try:
            offers_res = (
                self.service.supabase.table("parking_offers")
                .select("*")
                .eq("owner_id", user_id)
                .gt("end_time", now.isoformat())
                .execute()
            )
            claims_res = (
                self.service.supabase.table("parking_reservations")
                .select("*")
                .eq("claimer_id", user_id)
                .gt("end_time", now.isoformat())
                .execute()
            )

            for offer in offers_res.data or []:
                start = datetime.fromisoformat(offer["start_time"]).astimezone(LOCAL_TZ)
                end = datetime.fromisoformat(offer["end_time"]).astimezone(LOCAL_TZ)
                label = (
                    f"Withdraw: Spot {offer['spot_number']} "
                    f"{start.strftime('%a %b')} {start.day} {start.strftime('%I:%M %p')}"
                    f" - {end.strftime('%a %b')} {end.day} {end.strftime('%I:%M %p')}"
                )
                if current.lower() in label.lower():
                    choices.append(app_commands.Choice(name=label, value=f"sig_offer_{offer['id']}"))

            for claim in claims_res.data or []:
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

        except Exception as e:
            logger.exception(
                "Parking cancel autocomplete failed",
                extra={
                    "user_id": user_id,
                    "current": current,
                },
            )
            return []

        return choices[:25]

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
                extra={
                    "user_id": str(interaction.user.id),
                    "spot_token": spot,
                },
            )
            return await interaction.followup.send(
                "❌ Cancel timed out. Please try again in a moment.",
                ephemeral=True,
            )
        except Exception:
            logger.exception(
                "Parking cancel failed in command handler",
                extra={
                    "user_id": str(interaction.user.id),
                    "spot_token": spot,
                },
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
                    extra={
                        "user_id": str(interaction.user.id),
                        "spot_token": spot,
                        "pings": pings,
                    },
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
                "`/cancel [spot]` - Cancel your reservation or withdraw your offer.\n"
                "   *Leave [spot] blank to cancel Staff reservations.*"
            ),
            inline=False,
        )
        embed.add_field(
            name="🏠 Resident & Guest Spots",
            value=(
                f"**Guest Spot(s): {guest_list_str}**\n"
                "Always available to claim up to 7 days in advance.\n\n"
                "**Resident Spots (1-33, 41-45):** Must be offered by the owner first.\n\n"
                "`/offer_spot` - Owners list their spot for others to use.\n"
                "`/claim_spot` - Reserve an offered resident spot or the guest spot.\n"
                "   *Note: Claims must be between 2 hours and 7 days long.* "
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
        embed.set_footer(text="All times are in America/Chicago (CST/CDT)")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Register the parking cog with the bot."""
    await bot.add_cog(Parking(bot))

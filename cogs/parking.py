from collections import Counter
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from helpers.constants import WEEKDAYS, VALID_SPOTS, LOCAL_TZ, STAFF_SPOTS
from helpers.parking_service import ParkingService


class Parking(commands.Cog):
    """Slash commands for offering, claiming, and viewing parking availability."""

    day_choices = [app_commands.Choice(name=name, value=obj.weekday) for obj, name in WEEKDAYS]
    time_choices = [app_commands.Choice(name=f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}",
                                        value=f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}") for i in range(24)]

    def __init__(self, bot):
        """Initialize the parking cog and its shared service layer."""
        self.bot = bot
        self.service = ParkingService()

    # Add this back to your Parking class in parking.py if you want to keep main.py as is:
    async def initialize_parking_spots(self):
        """Ensure the configured parking spots exist in the backing database."""
        await self.service.initialize_spots()  # You'd need to create this in Service

    @app_commands.command(name="my_parking", description="View your active offers and reservations")
    async def my_parking(self, interaction: discord.Interaction):
        """Show the caller's active offers and reservations in one ledger."""
        user_id = str(interaction.user.id)
        now = datetime.now(LOCAL_TZ)

        # Ask the Service for the user's data
        raw_offers, raw_claims = await self.service.get_user_activity(user_id)

        embed = discord.Embed(
            title="📋 My Parking Activity",
            color=discord.Color.green(),
            timestamp=now
        )

        # 1. Format Offers
        offer_groups = Counter()
        for off in (raw_offers or []):
            start = datetime.fromisoformat(off['start_time']).astimezone(LOCAL_TZ)
            end = datetime.fromisoformat(off['end_time']).astimezone(LOCAL_TZ)
            # Create a unique key based on the day of week and time
            time_key = f"**Spot {off['spot_number']}**: {start.strftime('%a %I%p')} — {end.strftime('%a %I%p')}"
            offer_groups[time_key] += 1

        offer_lines = [f"{key} (x{count})" if count > 1 else key for key, count in offer_groups.items()]
        embed.add_field(name="📤 My Offers", value="\n".join(offer_lines) or "No active offers.", inline=False)

        # 2. Format Claims (Reservations)
        claim_groups = Counter()
        for c in (raw_claims or []):
            start = datetime.fromisoformat(c['start_time']).astimezone(LOCAL_TZ)
            end = datetime.fromisoformat(c['end_time']).astimezone(LOCAL_TZ)
            spot_label = "Staff Spot" if c['spot_number'] in STAFF_SPOTS else f"Spot {c['spot_number']}"
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
                         start_day: app_commands.Choice[int], start_time: app_commands.Choice[str],
                         end_day: app_commands.Choice[int], end_time: app_commands.Choice[str],
                         weeks: app_commands.Range[int, 1, 12] = 1):
        """Offer a resident parking spot for a recurring weekly time window."""
        if spot not in VALID_SPOTS:
            return await interaction.response.send_message(f"❌ Spot {spot} is invalid.", ephemeral=True)

        start, end, duration = self.service.parse_range(start_day.value, start_time.value, end_day.value,
                                                        end_time.value)

        # Validation
        if duration < timedelta(hours=2):
            return await interaction.response.send_message("❌ Offers must be at least 2 hours.", ephemeral=True)

        # We still need a small method in Service to handle the actual INSERT for offers
        success, msg = await self.service.create_offers(interaction.user.id, spot, start, end, weeks)
        await interaction.response.send_message(msg, ephemeral=not success)

    @app_commands.command(name="claim_spot", description="Reserve a resident or guest spot")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def claim_spot(self, interaction: discord.Interaction, spot: int,
                         start_day: app_commands.Choice[int], start_time: app_commands.Choice[str],
                         end_day: app_commands.Choice[int], end_time: app_commands.Choice[str]):
        """Reserve an offered resident spot or a designated guest spot."""
        if spot not in VALID_SPOTS: return await interaction.response.send_message("Invalid spot.", ephemeral=True)
        start, end, duration = self.service.parse_range(start_day.value, start_time.value, end_day.value,
                                                        end_time.value)
        if duration < timedelta(hours=2) or duration > timedelta(days=7):
            return await interaction.response.send_message("❌ Must be between 2h and 7d.", ephemeral=True)

        success, msg = await self.service.claim_resident_spot(interaction.user.id, spot, start, end)
        await interaction.response.send_message(msg, ephemeral=not success)

    @app_commands.command(name="claim_staff", description="Reserve a staff spot")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def claim_staff(self, interaction: discord.Interaction,
                          start_day: app_commands.Choice[int], start_time: app_commands.Choice[str],
                          end_day: app_commands.Choice[int], end_time: app_commands.Choice[str]):
        """Reserve one of the rotating staff spots if blackout rules allow it."""
        start, end, duration = self.service.parse_range(start_day.value, start_time.value, end_day.value,
                                                        end_time.value)
        success, msg = await self.service.claim_staff_spot(interaction.user.id, start, end)
        await interaction.response.send_message(msg, ephemeral=not success)

    @app_commands.command(name="parking_status", description="View available parking spots")
    async def parking_status(self, interaction: discord.Interaction):
        """Summarize resident, guest, and staff parking availability for the next week."""
        # 1. Setup timeframes
        now = datetime.now(LOCAL_TZ).replace(minute=0, second=0, microsecond=0)
        cutoff = now + timedelta(days=7)

        # 2. Fetch Data from Service
        raw_offers, raw_claims, guest_spots = await self.service.get_parking_data(now, cutoff)

        # 3. Organize Data into Spot-specific dictionaries
        offers_db = {}
        for row in raw_offers:
            s = row['spot_number']
            offers_db.setdefault(s, []).append({
                "start": datetime.fromisoformat(row['start_time']).astimezone(LOCAL_TZ),
                "end": datetime.fromisoformat(row['end_time']).astimezone(LOCAL_TZ)
            })

        claims_db = {}
        for row in raw_claims:
            s = row['spot_number']
            claims_db.setdefault(s, []).append({
                "start": datetime.fromisoformat(row['start_time']).astimezone(LOCAL_TZ),
                "end": datetime.fromisoformat(row['end_time']).astimezone(LOCAL_TZ)
            })

        # 4. Process Every Spot
        lines = []
        all_spots = sorted(set(list(offers_db.keys()) + guest_spots))

        for s in all_spots:
            spot_offers = offers_db.get(s, [])
            spot_claims = sorted(claims_db.get(s, []), key=lambda x: x['start'])
            is_guest = s in guest_spots

            # Call our Service helper for the heavy math
            header, blocks = self.service.get_merged_availability(
                now, cutoff, spot_offers, spot_claims, is_guest
            )

            # Format the "Free" details line
            detail = " | ".join([
                f"{'🟢' if b[0] <= now < b[1] else '📅'} {b[0].strftime('%a %I%p')}-{b[1].strftime('%a %I%p')}"
                for b in blocks
            ])

            lines.append(f"**Spot {s}**: {header}\n└ *Free:* {detail or '❌ Fully Booked'}")

        # 5. Staff Spot Logic
        is_blk = self.service.is_blackout(now, now + timedelta(hours=1))
        staff_claims = claims_db.get(STAFF_SPOTS[0], []) + claims_db.get(STAFF_SPOTS[1], [])
        active_staff = len([t for t in staff_claims if t["start"] <= now < t["end"]])

        if is_blk:
            staff_status = "❌ Closed (Blackout)"
        else:
            free_count = len(STAFF_SPOTS) - active_staff
            staff_status = f"✅ {free_count}/{len(STAFF_SPOTS)} Free"

        # 6. Build and Send Embed
        embed = discord.Embed(
            title="🚗 Parking Status (Next 7 Days)",
            color=discord.Color.blue(),
            timestamp=datetime.now(LOCAL_TZ)
        )

        # Split lines into chunks if they exceed Discord's field limit (1024 chars)
        res_value = "\n".join(lines) if lines else "No spots currently offered."
        if len(res_value) > 1024:
            res_value = res_value[:1020] + "..."

        embed.add_field(name="Resident/Guest Spots", value=res_value, inline=False)
        embed.add_field(name="Staff Parking", value=staff_status, inline=False)
        embed.set_footer(text="Gerald Parking System • Chicago Time")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cancel_spot_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        """Build autocomplete options for the caller's cancellable offers and reservations."""
        user_id = str(interaction.user.id)
        choices = []
        now = datetime.now(LOCAL_TZ)

        try:
            # 1. Fetch raw data from the service
            # (Note: You can reuse get_parking_data or add a specific 'get_user_activity' to Service)
            offers_res = self.service.supabase.table("parking_offers").select("*").eq("owner_id", user_id).gt(
                "end_time", now.isoformat()).execute()
            claims_res = self.service.supabase.table("parking_reservations").select("*").eq("claimer_id", user_id).gt(
                "end_time", now.isoformat()).execute()

            # 2. Process Offers
            offer_seen = set()
            for off in (offers_res.data or []):
                start = datetime.fromisoformat(off['start_time']).astimezone(LOCAL_TZ)
                end = datetime.fromisoformat(off['end_time']).astimezone(LOCAL_TZ)

                # Signature matches the parsing logic in your Service
                sig = f"sig_offer_{off['spot_number']}_{start.weekday()}_{start.hour}_{end.hour}"
                label = f"Withdraw ALL: Spot {off['spot_number']} {start.strftime('%a %I%p')}-{end.strftime('%I%p')}"

                if sig not in offer_seen and current.lower() in label.lower():
                    choices.append(app_commands.Choice(name=label, value=sig))
                    offer_seen.add(sig)

            # 3. Process Claims
            claim_seen = set()
            for c in (claims_res.data or []):
                start = datetime.fromisoformat(c['start_time']).astimezone(LOCAL_TZ)
                end = datetime.fromisoformat(c['end_time']).astimezone(LOCAL_TZ)
                spot_label = "Staff" if c['spot_number'] in STAFF_SPOTS else f"Spot {c['spot_number']}"

                sig = f"sig_claim_{c['spot_number']}_{start.weekday()}_{start.hour}_{end.hour}"
                label = f"Cancel ALL: {spot_label} {start.strftime('%a %I%p')}-{end.strftime('%I%p')}"

                if sig not in claim_seen and current.lower() in label.lower():
                    choices.append(app_commands.Choice(name=label, value=sig))
                    claim_seen.add(sig)

        except Exception as e:
            print(f"Autocomplete Error: {e}")
            return []

        return choices[:25]  # Discord limit

    @app_commands.command(name="cancel", description="Cancel your reservations or withdraw offers")
    @app_commands.autocomplete(spot=cancel_spot_autocomplete)  # Link it here!
    async def cancel(self, interaction: discord.Interaction, spot: str):
        """Cancel the selected recurring reservation or offered spot window."""
        if not spot.startswith("sig_"):
            return await interaction.response.send_message("❌ Please select an option from the list.", ephemeral=True)

        p = spot.split("_")
        # p[1]=type, p[2]=spot_num, p[3]=weekday, p[4]=start_h, p[5]=end_h
        success, msg, pings = await self.service.cancel_action(
            interaction.user.id, p[1], int(p[2]), int(p[3]), int(p[4]), int(p[5])
        )

        if pings:
            await interaction.channel.send(f"⚠️ **Attention {', '.join(pings)}**: {msg}")

        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="parking_help", description="How to use the parking system")
    async def parking_help(self, interaction: discord.Interaction):
        """Send an overview of parking commands, rules, and guest spot details."""
        # 1. Fetch formatted guest list string from the Service
        guest_list_str = await self.service.get_guest_spot_list()

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
                "`/my_parking` - View your active offers and reservations.\n"
                "`/cancel [spot]` - Cancel your reservation or withdraw your offer.\n"
                "   *Leave [spot] blank to cancel Staff reservations.*"
            ),
            inline=False
        )

        # Resident/Guest Section
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
    """Register the parking cog with the bot."""
    await bot.add_cog(Parking(bot))

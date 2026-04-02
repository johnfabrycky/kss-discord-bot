import discord
from discord import app_commands
from discord.ext import commands
from helpers.constants import WEEKDAYS, VALID_SPOTS, LOCAL_TZ, STAFF_SPOTS
from helpers.parking_service import ParkingService
from datetime import datetime, timedelta


class Parking(commands.Cog):
    day_choices = [app_commands.Choice(name=name, value=obj.weekday) for obj, name in WEEKDAYS]
    time_choices = [app_commands.Choice(name=f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}",
                                        value=f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}") for i in range(24)]

    def __init__(self, bot):
        self.bot = bot
        self.service = ParkingService()

    @app_commands.command(name="offer_spot", description="List your spot as available")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def offer_spot(self, interaction: discord.Interaction, spot: int,
                         start_day: app_commands.Choice[int], start_time: app_commands.Choice[str],
                         end_day: app_commands.Choice[int], end_time: app_commands.Choice[str],
                         weeks: int = 1):
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

    @app_commands.command(name="claim_spot")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def claim_spot(self, interaction: discord.Interaction, spot: int,
                         start_day: app_commands.Choice[int], start_time: app_commands.Choice[str],
                         end_day: app_commands.Choice[int], end_time: app_commands.Choice[str]):
        if spot not in VALID_SPOTS: return await interaction.response.send_message("Invalid spot.", ephemeral=True)
        start, end, duration = self.service.parse_range(start_day.value, start_time.value, end_day.value,
                                                        end_time.value)
        if duration < timedelta(hours=2) or duration > timedelta(days=7):
            return await interaction.response.send_message("❌ Must be between 2h and 7d.", ephemeral=True)

        success, msg = await self.service.claim_resident_spot(interaction.user.id, spot, start, end)
        await interaction.response.send_message(msg, ephemeral=not success)

    @app_commands.command(name="claim_staff")
    @app_commands.choices(start_day=day_choices, end_day=day_choices, start_time=time_choices, end_time=time_choices)
    async def claim_staff(self, interaction: discord.Interaction,
                          start_day: app_commands.Choice[int], start_time: app_commands.Choice[str],
                          end_day: app_commands.Choice[int], end_time: app_commands.Choice[str]):
        start, end, duration = self.service.parse_range(start_day.value, start_time.value, end_day.value,
                                                        end_time.value)
        success, msg = await self.service.claim_staff_spot(interaction.user.id, start, end)
        await interaction.response.send_message(msg, ephemeral=not success)

    @app_commands.command(name="parking_status", description="View available parking spots")
    async def parking_status(self, interaction: discord.Interaction):
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

    @app_commands.command(name="cancel")
    async def cancel(self, interaction: discord.Interaction, spot: str):
        if not spot.startswith("sig_"): return await interaction.response.send_message("❌ Select from list.",
                                                                                       ephemeral=True)
        p = spot.split("_")
        success, msg, pings = await self.service.cancel_action(interaction.user.id, p[1], int(p[2]), int(p[3]),
                                                               int(p[4]), int(p[5]))

        if pings: await interaction.channel.send(f"⚠️ **Attention {', '.join(pings)}**: {msg}")
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="parking_help")
    async def parking_help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🚗 Parking Guide", color=discord.Color.blue())
        embed.add_field(name="Resident Spots", value="1-33, 41-45 (Must be offered first)")
        embed.add_field(name="Guest Spot", value="46 (Always open to claim)")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Parking(bot))
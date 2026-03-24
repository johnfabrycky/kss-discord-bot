import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client
from cogs.helpers.swapview import SwapView
import os


class Shifts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        self.supabase: Client = create_client(url, key)

    SHIFT_TYPES = ["Lunch Prep", "Lunch Cleanup", "Dinner Prep", "Dinner Cleanup", "Saturday Dinner"]
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    # --- AUTOCOMPLETE LOGIC ---
    async def shift_autocomplete(self, interaction: discord.Interaction, current: str):
        # Fetch shifts that haven't been claimed yet
        response = (self.supabase.table("shifts")
                    .select("*")
                    .is_("claimed_by_id", "null")
                    .neq("seller_id", str(interaction.user.id))
                    .execute())
        available = response.data

        # Filter based on what the user is typing
        choices = []
        for s in available:
            label = f"{s['shift_type']} ({s['day_of_week']}) - ${s['price']:.2f}"
            if current.lower() in label.lower():
                # Name is what they see, Value is the ID the bot uses
                choices.append(app_commands.Choice(name=label, value=str(s['id'])))

        # Discord limits autocomplete to 25 choices
        return choices[:25]

    async def target_user_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)

        # 1. Fetch all shifts that are either claimed by someone or offered by a seller
        # We need this to see who actually HAS a shift to trade
        response = self.supabase.table("shifts").select("seller_id, seller_name, claimed_by_id").execute()

        # 2. Use a dictionary to store unique users {user_id: user_name}
        valid_targets = {}

        for s in response.data:
            sid = s['seller_id']
            sname = s['seller_name']
            cid = s['claimed_by_id']

            # Case A: If the shift is unclaimed, the seller is the 'owner'
            if cid is None and sid != user_id:
                valid_targets[sid] = sname
            # Case B: If the shift is claimed, the claimer is the 'owner'
            # Note: We can't get the claimer's name from the DB easily here
            # so we'll focus on sellers/known names or use discord cache
            elif cid is not None and cid != user_id:
                # We'll try to get the member name from Discord's cache
                member = interaction.guild.get_member(int(cid))
                if member:
                    valid_targets[cid] = member.display_name

        # 3. Filter based on what the user is typing
        choices = []
        for uid, name in valid_targets.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=uid))

        return choices[:25]

    @app_commands.command(name="offer_shift",
                          description="Offer a shift (if you claimed it, this puts it back up for hire)")
    @app_commands.choices(
        shift_type=[app_commands.Choice(name=st, value=st) for st in SHIFT_TYPES],
        day=[app_commands.Choice(name=d, value=d) for d in DAYS]
    )
    async def offer(self, interaction: discord.Interaction, shift_type: str, day: str, price: float):
        user_id = str(interaction.user.id)

        # Check if you currently hold this shift as a CLAIM
        existing = self.supabase.table("shifts").select("*") \
            .eq("claimed_by_id", user_id) \
            .eq("shift_type", shift_type) \
            .eq("day_of_week", day).execute()

        if existing.data:
            # You already claimed this! We "re-list" it.
            # We set claimed_by_id back to NULL and update the seller to YOU.
            shift_id = existing.data[0]['id']
            self.supabase.table("shifts").update({
                "seller_id": user_id,
                "seller_name": interaction.user.display_name,
                "price": price,
                "claimed_by_id": None  # It's back on the market
            }).eq("id", shift_id).execute()

            await interaction.response.send_message(
                f"♻️ You've put your claimed **{shift_type}** back on the market for **${price:.2f}**.")

        else:
            # Standard offer for a shift you originally owned
            payload = {
                "seller_id": user_id,
                "seller_name": interaction.user.display_name,
                "shift_type": shift_type,
                "day_of_week": day,
                "price": price
            }
            self.supabase.table("shifts").insert(payload).execute()
            await interaction.response.send_message(f"✅ **Shift Posted!** {shift_type} on {day} for ${price:.2f}.")

    # 1. Autocomplete for shifts the Proposer CURRENTLY OWNS
    async def my_owned_shifts_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        # Finds shifts where you are the current owner or original seller (if unclaimed)
        response = (self.supabase.table("shifts")
                .select("*")
                .eq("seller_id", user_id)
                .is_("claimed_by_id", "null")
                .execute())

        return [
            app_commands.Choice(name=f"{s['shift_type']} ({s['day_of_week']})", value=str(s['id']))
            for s in response.data if current.lower() in f"{s['shift_type']} {s['day_of_week']}".lower()
        ][:25]

    # 2. Autocomplete for shifts the TARGET USER currently owns
    async def target_shifts_autocomplete(self, interaction: discord.Interaction, current: str):
        # 1. Grab the target from the namespace
        target = interaction.namespace.target_user

        # 2. Logic Check: If no user is selected OR if the user is YOU, return nothing
        if not target or str(target.id if hasattr(target, 'id') else target) == str(interaction.user.id):
            return []

        # 3. Extract the ID safely
        target_id = str(target.id) if hasattr(target, 'id') else str(target)

        try:
            # Find shifts where the target is the owner OR the unclaimed seller
            response = (self.supabase.table("shifts")
                     .select("*")
                     .eq("seller_id", target_id)
                     .is_("claimed_by_id", "null")
                     .execute())

            return [
                app_commands.Choice(name=f"{s['shift_type']} ({s['day_of_week']})", value=str(s['id']))
                for s in response.data
                if current.lower() in f"{s['shift_type']} {s['day_of_week']}".lower()
            ][:25]
        except Exception as e:
            print(f"⚠️ Target Autocomplete Error: {e}")
            return []

    @app_commands.command(name="swap_shift", description="Propose a specific 1-for-1 shift trade")
    @app_commands.autocomplete(my_shift=my_owned_shifts_autocomplete, target_user=target_user_autocomplete, their_shift=target_shifts_autocomplete)
    async def swap(self, interaction: discord.Interaction, target_user: str, my_shift: str,
                   their_shift: str):
        # 1. Validation Guard: Check if inputs are actually numeric IDs
        if not (my_shift.isdigit() and their_shift.isdigit()):
            return await interaction.response.send_message(
                "❌ Please select a shift from the search results rather than typing it manually.",
                ephemeral=True
            )

        target_id = int(target_user)
        target_member = interaction.guild.get_member(target_id)

        if target_member is None:
            try:
                target_member = await interaction.guild.fetch_member(target_id)
            except discord.NotFound:
                return await interaction.response.send_message("❌ Could not find that user in this server.",
                                                               ephemeral=True)

        # 2. Proceed with the rest of your logic using int() safely
        res_p = self.supabase.table("shifts").select("*").eq("id", int(my_shift)).execute()
        res_t = self.supabase.table("shifts").select("*").eq("id", int(their_shift)).execute()

        if not res_p.data or not res_t.data:
            return await interaction.response.send_message("❌ One of those shifts is no longer available.",
                                                           ephemeral=True)

        p_data = res_p.data[0]
        t_data = res_t.data[0]

        # Updated Ownership Check
        target_id_str = str(target_member.id)
        is_claimer = t_data.get('claimed_by_id') == target_id_str
        is_unclaimed_seller = t_data.get('seller_id') == target_id_str and t_data.get('claimed_by_id') is None

        if not (is_claimer or is_unclaimed_seller):
            return await interaction.response.send_message(
                f"❌ {target_member.display_name} doesn't seem to own that shift anymore.",
                ephemeral=True
            )

        view = SwapView(interaction.user, target_user, p_data, t_data, self.supabase)

        await interaction.response.send_message(
            f"📩 {target_member.mention}, **{interaction.user.display_name}** proposes a swap:\n"
            f"⬆️ **Giving:** {p_data['shift_type']} ({p_data['day_of_week']})\n"
            f"⬇️ **Taking:** {t_data['shift_type']} ({t_data['day_of_week']})\n"
            f"Do you accept?",
            view=view
        )

    @app_commands.command(name="view_market", description="See all available shifts for hire")
    async def view_market(self, interaction: discord.Interaction):
        # 1. Immediately tell Discord to wait (gives you more than 3 seconds)
        await interaction.response.defer(ephemeral=True)

        try:
            # 2. Perform the database work
            response = self.supabase.table("shifts").select("*").is_("claimed_by_id", "null").execute()
            available = response.data

            if not available:
                # Use followup.send because response has already been deferred
                return await interaction.followup.send("There are no shifts currently available.", ephemeral=True)

            embed = discord.Embed(title="🛒 Available Shifts", color=discord.Color.green())
            for s in available:
                embed.add_field(
                    name=f"{s['shift_type']} - {s['day_of_week']}",
                    value=f"💰 **Bounty:** ${s['price']:.2f}\n👤 **Offered by:** {s['seller_name']}",
                    inline=False
                )

            # 3. Use followup.send to deliver the final embed
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"Error in view_market: {e}")
            await interaction.followup.send("❌ An error occurred while fetching the market data.", ephemeral=True)

    @app_commands.command(name="claim_shift", description="Take a shift from the market")
    @app_commands.autocomplete(shift=shift_autocomplete)
    async def claim(self, interaction: discord.Interaction, shift: str):
        # 1. Fetch the data using the 'shift' string (which is the ID)
        response = self.supabase.table("shifts").select("*").eq("id", int(shift)).execute()

        if not response.data:
            return await interaction.response.send_message("❌ Shift no longer available.", ephemeral=True)

        # We rename the dictionary variable to 'data' so 'shift' stays an ID string
        data = response.data[0]
        seller_name = data['seller_name']
        price = data['price']
        shift_name = data['shift_type']
        day = data['day_of_week']

        # 2. Logic Check: Prevent self-claiming
        if data["seller_id"] == str(interaction.user.id):
            return await interaction.response.send_message("❌ You can't claim your own shift!", ephemeral=True)

        # 3. Update the record: 'shift' is still the ID string, so int(shift) works!
        self.supabase.table("shifts").update({"claimed_by_id": str(interaction.user.id)}).eq("id", int(shift)).execute()

        # 4. Final confirmation message
        await interaction.response.send_message(
            f"🤝 **Shift Claimed!** {interaction.user.mention}, you've taken the **{shift_name}** on **{day}** from **{seller_name}** for **${price:.2f}**."
        )

    @app_commands.command(name="my_shifts", description="View your offers and claims")
    async def my_shifts(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # Offers: Where you are the seller and nobody has taken it yet
        offers = self.supabase.table("shifts").select("*").eq("seller_id", user_id).is_("claimed_by_id",
                                                                                        "null").execute()

        # Claims: Where you are the current claimer
        claims = self.supabase.table("shifts").select("*").eq("claimed_by_id", user_id).execute()

        embed = discord.Embed(title="📋 Shift Ledger", color=discord.Color.blue())

        off_list = [f"• **{s['shift_type']}** ({s['day_of_week']}) - ${s['price']:.2f}" for s in offers.data]
        embed.add_field(name="📤 My Active Offers", value="\n".join(off_list) or "None", inline=False)

        clm_list = [f"• **{s['shift_type']}** ({s['day_of_week']}) - ${s['price']:.2f}" for s in claims.data]
        embed.add_field(name="📥 My Current Claims", value="\n".join(clm_list) or "None", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Autocomplete for shifts the user has posted but are not yet claimed
    async def cancel_autocomplete(self, interaction: discord.Interaction, current: str):
        response = self.supabase.table("shifts").select("*") \
            .eq("seller_id", str(interaction.user.id)) \
            .is_("claimed_by_id", "null") \
            .execute()

        choices = []
        for s in response.data:
            label = f"Cancel: {s['shift_type']} ({s['day_of_week']}) - ${s['price']:.2f}"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=str(s['id'])))

        return choices[:25]

    @app_commands.command(name="cancel_shift", description="Remove one of your shift offers from the market")
    @app_commands.autocomplete(shift=cancel_autocomplete)
    async def cancel(self, interaction: discord.Interaction, shift: str):
        # We use 'shift' as the ID string to keep your preferred UI label

        # 1. Attempt to delete. We add the seller_id check as a security layer.
        response = self.supabase.table("shifts").delete() \
            .eq("id", int(shift)) \
            .eq("seller_id", str(interaction.user.id)) \
            .is_("claimed_by_id", "null") \
            .execute()

        # 2. Check if anything was actually deleted
        if not response.data:
            return await interaction.response.send_message(
                "❌ **Error:** Could not cancel. The shift may have already been claimed or doesn't belong to you.",
                ephemeral=True
            )

        data = response.data[0]
        await interaction.response.send_message(
            f"🗑️ **Offer Cancelled:** Your **{data['shift_type']}** on **{data['day_of_week']}** has been removed.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Shifts(bot))
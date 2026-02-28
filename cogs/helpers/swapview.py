import discord
#
# class SwapView(discord.ui.View):
#     def __init__(self, proposer, target, proposer_shift_id, supabase):
#         super().__init__(timeout=60)
#         self.proposer = proposer
#         self.target = target
#         self.proposer_shift_id = proposer_shift_id
#         self.supabase = supabase
#
#     @discord.ui.button(label="Accept Swap Request", style=discord.ButtonStyle.green)
#     async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
#         if interaction.user.id != self.target.id:
#             return await interaction.response.send_message("This isn't your swap to accept!", ephemeral=True)
#
#         # Fetch the Target's available shifts to trade back
#         response = self.supabase.table("shifts").select("*").eq("claimed_by_id", str(self.target.id)).execute()
#
#         if not response.data:
#             return await interaction.response.send_message("You don't have any shifts to trade back!", ephemeral=True)
#
#         options = [
#             discord.SelectOption(label=f"{s['shift_type']} ({s['day_of_week']})", value=str(s['id']))
#             for s in response.data
#         ]
#
#         select = discord.ui.Select(placeholder="Pick your shift to trade back...", options=options)
#
#         async def select_callback(select_interaction: discord.Interaction):
#             target_shift_id = int(select.values[0])
#
#             # --- DATABASE UPDATE ---
#             # 1. Give Proposer's shift to Target
#             self.supabase.table("shifts").update({"claimed_by_id": str(self.target.id)}).eq("id", self.proposer_shift_id).execute()
#             # 2. Give Target's shift to Proposer
#             self.supabase.table("shifts").update({"claimed_by_id": str(self.proposer.id)}).eq("id", target_shift_id).execute()
#
#             await select_interaction.response.send_message(
#                 f"✅ **Swap Complete!** {self.proposer.mention} and {self.target.mention} have traded shifts!"
#             )
#             self.stop()
#
#         select.callback = select_callback
#         new_view = discord.ui.View()
#         new_view.add_item(select)
#         await interaction.response.send_message("Select your shift to trade back:", view=new_view, ephemeral=True)
#
#     @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
#     async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
#         if interaction.user.id != self.target.id:
#             return await interaction.response.send_message("Only the target user can decline.", ephemeral=True)
#         await interaction.response.send_message("Swap request declined.")
#         self.stop()


class SwapView(discord.ui.View):
    def __init__(self, proposer, target, p_data, t_data, supabase):
        super().__init__(timeout=300)
        self.proposer = proposer
        self.target = target
        self.p_data = p_data  # These are the shift dictionaries
        self.t_data = t_data
        self.supabase = supabase

    @discord.ui.button(label="Accept Swap", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("Only the recipient can accept this.", ephemeral=True)

        # 1. Give Proposer's shift to Target & update ownership
        self.supabase.table("shifts").update({
            "claimed_by_id": str(self.target.id),
            "seller_id": str(self.target.id),
            "seller_name": self.target.display_name
        }).eq("id", self.p_data['id']).execute()

        # 2. Give Target's shift to Proposer & update ownership
        self.supabase.table("shifts").update({
            "claimed_by_id": str(self.proposer.id),
            "seller_id": str(self.proposer.id),
            "seller_name": self.proposer.display_name
        }).eq("id", self.t_data['id']).execute()

        await interaction.response.send_message(
            f"🤝 **Swap Finalized!**\n"
            f"{self.proposer.mention} took **{self.t_data['shift_type']} ({self.t_data['day_of_week']})**\n"
            f"{self.target.mention} took **{self.p_data['shift_type']} ({self.p_data['day_of_week']})**"
        )
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("Only the recipient can decline.", ephemeral=True)
        await interaction.response.send_message("Swap request declined.")
        self.stop()
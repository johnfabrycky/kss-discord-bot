import discord


class SwapView(discord.ui.View):
    """Interactive approval view for a proposed shift swap."""

    def __init__(self, proposer, target_id, p_data, t_data, supabase):
        """Store swap participants, shift payloads, and the database client."""
        super().__init__(timeout=300)
        self.proposer = proposer
        self.target_id = str(target_id)
        self.p_data = p_data
        self.t_data = t_data
        self.supabase = supabase

    @discord.ui.button(label="Accept Swap", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Finalize the swap when the invited user accepts it."""
        # 1. Validation check
        if str(interaction.user.id) != self.target_id:
            return await interaction.response.send_message("Only the recipient can accept this.", ephemeral=True)

        # 2. IMMEDIATELY defer to prevent 3-second timeout
        await interaction.response.defer()

        try:
            # 3. Perform Database Updates
            # Give Proposer's shift to Target
            self.supabase.table("shifts").update({
                "claimed_by_id": self.target_id,
                "seller_id": self.target_id,
                "seller_name": interaction.user.display_name
            }).eq("id", self.p_data['id']).execute()

            # Give Target's shift to Proposer
            self.supabase.table("shifts").update({
                "claimed_by_id": str(self.proposer.id),
                "seller_id": str(self.proposer.id),
                "seller_name": self.proposer.display_name
            }).eq("id", self.t_data['id']).execute()

            # 4. Use followup.send because we deferred
            await interaction.followup.send(
                f"🤝 **Swap Finalized!**\n"
                f"{self.proposer.mention} took **{self.t_data['shift_type']} ({self.t_data['day_of_week']})**\n"
                f"{interaction.user.mention} took **{self.p_data['shift_type']} ({self.p_data['day_of_week']})**"
            )

            # Disable buttons after success
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)
            self.stop()

        except Exception as e:
            print(f"❌ Swap Error: {e}")
            await interaction.followup.send("An error occurred during the swap. Please try again.", ephemeral=True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reject the swap request and disable the action buttons."""
        if str(interaction.user.id) != self.target_id:
            return await interaction.response.send_message("Only the recipient can decline.", ephemeral=True)

        await interaction.response.send_message("Swap request declined.")

        # Disable buttons on decline
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        self.stop()

import discord
from lobbybot.lobby.models import Lobby
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from lobbybot.lobby.controllers import LobbyController
import logging
logger = logging.getLogger(__name__)
import time

class ForceStartView(discord.ui.View):
    def __init__(self, timeout: int, lobby: Lobby, controller: "LobbyController"):
        super().__init__(timeout=timeout)
        self.lobby = lobby
        self.controller = controller
        self.response_sent = False
        self.message = None # holds message object to disable buttons on timeout or response

    def get_embed(self):
        embed = discord.Embed(
            title=f"Force Start Lobby {self.lobby.id}?",
            description=f"{self.lobby.owner.mention} is requesting to force start the lobby with {len(self.lobby._players)}/{self.lobby.max_players} players.",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"You have {int(self.timeout)} seconds to respond.")
        return embed

    @discord.ui.button(label="Force Start", style=discord.ButtonStyle.green)
    async def force_start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Lobby {self.lobby.id}: {interaction.user.name}({interaction.user.id}) pressed Force Start button.")
        handled = await self.controller.handle_start_lobby(interaction, self.lobby, forced=True)
        if handled:
            self.response_sent = True
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
    
    @discord.ui.button(label="Wait For More Players", style=discord.ButtonStyle.red)
    async def deny_force_start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Lobby {self.lobby.id}: {interaction.user.name}({interaction.user.id}) pressed Decline Force Start button.")
        handled = await self.controller.handle_force_start_deny(self.lobby, interaction)
        if handled:
            self.response_sent = True
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)


    async def on_timeout(self):
        if self.response_sent:
            return
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception as e:
            logger.warning(f"Failed to edit ForceStartView message on timeout: {e}")
            
        await self.controller.handle_force_start_deny(self.lobby)

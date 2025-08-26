import discord
from lobbybot.lobby.models import Player
from lobbybot.timezones import ASAP_TIME
from typing import TYPE_CHECKING, List
from lobbybot.images import get_img_store
if TYPE_CHECKING:
    from lobbybot.lobby.controllers import LobbyController

import logging

logger = logging.getLogger(__name__)

class ReadyCheckView(discord.ui.View):
    def __init__(self, timeout: int, players: List[Player], controller: "LobbyController"):
        super().__init__(timeout=timeout)
        self.players = players
        self.controller = controller
    
    @discord.ui.button(label="Ready!", style=discord.ButtonStyle.primary, row=0)
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "play")
        await self.controller.handle_ready_check(interaction, self.lobby, interaction.user, is_filler=False)

    pass

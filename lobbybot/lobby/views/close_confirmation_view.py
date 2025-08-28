import discord
from lobbybot.lobby.models import Lobby
from typing import TYPE_CHECKING, List
from lobbybot.images import get_img_store
if TYPE_CHECKING:
    from lobbybot.lobby.controllers import LobbyController

import logging

logger = logging.getLogger(__name__)

class CloseConfirmationView(discord.ui.View):
    def __init__(self, timeout: int, msg: discord.Message, user_id: int, lobby: Lobby, controller: "LobbyController"):
        super().__init__(timeout=timeout)
        self.msg = msg
        self.user_id = user_id
        self.lobby = lobby
        self.controller = controller
    
    @discord.ui.button(label="✅", style=discord.ButtonStyle.secondary, row=0)
    async def confirm_close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"confirming non-owner close for lobby {self.lobby.id}")
        await self.controller.handle_close_confirmation(self.msg, self.user_id, interaction, self.lobby, True)
    
    @discord.ui.button(label="❌", style=discord.ButtonStyle.secondary, row=0)
    async def deny_close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"denying non-owner close for lobby {self.lobby.id}")
        await self.controller.handle_close_confirmation(self.msg, self.user_id, interaction, self.lobby, False)

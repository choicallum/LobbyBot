import discord
from lobbybot.lobby.models import Lobby, Player, LobbyState
from lobbybot.timezones import ASAP_TIME
from typing import TYPE_CHECKING, List
from lobbybot.images import get_img_store
if TYPE_CHECKING:
    from lobbybot.lobby.controllers import LobbyController
from lobbybot.lobby.views.lobby_views import BaseLobbyView, alias_to_emoji

import logging

logger = logging.getLogger(__name__)

class ReadyCheckLobbyView(BaseLobbyView):
    def __init__(self, timeout: int, lobby: Lobby, controller: "LobbyController", timeout_time_utc: int):
        super().__init__(timeout, lobby, controller)
        self.timeout_time_utc = timeout_time_utc
    
    def create_lobby_embed(self):
        # Set color for ready check state
        color = discord.Color.orange()

        # get game emoji
        game_emoji = alias_to_emoji.get(self.lobby.game.lower(), "🎮")
            
        embed = discord.Embed(
            title=f"{game_emoji} {self.lobby.game} - Ready Check",
            color=color
        )

        embed.set_author(
            name=f"{self.lobby.owner.name}'s Lobby",
            icon_url=self.lobby.owner.display_avatar.url
        )

        if self.img:
            try:
                embed.set_image(url=self.img)
            except Exception as e:
                logger.warning(f"Failed to set lobby image: {e}")

        embed.description = f"⏳ Time Left: <t:{self.timeout_time_utc}:R>"

        # Players with ready status
        player_list = []
        for player in self.lobby.get_players:
            emoji = "✅" if player.is_ready() else "❌" if player.is_not_ready() else "🤔"
            note = " (force added)" if player.force_added else ""
            player_list.append(f"{emoji} <@{player.id}>{note}")
            
        players_text = "\n".join(player_list) if player_list else "None"
        embed.add_field(
            name=f"👥 Players",
            value=players_text,
            inline=True
        )
        
        # Fillers with ready status
        filler_list = []
        for filler in self.lobby.get_fillers:
            emoji = "✅" if filler.is_ready() else "❌" if filler.is_not_ready() else "🤔"
            filler_list.append(f"{emoji} <@{filler.id}>")
            
        fillers_text = "\n".join(filler_list) if filler_list else "None"
        embed.add_field(name="🧩 Fillers", value=fillers_text, inline=True)

        embed.set_footer(text=f"Lobby ID: {self.lobby.id} • Players that don't ready up may be replaced by ready fillers.")
        return embed

    @discord.ui.button(label="Ready!", style=discord.ButtonStyle.primary, row=0)
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "ready")
        await self.controller.handle_ready(interaction, self.lobby)

    @discord.ui.button(label="Not Ready!", style=discord.ButtonStyle.red, row=0)
    async def not_ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "not_ready")
        await self.controller.handle_not_ready(interaction, self.lobby)
    
    @discord.ui.button(label="Cancel Ready Check", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "cancel_ready")
        await self.controller.handle_end_ready_check(interaction, self.lobby)

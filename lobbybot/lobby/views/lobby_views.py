import discord
from lobbybot.lobby.models import Lobby, LobbyState
from lobbybot.timezones import ASAP_TIME
from typing import TYPE_CHECKING
from lobbybot.images import get_img_store
import random
if TYPE_CHECKING:
    from lobbybot.lobby.controllers import LobbyController

import logging

logger = logging.getLogger(__name__)

class BaseLobbyView(discord.ui.View):
    def __init__(self, timeout: int, lobby: Lobby, controller: "LobbyController"):
        super().__init__(timeout=timeout)
        self.lobby = lobby
        self.controller = controller
        self.img = get_img_store().get_random_img()
    
    def log_button(self, interaction: discord.Interaction, button_name: str):
        """Log button interactions for debugging"""
        logger.info(f"Lobby {self.lobby.id}: {interaction.user.name}({interaction.user.id}) pressed {button_name} button.")
    
    def create_lobby_embed(self) -> discord.Embed:
        """Creates a Discord embed for a view"""
        if self.lobby.state == LobbyState.ACTIVE:
            # scheduled_time = f"<t:{self.lobby.time}:t>" if self.lobby.time != ASAP_TIME else "ASAP"
            started_time = f"<t:{self.lobby.started_at}:t>" if self.lobby.started_at else "N/A"
            time_display = f"Started at {started_time}"
        else:
            time_display = f"ASAP (Created at <t:{self.lobby.created_at}:t>)" if self.lobby.time == ASAP_TIME \
                else f"<t:{self.lobby.time}:t> (<t:{self.lobby.time}:R>)"
                
        # Set color based on lobby state
        if self.lobby.state == LobbyState.ACTIVE:
            color = discord.Color.red()
        elif self.lobby.state == LobbyState.WAITING or self.lobby.state == LobbyState.PENDING:
            color = discord.Color.blue()
        else:
            color = discord.Color.dark_gray()

        game_aliases = {
            "<:valorant:1409833022978785351>": ["val", "valorant", "shoot", "gun"],
            "<:leagueoflegends:1409852497316806746>": ["league", "league of legends", "lol", "flex", "flex now"],
            "<:deadlock:1411925174671904899>": ["deadlock"]
        }
        # flatten aliases into a single dict mapping alias -> emoji
        alias_to_emoji = {alias.lower(): emoji for emoji, aliases in game_aliases.items() for alias in aliases}
        game_emoji = alias_to_emoji.get(self.lobby.game.lower(), "🎮")
            
        embed = discord.Embed(
            title=f"{game_emoji} {self.lobby.game}",
            color=color
        )

        embed.set_author(
            name=f"{self.lobby.owner.name}'s {'Active ' if self.lobby.state == LobbyState.ACTIVE else ''}Lobby",
            icon_url=self.lobby.owner.display_avatar.url
        )

        embed.description = f"🕒 {time_display}"   
        if self.img:
            try:
                embed.set_image(url=self.img)
            except Exception as e:
                logger.warning(f"Failed to set lobby image: {e}")

        player_list = []
        for player in self.lobby.get_players:
            note = " (force added)" if player.force_added else ""
            player_list.append(f"<@{player.id}>{note}")

        players_text = "\n".join(player_list) if player_list else "None"
        embed.add_field(
            name=f"👥 Players ({len(self.lobby.get_players)}/{self.lobby.max_players})",
            value=players_text,
            inline=True
        )

        fillers_text = "\n".join([f"<@{filler.id}>" for filler in self.lobby._fillers]) if self.lobby._fillers else "None"
        embed.add_field(name="🧩 Fillers", value=fillers_text, inline=True)

        embed.set_footer(text=f"Lobby ID: {self.lobby.id}")
        return embed

class WaitingLobbyView(BaseLobbyView):
    @discord.ui.button(label="Join as Player", style=discord.ButtonStyle.primary, row=0)
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "play")
        await self.controller.handle_join_lobby(interaction, self.lobby, interaction.user, is_filler=False)
    
    @discord.ui.button(label="Join as Filler", style=discord.ButtonStyle.secondary, row=0)
    async def fill_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "fill")
        await self.controller.handle_join_lobby(interaction, self.lobby, interaction.user, is_filler=True)

    @discord.ui.button(label="Leave Lobby", style=discord.ButtonStyle.red, row=0)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "leave_waiting")
        await self.controller.handle_leave_lobby(interaction, self.lobby, interaction.user)
    
    @discord.ui.button(label="Start Lobby", style=discord.ButtonStyle.green, row=1)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "start")
        await self.controller.handle_start_lobby(interaction, self.lobby, forced=False)
    
    @discord.ui.button(label="Close Lobby", style=discord.ButtonStyle.red, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "close_waiting")
        await self.controller.handle_close_lobby(interaction, self.lobby)

class ActiveLobbyView(BaseLobbyView):
    def __init__(self, timeout: int, lobby: Lobby, controller: "LobbyController"):
        super().__init__(timeout, lobby, controller)

    @discord.ui.button(label="Join as Player", style=discord.ButtonStyle.primary, row=0)
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "play_active")
        await self.controller.handle_join_lobby(interaction, self.lobby, interaction.user, is_filler=False)

    @discord.ui.button(label="Join as Filler", style=discord.ButtonStyle.secondary, row=0)
    async def fill_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "fill_active")
        await self.controller.handle_join_lobby(interaction, self.lobby, interaction.user, is_filler=True)

    @discord.ui.button(label="Leave Lobby", style=discord.ButtonStyle.red, row=0)
    async def dropout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "leave_active")
        await self.controller.handle_dropout_active(interaction, self.lobby, interaction.user)

    @discord.ui.button(label="Close Lobby", style=discord.ButtonStyle.red, row=1)
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.log_button(interaction, "close_active")
        await self.controller.handle_end_lobby(interaction, self.lobby)

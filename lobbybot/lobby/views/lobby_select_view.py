import discord
from lobbybot.lobby.models import Lobby
from typing import List
from lobbybot.timezones import ASAP_TIME
from datetime import datetime
import pytz

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from lobbybot.lobby.controllers import LobbyController

class LobbySelectView(discord.ui.View):
    """ Takes an on_select function, with signature async(self: LobbyController, interaction: discord.Interaction, lobby_id: int, **kwargs) """
    def __init__(self, timeout: int, timezone: str, lobbies: List[Lobby], controller: "LobbyController", on_select, **kwargs):
        super().__init__(timeout=timeout)
        self.lobbies = lobbies
        self.controller = controller
        self.extra_args = kwargs

        options = []
        for lobby in self.lobbies:
            if lobby.time != ASAP_TIME:
                utc_time = datetime.utcfromtimestamp(lobby.time)
                time_str = utc_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(timezone)).strftime("%I:%M %p")
            else:
                time_str = "ASAP"
            options.append(discord.SelectOption(label=f"ID: {lobby.id} - Owner: {lobby.owner.name} - {time_str}", value=lobby.id))
        select = discord.ui.Select(
            placeholder="Which lobby? 🤔",
            options=options
        )
        self.add_item(select)

        async def select_callback(interaction: discord.Interaction):
            lobby_id = int(select.values[0])
            await on_select(interaction, lobby_id, **self.extra_args)
        select.callback = select_callback

from .player import Player
from .lobby_enums import LobbyAddResult, LobbyRemoveResult, LobbyState
from typing import Tuple, List
import discord

class Lobby:
    def __init__(self, id: int, owner: discord.Member, time: int, max_players: int, game: str, started_at: int):
        self.id = id
        self.owner = owner
        self.time = time
        self.max_players = max_players
        self.game = game
        self.started_at = started_at

        self._state = LobbyState.WAITING
        self._players: list[Player] = [Player(owner.id)]
        self._fillers: list[Player] = list()
    
    def in_lobby(self, user_id: int) -> bool:
        """ Returns if a user_id is in the lobby at all. """
        return any(player.id == user_id for player in self._players) or any(player.id == user_id for player in self._fillers)

    def edit_time(self, new_time: int) -> None:
        """ Edits the time of the lobby. """
        self.time = new_time

    def add_player(self, player: discord.Member, forced: bool) -> LobbyAddResult:
        """ Adds a player to the player list, removing them from the fillers if they were in the filler list. """
        if self._state  == LobbyState.COMPLETED:
            return LobbyAddResult.LOBBY_COMPLETED
        
        if player.id in self._players:
            return LobbyAddResult.ALREADY_IN_LOBBY
        elif len(self._players) < self.max_players:
            if player.id in self._fillers: 
                self._fillers.remove(Player(player.id))
            self._players.append(Player(player.id, forced))
            return LobbyAddResult.SUCCESS
        else:   # otherwise, lobby is full
            return LobbyAddResult.LOBBY_FULL
        
    def add_filler(self, player: discord.Member, forced: bool) -> LobbyAddResult:
        """ Adds a player to the filler list. """
        if self._state  == LobbyState.COMPLETED:
            return LobbyAddResult.LOBBY_COMPLETED
        
        if self.in_lobby(player.id):
            return LobbyAddResult.ALREADY_IN_LOBBY
        elif len(self._players) < self.max_players:
            self._fillers.append(Player(player.id, forced))
            return LobbyAddResult.SUCCESS
    
    def remove_player(self, player: discord.Member) -> LobbyRemoveResult:
        """ Removes a player from the player or filler list."""
        if self._state  == LobbyState.COMPLETED:
            return LobbyRemoveResult.LOBBY_COMPLETED
        
        if player.id in self._players:
            self._players.remove(Player(player.id))
            return LobbyRemoveResult.SUCCESS_PLAYER
        elif player.id in self._fillers:
            self._fillers.remove(Player(player.id))
            return LobbyRemoveResult.SUCCESS_PLAYER
        else:
            return LobbyRemoveResult.NOT_IN_LOBBY
    
    def _get_final_players(self) -> List[Player]:
        # how many players are we short by?
        needed = self.max_players - len(self._players)
        
        if needed > 0:
            # get 'needed' number of fillers from self._fillers
            fillers_to_add = self._fillers[:needed]
            return self._players + fillers_to_add
        else:
            return self._players
            
    def start(self, force: bool) -> Tuple[bool, List[Player]]:
        """ Attempts to start the lobby, returns success and final player list. If force is True, will always start the lobby. """
        if self._state != LobbyState.WAITING:
            return False, []
        
        final_players = self._get_final_players()
        if len(final_players) == self.max_players or force:
            self._state = LobbyState.ACTIVE

            # move any used fillers to players
            needed = len(final_players) - len(self._players)
            if needed > 0:
                fillers_used = self._fillers[:needed]
                self._players.extend(fillers_used)
                del self._fillers[:needed]  # remove them from fillers

            return True, final_players
        return False, final_players

    def end(self) -> None:
        """ Ends the lobby. """
        self._state = LobbyState.COMPLETED
    
    def __str__(self, delimiter="\n"):
        player_list = ", ".join([f"<@{player.id}>" for player in self._players])
        filler_list = ", ".join([f"<@{filler.id}>" for filler in self._fillers])
        parts = [f"ID: {self.id}",f"Owner: <@{self.owner.id}>", f"Game: {self.game}", f"Max Players: {self.max_players}", f"Time: {self.time} (<t:{self.time}>)", f"Players: {player_list}", f"Fillers: {filler_list}"]
        return delimiter.join(parts)


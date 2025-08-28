from .player import Player
from .lobby_enums import LobbyAddResult, LobbyRemoveResult, LobbyState, TRANSITIONS
from typing import Tuple, List, TYPE_CHECKING
import discord
import time
if TYPE_CHECKING:
    from discord import VoiceState

class Lobby:
    def __init__(self, id: int, owner: discord.Member, time: int, max_players: int, game: str, created_at: int):
        self.id = id
        self.owner = owner
        self.time = time
        self.max_players = max_players
        self.game = game
        self.created_at = created_at
        self.started_at = None

        self._state = LobbyState.WAITING
        self._players: list[Player] = [Player(owner.id)]
        self._fillers: list[Player] = []

    # -----------------------------
    # State
    # -----------------------------
    @property
    def state(self) -> LobbyState:
        return self._state

    def is_active(self) -> bool:
        return self._state == LobbyState.ACTIVE

    def is_completed(self) -> bool:
        return self._state == LobbyState.COMPLETED

    def can_transition(self, new_state: LobbyState) -> bool:
        return new_state in TRANSITIONS[self._state]

    def transition(self, new_state: LobbyState) -> LobbyState:
        if not self.can_transition(new_state):
            raise ValueError(f"Invalid transition: {self._state} → {new_state}")
        self._state = new_state
        return self._state

    # -----------------------------
    # players
    # -----------------------------
    def is_full(self) -> bool:
        """ Returns if the lobby is full (i.e. has max_players in the player list). """
        return len(self._players) >= self.max_players

    def playing_in_lobby(self, user_id: int) -> bool:
        """ Returns if a user_id is in the player list of the lobby. """
        return any(player.id == user_id for player in self._players)

    def in_lobby(self, user_id: int) -> bool:
        """ Returns if a user_id is in the lobby at all. """
        return self.playing_in_lobby(user_id) or any(player.id == user_id for player in self._fillers)

    def edit_participant_voicestate(self, player_id: int, new_state: "VoiceState"):
        participant = next((p for p in self._players if p == player_id), None)
        if not participant:
            participant = next((p for p in self._filler if p == player_id), None)

        if participant:
            participant.voice_state = new_state
    
    def participant_joined_voice(self, player_id: int):
        participant = next((p for p in self._players if p == player_id), None)
        if not participant:
            participant = next((p for p in self._filler if p == player_id), None)

        if participant:
            participant.joined_voice = True

    
    def get_participants(self):
        return self._players + self._fillers

    def get_players(self):
        return self._players
        
    def edit_time(self, new_time: int) -> None:
        """ Edits the time of the lobby. """
        self.time = new_time

    def add_player(self, player: discord.Member, forced: bool) -> LobbyAddResult:
        """ Adds a player to the player list, removing them from the fillers if they were in the filler list. """
        if self._state == LobbyState.COMPLETED:
            return LobbyAddResult.LOBBY_COMPLETED

        if self.playing_in_lobby(player.id):
            return LobbyAddResult.ALREADY_IN_LOBBY
        elif len(self._players) < self.max_players:
            # if they were in fillers, remove them
            self._fillers = [f for f in self._fillers if f.id != player.id]
            self._players.append(Player(player.id, forced))
            return LobbyAddResult.SUCCESS
        else:
            return LobbyAddResult.LOBBY_FULL

    def add_filler(self, player: discord.Member, forced: bool) -> LobbyAddResult:
        """ Adds a player to the filler list. """
        if self._state == LobbyState.COMPLETED:
            return LobbyAddResult.LOBBY_COMPLETED

        if player.id in [f.id for f in self._fillers]:
            return LobbyAddResult.ALREADY_IN_LOBBY
        elif self.playing_in_lobby(player.id):
            self._players = [p for p in self._players if p.id != player.id]
            self._fillers.append(Player(player.id, forced))
            return LobbyAddResult.SUCCESS
        else:
            self._fillers.append(Player(player.id, forced))
            return LobbyAddResult.SUCCESS

    def remove_participant(self, player: discord.Member) -> LobbyRemoveResult:
        """ Removes a player from the player or filler list. If the player leaving is the last player, the lobby will close. """
        if self._state == LobbyState.COMPLETED:
            return LobbyRemoveResult.LOBBY_COMPLETED

        lobby_result = None
        if self.playing_in_lobby(player.id):
            self._players = [p for p in self._players if p.id != player.id]
            lobby_result = LobbyRemoveResult.SUCCESS_PLAYER
        elif any(f.id == player.id for f in self._fillers):
            self._fillers = [f for f in self._fillers if f.id != player.id]
            lobby_result = LobbyRemoveResult.SUCCESS_FILLER
        else:
            return LobbyRemoveResult.NOT_IN_LOBBY

        if not self._players and not self._fillers:
            lobby_result = LobbyRemoveResult.LOBBY_EMPTY

        return lobby_result

    def _get_final_players(self) -> List[Player]:
        # how many players are we short by?
        needed = self.max_players - len(self._players)
        if needed > 0:
            return self._players + self._fillers[:needed]
        return self._players

    # -----------------------------
    # Lifecycle
    # -----------------------------
    def start(self, force: bool) -> Tuple[bool, List[Player]]:
        """ Attempts to start the lobby, returns success and final player list. If force is True, will always start the lobby. """
        if self._state not in (LobbyState.WAITING, LobbyState.PENDING):
            return False, []

        final_players = self._get_final_players()

        if len(final_players) == self.max_players or force:
            self.transition(LobbyState.ACTIVE)

            # promote fillers if needed
            needed = len(final_players) - len(self._players)
            if needed > 0:
                fillers_used = self._fillers[:needed]
                self._players.extend(fillers_used)
                del self._fillers[:needed]

            self.started_at = int(time.time())
            return True, final_players

        # not enough players, and not forced
        self.transition(LobbyState.PENDING)
        return False, final_players

    def end(self) -> None:
        """Ends the lobby."""
        self.transition(LobbyState.COMPLETED)

    def reset_pending(self) -> None:
        """Return from PENDING → WAITING when force start expires or is declined."""
        if self._state == LobbyState.PENDING:
            self.transition(LobbyState.WAITING)

    def __str__(self, delimiter="\n"):
        player_list = ", ".join([f"<@{player.id}>" for player in self._players])
        filler_list = ", ".join([f"<@{filler.id}>" for filler in self._fillers])
        parts = [
            f"ID: {self.id}",
            f"Owner: <@{self.owner.id}>",
            f"Game: {self.game}",
            f"Max Players: {self.max_players}",
            f"Time: {self.time} (<t:{self.time}>)",
            f"Players: {player_list}",
            f"Fillers: {filler_list}",
            f"State: {self._state.name}"
        ]
        return delimiter.join(parts)

from .player import Player
from .lobby_enums import LobbyAddResult, LobbyRemoveResult, LobbyState, TRANSITIONS, ReadyResult
from typing import Tuple, List, TYPE_CHECKING
import discord
import time
if TYPE_CHECKING:
    from discord import VoiceState
from itertools import chain

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
        self._players: List[Player] = [Player(owner.id, voice_state=owner.voice)]
        self._fillers: List[Player] = []

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

    def is_player(self, user_id: int) -> bool:
        """ Returns if a user_id is in the player list of the lobby. """
        return any(player.id == user_id for player in self._players)
    
    def is_filler(self, user_id: int) -> bool:
        """ Returns if a user_id is in the filler list of the lobby. """
        return any(player.id == user_id for player in self._fillers)

    def in_lobby(self, user_id: int) -> bool:
        """ Returns if a user_id is in the lobby at all. """
        return self.is_player(user_id) or any(player.id == user_id for player in self._fillers)

    def ready_up(self, user: discord.Member) -> ReadyResult:
        """ Readies up user_id. If the player is not in the lobby, add them as a filler. """
        player = next((p for p in self._players if p == user.id), None)
        filler = None
        if not player:
            filler = next((p for p in self._fillers if p == user.id), None)
        
        # add a player  
        if not player and not filler:
            new_player = Player(user.id, False, user.voice)
            self._fillers.append(new_player)
            filler = new_player
        
        if (player and player.is_ready()) or (filler and filler.is_ready()):
            return ReadyResult.ALREADY_READY
    
        if player:
            player.ready_up()
            return ReadyResult.SUCCESS_PLAYER
        elif filler:
            filler.ready_up()
            return ReadyResult.SUCCESS_FILLER
        
    def unready(self, user: discord.Member) -> ReadyResult:
        """ Unreadies user_id. """
        player = next((p for p in self._players if p == user.id), None)
        filler = None
        if not player:
            filler = next((p for p in self._fillers if p == user.id), None)
        if (player and player.is_not_ready()) or (filler and filler.is_not_ready()):
            return ReadyResult.ALREADY_READY
        if player:
            player.unready()
            return ReadyResult.SUCCESS_PLAYER
        elif filler:
            filler.unready()
            return ReadyResult.SUCCESS_FILLER
        else:
            return ReadyResult.NOT_IN_LOBBY

    def all_ready(self, treat_pending_as_declined: bool = False) -> bool:
        """ get the number of fillers we are allowed to fill in based on how many players have rejected
        pending_players_are_not_ready tells the function to count pending players as not_ready or not"""
        players_ready = sum([1 for player in self._players if player.is_ready()])

        if treat_pending_as_declined:
            players_declined = sum([1 for player in self._players if player.is_not_ready() or player.is_pending_ready()])
        else:
            players_declined = sum([1 for player in self._players if player.is_not_ready()])

        if players_declined == 0:
            return players_ready == len(self._players)
        
        fillers_ready = sum([1 for filler in self._fillers if filler.is_ready()])
        # otherwise, if we have declined players, we need all other players ready and enough fillers to fill the declined players
        return players_ready == (len(self._players) - players_declined) and fillers_ready >= players_declined

    def edit_participant_voicestate(self, player_id: int, new_state: "VoiceState"):
        """ 
        Changes a participant's voicestate to new_state if they are in the lobby, and ignores it otherwise. 
        Also, if the lobby is active, this method updates their joined voice status. 
        """
        participant = next((p for p in self._players if p == player_id), None)
        if not participant:
            participant = next((p for p in self._fillers if p == player_id), None)

        if participant:
            participant.update_voice_state(new_state)
            if self.is_active():
                participant.update_joined_voice()

    def get_participants(self):
        return self._players + self._fillers

    @property
    def get_players(self):
        return self._players
    
    @property
    def get_fillers(self):
        return self._fillers
        
    def edit_time(self, new_time: int) -> None:
        """ Edits the time of the lobby. """
        self.time = new_time

    def add_player(self, player: discord.Member, forced: bool) -> LobbyAddResult:
        """Adds a player to the player list, moving them from fillers if necessary."""
        if self._state == LobbyState.COMPLETED:
            return LobbyAddResult.LOBBY_COMPLETED
    
        if self._state == LobbyState.READY_CHECK:
            return LobbyAddResult.LOBBY_IN_READY_CHECK

        if self.is_player(player.id):
            return LobbyAddResult.ALREADY_IN_LOBBY

        if len(self._players) < self.max_players:
            # look for an existing Player object in fillers
            existing_player = next((f for f in self._fillers if f.id == player.id), None)
            if existing_player:
                self._fillers.remove(existing_player)
                existing_player.force_added = forced # update forced
                existing_player.voice_state = player.voice  # keep voice state fresh
                self._players.append(existing_player)
            else:
                # create new Player if they weren’t a filler
                self._players.append(Player(player.id, forced, voice_state=player.voice))

            return LobbyAddResult.SUCCESS
        else:
            return LobbyAddResult.LOBBY_FULL

    def add_filler(self, player: discord.Member, forced: bool) -> LobbyAddResult:
        """Adds a player to the filler list, moving them from players if necessary."""
        if self._state == LobbyState.COMPLETED:
            return LobbyAddResult.LOBBY_COMPLETED
        
        if self._state == LobbyState.READY_CHECK:
            return LobbyAddResult.LOBBY_IN_READY_CHECK

        if any(f.id == player.id for f in self._fillers):
            return LobbyAddResult.ALREADY_IN_LOBBY

        if self.is_player(player.id):
            # move from players -> fillers
            existing_player = next((p for p in self._players if p.id == player.id), None)
            if existing_player:
                self._players.remove(existing_player)
                existing_player.force_added = forced
                existing_player.voice_state = player.voice # keep voice state fresh
                self._fillers.append(existing_player)
                return LobbyAddResult.SUCCESS
        else:
            # brand new filler
            self._fillers.append(Player(player.id, forced, player.voice))
            return LobbyAddResult.SUCCESS

    def remove_participant(self, player: discord.Member) -> LobbyRemoveResult:
        """ Removes a player from the player or filler list. If the player leaving is the last player, the lobby will close. """
        if self._state == LobbyState.COMPLETED:
            return LobbyRemoveResult.LOBBY_COMPLETED
        
        if self._state == LobbyState.READY_CHECK:
            return LobbyRemoveResult.LOBBY_IN_READY_CHECK

        lobby_result = None
        if self.is_player(player.id):
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
    def start_ready_check(self):
        """ Starts ready check for this lobby. """
        self._players = self._get_final_players()

        self._state = LobbyState.READY_CHECK

    def end_ready_check(self):
        """ Ends ready check for this lobby. """
        if self._state == LobbyState.READY_CHECK:
            self.transition(LobbyState.WAITING)

        # any declined players should be removed from the lobby
        self._players = [player for player in self._players if not player.is_not_ready()]

        # any declined fillers should be removed from the lobby
        self._fillers = [filler for filler in self._fillers if not filler.is_not_ready()]

        for participant in self.get_participants():
            participant.unready()
        
        if not self._players and not self._fillers:
            return LobbyRemoveResult.LOBBY_EMPTY
        return None

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

    def start_from_ready_check(self): 
        if self._state != LobbyState.READY_CHECK:
            return

        # start with ready players
        final_players = [p for p in self._players if p.is_ready()]

        # promote ready fillers if we still need players
        needed_players = self.max_players - len(final_players)
        ready_fillers = [f for f in self._fillers if f.is_ready()]
        to_promote = ready_fillers[:needed_players]
        for filler in to_promote:
            self._fillers.remove(filler)
            final_players.append(filler)

        # move unready players to fillers. Remove not_ready players from the player list altogether.
        pending_players = [p for p in self._players if p.is_pending_ready()]
        for player in pending_players:
            self._players.remove(player)
            self._fillers.append(player)

        self._players = final_players

        self.transition(LobbyState.ACTIVE)
        self.started_at = int(time.time())

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

from typing import TYPE_CHECKING, Optional
from .lobby_enums import ReadyState
if TYPE_CHECKING:
    from discord import VoiceState


class Player:
    def __init__(self, id: int, force_added: bool = False, voice_state: "VoiceState" = None):
        self.id = id
        self.force_added = force_added

        self.voice_state: Optional["VoiceState"] = voice_state
        self.joined_voice: bool = False
        self.ready = ReadyState
    
    def ready_up(self):
        self.ready = ReadyState.READY

    def reset(self):
        self.ready = ReadyState.PENDING

    def unready(self):
        self.ready = ReadyState.NOT_READY
    
    def is_ready(self) -> bool:
        return self.ready == ReadyState.READY
    
    def is_pending_ready(self) -> bool:
        return self.ready == ReadyState.PENDING

    def is_not_ready(self) -> bool:
        return self.ready == ReadyState.NOT_READY
    
    def update_voice_state(self, new_state: Optional["VoiceState"]):
        self.voice_state = new_state
    
    def update_joined_voice(self):
        """ 
        joined_voice is a parameter that describes if a player has joined voice while being in an active lobby or not.
        Once it turns true, it should never turn false again.
        """
        self.joined_voice = self.joined_voice or bool(self.voice_state and self.voice_state.channel)

    def __eq__(self, other):
        if isinstance(other, Player):
            return self.id == other.id
        return self.id == other
    
    def __hash__(self):
        return hash(self.id)

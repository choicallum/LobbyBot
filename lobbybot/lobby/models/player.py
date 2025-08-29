from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from discord import VoiceState

class Player:
    def __init__(self, id: int, force_added: bool = False, voice_state: "VoiceState" = None):
        self.id = id
        self.force_added = force_added

        self.voice_state: "VoiceState" = voice_state
        self.joined_voice: bool = False
        self.ready = False
    
    def ready_up(self):
        self.ready = True
    
    def __eq__(self, other):
        if isinstance(other, Player):
            return self.id == other.id
        return self.id == other
    
    def __hash__(self):
        return hash(self.id)

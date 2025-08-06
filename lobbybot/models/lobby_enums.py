from enum import Enum, auto

class LobbyAddResult(Enum):
    SUCCESS = auto()
    ALREADY_IN_LOBBY = auto()
    LOBBY_FULL = auto()
    LOBBY_COMPLETED = auto()

class LobbyRemoveResult(Enum):
    SUCCESS_PLAYER = auto()
    SUCCESS_FILLER = auto()
    NOT_IN_LOBBY = auto()
    LOBBY_COMPLETED = auto()

class LobbyState(Enum):
    WAITING = auto()
    ACTIVE = auto()
    COMPLETED = auto()

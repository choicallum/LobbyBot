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
    LOBBY_EMPTY = auto()

class LobbyState(Enum):
    WAITING = auto()
    PENDING = auto() # waiting for force start decision / ready check (?)
    ACTIVE = auto()
    COMPLETED = auto()

TRANSITIONS = {
    LobbyState.WAITING: {LobbyState.PENDING, LobbyState.ACTIVE, LobbyState.COMPLETED},
    LobbyState.PENDING: {LobbyState.WAITING, LobbyState.ACTIVE, LobbyState.COMPLETED},
    LobbyState.ACTIVE: {LobbyState.COMPLETED},
    LobbyState.COMPLETED: set(),  # terminal state
}

from enum import Enum, auto

class LobbyAddResult(Enum):
    SUCCESS = auto()
    ALREADY_IN_LOBBY = auto()
    LOBBY_IN_READY_CHECK = auto()
    LOBBY_FULL = auto()
    LOBBY_COMPLETED = auto()

class LobbyRemoveResult(Enum):
    SUCCESS_PLAYER = auto()
    SUCCESS_FILLER = auto()
    LOBBY_IN_READY_CHECK = auto()
    NOT_IN_LOBBY = auto()
    LOBBY_COMPLETED = auto()
    LOBBY_EMPTY = auto()

class LobbyState(Enum):
    WAITING = auto()
    PENDING = auto() # waiting for force start decision
    READY_CHECK = auto() # ready check ongoing
    ACTIVE = auto()
    COMPLETED = auto()

TRANSITIONS = {
    LobbyState.WAITING: {LobbyState.PENDING, LobbyState.READY_CHECK, LobbyState.ACTIVE, LobbyState.COMPLETED},
    LobbyState.PENDING: {LobbyState.WAITING, LobbyState.ACTIVE, LobbyState.COMPLETED},
    LobbyState.READY_CHECK: {LobbyState.WAITING, LobbyState.ACTIVE},
    LobbyState.ACTIVE: {LobbyState.COMPLETED},
    LobbyState.COMPLETED: set(),  # terminal state
}

class ReadyState(Enum):
    PENDING = auto()
    READY = auto()
    NOT_READY = auto()

class ReadyResult(Enum):
    SUCCESS_PLAYER = auto()
    SUCCESS_FILLER = auto()
    ALREADY_READY = auto()
    NOT_IN_LOBBY = auto()

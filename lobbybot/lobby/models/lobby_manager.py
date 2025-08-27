from typing import Dict, Optional, List
from .lobby import Lobby
from discord import Member
from datetime import datetime
class LobbyManager:
    def __init__(self):
        self._lobbies: Dict[int, Lobby] = {} # owner id -> lobby
        self._id_counter = 0
    
    def create_lobby(self, owner: Member, time: int, max_players: int, game: str) -> Lobby:
        """ Creates a lobby. Returns None if owner already has a lobby. """
        if owner.id in self._lobbies:
            return None
        
        lobby = Lobby(self._id_counter, owner, time, max_players, game, int(datetime.now().timestamp()))
        self._lobbies[owner.id] = lobby
        self._id_counter += 1
        return lobby
    
    def get_lobby_by_id(self, lobby_id: int) -> Optional[Lobby]:
        """ Returns a lobby based on the lobby's id. Returns None if there is no such lobby. """
        for lobby in self._lobbies.values():
            if lobby.id == lobby_id:
                return lobby
        return None
    
    def get_all_lobbies(self) -> List[Lobby]:
        """ Returns a list of all lobbies. """
        return list(lobby for lobby in self._lobbies.values() if not lobby.is_completed())

    def get_lobby_by_owner(self, owner_id: int) -> Optional[Lobby]:
        """ Returns a lobby based on the owner's id. Returns None if there is no such lobby. """
        return self._lobbies.get(owner_id)
    
    def close_lobby(self, owner_id: int) -> bool:
        """ Closes a lobby based on the owner's id. Returns True if successful, and False otherwise. """
        if owner_id in self._lobbies: 
            self._lobbies[owner_id].end()
            del self._lobbies[owner_id]
            return True
        return False
    

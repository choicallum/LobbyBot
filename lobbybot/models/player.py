class Player:
    def __init__(self, id: int, forceAdded: bool = False):
        self.id = id
        self.forceAdded = forceAdded
    
    def __eq__(self, other):
        if isinstance(other, Player):
            return self.id == other.id
        return self.id == other
    
    def __hash__(self):
        return hash(self.id)

class Player:
    def __init__(self, id: int, force_added: bool = False):
        self.id = id
        self.force_added = force_added

        self.ready = False
    
    def ready_up(self):
        self.ready = True
    
    def __eq__(self, other):
        if isinstance(other, Player):
            return self.id == other.id
        return self.id == other
    
    def __hash__(self):
        return hash(self.id)

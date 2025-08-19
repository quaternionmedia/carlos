from tinydb import TinyDB
from pathlib import Path

class DatabaseManager:
    """TinyDB database manager"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(self.db_path)
        self.animations = self.db.table('animations')
        self.items = self.db.table('items')
    
    def generate_id(self) -> str:
        """Generate unique ID"""
        from uuid import uuid4
        return str(uuid4())
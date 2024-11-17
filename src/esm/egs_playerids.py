import sqlite3
import logging
from typing import Dict

log = logging.getLogger(__name__)

class PlayerInformationProvider:
    """
        class that will read the egs database and retrieve
        a map of entity ids to player names
    """
    def __init__(self, database_path: str):
        self.database_path = database_path
        self.entityMap: Dict[int, str] = {}

    def initialize(self):
        self.entityMap = self._readEntityMap()

    def getPlayerName(self, playerId: int) -> str:
        return self.entityMap.get(playerId, None)

    def _readEntityMap(self) -> Dict[int, str]:
        """
        Retrieve all entities of type 1 (Players) from the Entities table and return them as an ID-name map.
        Args:
            database_path (str): Path to the SQLite database file
        Returns:
            Dict[int, str]: Dictionary mapping entity IDs to their names
        """
        entity_map = {}
        try:
            # Connect to the database
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            # Execute the query to get all entities of type 1
            cursor.execute("SELECT entityId, name FROM Entities WHERE etype = 1")
            results = cursor.fetchall()
            # Build the map from the results
            entity_map = {entity_id: name for entity_id, name in results}
            # Close the connection
            conn.close()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        except Exception as e:
            print(f"Error: {e}")
        return entity_map

# Example usage
if __name__ == "__main__":
    # Replace with your database path
    db_path = r"d:\Servers\Empyrion\Saves\Games\EsmDediGame\global.db"
    provider = PlayerInformationProvider(db_path)
    provider.initialize()

    entity_id = 2142
    log.info(f"entities found: {provider.entityMap}")
    log.info(f"entity {entity_id} is: {provider.getPlayerName(entity_id)}")

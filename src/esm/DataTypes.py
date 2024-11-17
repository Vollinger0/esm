from enum import Enum
from pathlib import Path
from pydantic import BaseModel

class Territory:
    """
    data type for an ingame territory info
    """
    GALAXY = 'GALAXY'
    def __init__(self, name, x, y, z, radius):
        self.name = name
        self.x = x * 100000
        self.y = y * 100000
        self.z = z * 100000
        self.radius = radius * 100000

class SolarSystem:
    """
    contains the SolarSystem info as its saved in the db
    """
    def __init__(self, ssid, name, x, y, z):
        self.ssid = ssid
        self.name = name
        self.x = x
        self.y = y
        self.z = z
    def __eq__(self, other):
        if isinstance(other, SolarSystem):
            return self.ssid == other.ssid
        return False        
    def __hash__(self):
        return hash(self.ssid)

class Playfield:
    """
    playfield info as in the db
    """
    def __init__(self, pfid, name, ssid=0, starName=""):
        self.pfid = pfid
        self.name = name
        self.ssid = ssid
        self.starName = starName
    def __eq__(self, other):
        if isinstance(other, Playfield):
            return self.pfid == other.pfid
        return False        
    def __hash__(self):
        return hash(self.pfid)
    
class WipeTypeInfo:
    name: str
    description: str
    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

class WipeType(Enum):
    """
    contains the available wipe types
    """
    ALL = WipeTypeInfo('all', "Wipes the playfield completely")
    DEPOSIT = WipeTypeInfo('deposit', "Only wipe the deposits - be aware that this may wipe placed autominers aswell depending on their placement on the deposit")
    POI = WipeTypeInfo('poi', "Only wipe POIs - be aware that stuff in their bounding box may be affected aswell.")
    PLAYER = WipeTypeInfo('player', 'Wipes all player owned structures?')
    TERRAIN = WipeTypeInfo('terrain', 'Regenerates the terrain, e.g. if there are holes in it. Probably includes a wipe of the deposits.')

    @staticmethod
    def byName(name):
        for wt in list(WipeType):
            if wt.value.name == name:
                return wt
            
    @staticmethod
    def valueList():
        return list(map(lambda x: x.value.name, list(WipeType)))

class EntityType(Enum):
    """
    contains the games entity types (e.g. to recognize entities in the Entities table in db)
    """
    PLAYER = 1
    BA = 2
    CV = 3
    SV = 4
    HV = 5
    Asteroid = 7
    EscapePod = 8
    NPC = 9
    PlayerDrone = 12
    Trader = 13
    Playerbike = 19
    UNKNOWN = 0

    @staticmethod
    def byNumber(number):
        for et in list(EntityType):
            if et.value == number:
                return et
        return EntityType.UNKNOWN
            
class Entity:
    """
    game entity
    """
    def __init__(self, id, name, pfid, type: EntityType, isremoved: bool) -> None:
        self.id = id
        self.name = name
        self.pfid = pfid
        self.type = type
        self.isremoved = isremoved
    def __eq__(self, other):
        if isinstance(other, Entity):
            return self.id == other.id
        return False        
    def __hash__(self):
        return hash(self.id)


class ZipFile:
    """
    internal entity for handling zip files in the download server
    """
    name: str = None
    path: str = None
    size: int = 0
    downloads: int = 0
    wwwrootPath: Path = None

    def __init__(self, name: str, path: str = None, size: int = 0, downloads: int = 0, wwwrootPath: Path = None):
        self.name = name
        self.path = path
        self.size = size
        self.downloads = downloads
        self.wwwrootPath = wwwrootPath

class ChatMessage(BaseModel):
    """
    data type for a chat message, pydantic model
    """
    timestamp: float
    speaker: str
    message: str

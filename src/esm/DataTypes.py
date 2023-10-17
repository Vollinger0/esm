from collections import namedtuple
from enum import Enum

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

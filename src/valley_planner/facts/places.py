"""Readable names for the game's locations ("AnimalShop" -> "Marnie's Ranch").

The game's own names come from Data/Locations DisplayName (in the player's
language when the game is). Farms use the farm's name. A few places have
none there; for those we use our own labels, and anything else is split
at its capitals ("BusStop" -> "Bus Stop").
"""

from __future__ import annotations

import re

OUR_NAMES = {
    "FarmHouse": "the farmhouse", "FarmCave": "the farm cave", "Greenhouse": "the greenhouse",
    "Cellar": "the cellar", "HarveyRoom": "Harvey's room", "SebastianRoom": "Sebastian's room",
    "LewisBasement": "Lewis's basement", "SandyHouse": "the Oasis", "Club": "the Casino",
    "SkullCave": "Skull Cavern", "UndergroundMine": "the Mines", "BugLand": "the Mutant Bug Lair",
    "WitchSwamp": "the Witch's Swamp", "WitchHut": "the Witch's Hut", "WitchWarpCave": "the Witch's cave",
    "Summit": "the Summit", "BeachNightMarket": "the Night Market", "BeachTidePools": "the beach tide pools",
    "MermaidHouse": "the Mermaid's boat", "Submarine": "the submarine", "BoatTunnel": "Willy's boat",
    "DesertFestival": "the Desert Festival", "NightMarket": "the Night Market", "MasteryCave": "the Mastery Cave",
    "QiNutRoom": "Qi's Walnut Room", "LeoTreeHouse": "Leo's treehouse", "Caldera": "the volcano caldera",
    "IslandSouth": "Ginger Island (south)", "IslandSouthEast": "Ginger Island (southeast)",
    "IslandSouthEastCave": "Ginger Island (pirate cove)", "IslandEast": "Ginger Island (jungle)",
    "IslandWest": "Ginger Island (west)", "IslandNorth": "Ginger Island (north)",
    "IslandHut": "Leo's hut", "IslandWestCave1": "Ginger Island (west cave)",
    "IslandNorthCave1": "Ginger Island (north cave)", "IslandFieldOffice": "the island field office",
    "IslandFarmHouse": "the island farmhouse", "IslandFarmCave": "the island farm cave",
    "IslandShrine": "the island shrine", "CaptainRoom": "the shipwreck", "Sunroom": "Caroline's sunroom",
    "Farm": "your farm",
}


def _split(name: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).replace("_", " ")


class Places:
    def __init__(self, data, farm_name: str = ""):
        self.data = data
        self.farm_name = farm_name

    def name(self, location: str) -> str:
        if not location:
            return ""
        if location == "Farm" or location.startswith("Farm_"):
            return f"{self.farm_name} Farm" if self.farm_name else "your farm"
        raw = (self.data.asset("Data/Locations").get(location) or {}).get("DisplayName")
        text = self.data.text(raw) if raw else None
        if text and not text.startswith("["):
            return text
        return OUR_NAMES.get(location, _split(location))

"""The To-do list: its next-morning checks and the day log."""

from types import SimpleNamespace as NS

from valley_planner.engine.todo import DayLog, Task, check, data_root


def crop(tile, ready=False, grown=1, harvest="24"):
    return NS(location="Farm", tile=tile, ready=ready, grown=grown, harvest_id=harvest, dead=False, forage=False)


def save(**kw):
    base = dict(friends={}, crops=[], animals=[], items=[], shipped={}, buildings={}, flags=set(), house_upgrade=0,
                axe_level=0)
    return NS(**{**base, **kw})


def test_checks():
    gift = {"check": {"type": "gift", "npc": "Jodi", "points": 500}}
    assert check(gift, None, save(friends={"Jodi": NS(points=580)})) is True
    assert check(gift, None, save(friends={"Jodi": NS(points=500)})) is False
    harvest = {"check": {"type": "harvest", "tiles": [["Farm", [1, 1]]]}}
    assert check(harvest, None, save(crops=[crop((1, 1), ready=True)])) is False
    assert check(harvest, None, save(crops=[])) is True
    water = {"check": {"type": "water", "tiles": [["Farm", [2, 2]]]}}
    prev = save(crops=[crop((2, 2), grown=1)])
    assert check(water, prev, save(crops=[crop((2, 2), grown=2)])) is True
    assert check(water, prev, save(crops=[crop((2, 2), grown=1)])) is False
    assert check(water, None, save(crops=[crop((2, 2), grown=2)])) is None  # no save from the day before
    pet = {"check": {"type": "pet", "animals": {"1": 500}}}
    assert check(pet, None, save(animals=[{"id": "1", "friendship": 515}])) is True
    assert check(pet, None, save(animals=[{"id": "1", "friendship": 492}])) is False
    bridge = {"check": {"type": "flag", "flag": "beachBridgeFixed"}}
    assert check(bridge, None, save(flags={"beachBridgeFixed"})) is True
    assert check({"check": {}}, None, save()) is None


def test_day_log(tmp_path):
    log = DayLog("Farm_1", tmp_path)
    log.store(60, "Fall 4", [Task("pet", "Pet them")])
    assert log.tick(60, "pet", True)["ticks"] == {"pet": True}
    log.store(60, "Fall 4", [Task("pet", "Pet them")])  # regenerating keeps the ticks
    assert log.load(60)["ticks"] == {"pet": True}
    assert log.earlier(61) == 60 and log.earlier(60) is None
    assert str(data_root({"VALLEY_PLANNER_DATA": "/x"})) == "/x"
    assert "ValleyPlanner" in str(data_root({"LOCALAPPDATA": "C:/L"}, "win32"))

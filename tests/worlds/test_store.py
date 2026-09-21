"""Tests for Phase 6 WorldStore (YAML persistence)."""

from viveka.core.ids import new_id
from viveka.worlds.models import World
from viveka.worlds.store import WorldStore


def test_world_store_save_and_load(tmp_path):
    store = WorldStore(tmp_path)
    w_id = new_id("VWORLD")
    world = World(
        id=w_id,
        property_id="VPROP-1111",
        property_stable_key="test_key_1",
        seed=42,
    )

    saved_path = store.save(world)
    assert saved_path.is_file()

    loaded = store.load(w_id)
    assert loaded is not None
    assert loaded.id == w_id
    assert loaded.property_stable_key == "test_key_1"
    assert loaded.seed == 42


def test_world_store_load_all_and_by_property(tmp_path):
    store = WorldStore(tmp_path)
    w1 = World(
        id=new_id("VWORLD"),
        property_id="VPROP-1",
        property_stable_key="key_A",
        seed=1,
    )
    w2 = World(
        id=new_id("VWORLD"),
        property_id="VPROP-1",
        property_stable_key="key_A",
        seed=2,
    )
    w3 = World(
        id=new_id("VWORLD"),
        property_id="VPROP-2",
        property_stable_key="key_B",
        seed=3,
    )

    store.save_all([w1, w2, w3])

    all_worlds = store.load_all()
    assert len(all_worlds) == 3

    key_a_worlds = store.load_by_property("key_A")
    assert len(key_a_worlds) == 2
    assert {w.id for w in key_a_worlds} == {w1.id, w2.id}


def test_world_store_clear(tmp_path):
    store = WorldStore(tmp_path)
    w = World(
        id=new_id("VWORLD"),
        property_id="VPROP-1",
        property_stable_key="key_1",
        seed=1,
    )
    store.save(w)
    assert len(store.load_all()) == 1

    cleared = store.clear()
    assert cleared == 1
    assert len(store.load_all()) == 0

import pytest

from core import mob_modes
from server import map_worlds


def test_mob_settings_api_round_trips_mode_scoped_profiles(tmp_path):
    kind = "mob|goblin sprite-pack|g1"
    settings = mob_modes.default_settings(kind)
    settings["move_speed"] = 145
    settings["patrol"] = [[0, 0], [1, 0]]

    saved = map_worlds.save_mob_settings("front_line", kind, settings, tmp_path)
    loaded = map_worlds.load_mob_settings("front_line", kind, tmp_path)

    assert loaded == saved
    assert loaded["move_speed"] == 145
    assert loaded["patrol"] == [[0, 0], [1, 0]]
    assert map_worlds.load_mob_settings("economy", kind, tmp_path) != loaded


def test_front_line_mob_settings_round_trip_unlimited_stats_and_resources(tmp_path):
    kind = "imp_vanilla"
    settings = mob_modes.default_settings(kind)
    settings["level"] = 100
    settings["stats"] = {
        "strength": 101,
        "agility": 202,
        "intuition": 303,
        "wisdom": 404,
        "intellect": 505,
        "endurance": 606,
    }
    settings["max_hp"] = 707
    settings["max_mp"] = 808

    saved = map_worlds.save_mob_settings("front_line", kind, settings, tmp_path)
    loaded = map_worlds.load_mob_settings("front_line", kind, tmp_path)

    assert loaded == saved
    assert loaded["stats"]["endurance"] == 606
    assert (loaded["max_hp"], loaded["max_mp"]) == (707, 808)


def test_front_line_palette_mob_settings_round_trip(tmp_path):
    kind = "mob|goblin sprite-pack|g1"
    settings = mob_modes.default_settings(kind)
    settings["max_hp"] = 450
    settings["max_mp"] = 125

    saved = map_worlds.save_mob_settings("front_line", kind, settings, tmp_path)
    loaded = map_worlds.load_mob_settings("front_line", kind, tmp_path)

    assert loaded == saved
    assert (loaded["max_hp"], loaded["max_mp"]) == (450, 125)


@pytest.mark.parametrize(
    ("mode", "kind"),
    [
        ("unknown", "mob|pack|g1"),
        ("front_line", ""),
        ("front_line", " mob|pack|g1"),
        ("front_line", "mob|pack|g1\n"),
        ("front_line", "x" * 161),
    ],
)
def test_mob_settings_api_rejects_invalid_profile_identifiers(tmp_path, mode, kind):
    with pytest.raises(ValueError):
        map_worlds.load_mob_settings(mode, kind, tmp_path)


def test_mob_settings_api_rejects_invalid_profile_values(tmp_path):
    settings = mob_modes.default_settings("mob|goblin sprite-pack|g1")
    settings["move_speed"] = 401

    with pytest.raises(ValueError):
        map_worlds.save_mob_settings(
            "front_line",
            "mob|goblin sprite-pack|g1",
            settings,
            tmp_path,
        )

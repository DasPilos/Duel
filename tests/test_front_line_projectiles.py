import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from front_line.server import world as W


def _service():
    svc = W.FrontLineWorldService.__new__(W.FrontLineWorldService)
    svc._rng = random.Random(1)
    svc._projectiles = []
    svc._projectile_sequence = 0
    svc._mobs = {}
    svc._players = {}
    return svc


def _hero(x=100.0, y=100.0, hp=50):
    return SimpleNamespace(character_id=1, x=x, y=y, alive=True, facing=0.0,
                           fighter=SimpleNamespace(hp=hp, max_hp=50, profession_type="archer"))


def _mob(x=160.0, y=100.0, alive=True):
    return SimpleNamespace(id="m1", x=x, y=y, alive=alive, facing=0.0, log_names={},
                           fighter=SimpleNamespace(hp=10, max_hp=10), provoker=None)


class ProjectileDeathTests(unittest.TestCase):
    def _run(self, svc, ticks, dt=0.1):
        for _ in range(ticks):
            svc._update_projectiles(dt)

    def test_arrow_flies_to_dead_target_and_deals_no_damage(self):
        svc = _service()
        hero = _hero()
        mob = _mob(x=200.0, alive=False)  # погиб до попадания
        svc._players = {1: hero}
        svc._mobs = {"m1": mob}
        svc._projectiles = [{"id": 1, "owner": hero, "target": mob, "kind": "arrow", "from": (100.0, 100.0),
                             "pos": (100.0, 100.0), "last": (200.0, 100.0), "speed": 200.0, "age": 0.0}]
        with patch.object(W.FrontLineWorldService, "_strike_mob") as strike, \
             patch.object(W.FrontLineWorldService, "_emit", lambda *a, **k: None):
            self._run(svc, 12)
        strike.assert_not_called()  # урона мёртвой цели нет
        self.assertEqual(svc._projectiles, [])  # стрела долетела до точки и пропала

    def test_orb_explodes_at_last_position_when_target_dies_in_flight(self):
        svc = _service()
        hero = _hero()
        mob = _mob(x=200.0, alive=True)
        svc._players = {1: hero}
        svc._mobs = {"m1": mob}
        svc._projectiles = [{"id": 2, "owner": hero, "target": mob, "kind": "orb", "from": (100.0, 100.0),
                             "pos": (100.0, 100.0), "last": (200.0, 100.0), "speed": 200.0, "age": 0.0}]
        mob.alive = False  # погиб в полёте
        centers = []
        with patch.object(W.FrontLineWorldService, "_explode_orb", lambda self, owner, c: centers.append((c.x, c.y))), \
             patch.object(W.FrontLineWorldService, "_emit", lambda *a, **k: None):
            self._run(svc, 12)
        self.assertEqual(len(centers), 1)
        self.assertAlmostEqual(centers[0][0], 200.0, delta=1.0)  # взрыв в последней известной точке
        self.assertEqual(svc._projectiles, [])

    def test_mob_arrow_does_not_hit_dead_hero(self):
        svc = _service()
        hero = _hero(x=120.0, hp=0)
        mob = _mob(x=100.0)
        svc._players = {1: hero}
        svc._mobs = {"m1": mob}
        shot = {"id": 3, "source": "mob", "owner": mob, "target": hero, "kind": "arrow", "pos": (100.0, 100.0),
                "speed": 200.0, "age": 0.0}
        svc._projectiles = [shot]
        with patch.object(W.FrontLineWorldService, "_apply_mob_hit") as hit, \
             patch.object(W.FrontLineWorldService, "_emit", lambda *a, **k: None):
            svc._update_projectiles(0.1)
        hit.assert_not_called()

    def test_mob_orb_explosion_skips_dead_heroes(self):
        svc = _service()
        dead = _hero(x=110.0, hp=0)
        alive = _hero(x=112.0, hp=50)
        alive.character_id = 2
        svc._players = {1: dead, 2: alive}
        mob = _mob(x=100.0)
        with patch.object(W.FrontLineWorldService, "_apply_mob_hit") as hit, \
             patch.object(W.FrontLineWorldService, "_emit", lambda *a, **k: None):
            svc._land_mob_projectile({"id": 4, "kind": "orb", "owner": mob}, 110.0, 100.0, dead)
        targets = [call.args[1] for call in hit.call_args_list]
        self.assertNotIn(dead, targets)
        self.assertIn(alive, targets)


if __name__ == "__main__":
    unittest.main()

import time
import unittest
from unittest import mock

from psycopg import errors as pg_errors

from server.city_population import CITY_DEADLOCK_RETRIES, CityPopulation
from tests.fixtures import create_test_database, drop_test_database


class CityTickDeadlockTests(unittest.TestCase):
    def setUp(self):
        self.database = create_test_database()
        user = self.database.register("city-tick", "password")
        self.character_id = self.database.create_character(user["id"], "TickTester")["id"]
        self.city = CityPopulation(self.database)
        self.city.get_state(self.character_id, time.time())
        self.light = (self.database.world_id, "light")
        self.dark = (self.database.world_id, "dark")

    def tearDown(self):
        drop_test_database(self.database)

    def test_deadlock_is_retried_and_city_is_processed(self):
        calls = []

        def flaky(city, key, now):
            calls.append(key)
            if len(calls) == 1:
                raise pg_errors.DeadlockDetected("deadlock")

        with mock.patch.object(CityPopulation, "_process_due", flaky), mock.patch("time.sleep"):
            self.city._process_city(self.light, time.time())

        self.assertEqual(calls, [self.light, self.light])

    def test_persistent_deadlock_stops_after_retry_limit(self):
        calls = []

        def always_deadlock(city, key, now):
            calls.append(key)
            raise pg_errors.DeadlockDetected("deadlock")

        with mock.patch.object(CityPopulation, "_process_due", always_deadlock), mock.patch("time.sleep"), \
                mock.patch("traceback.print_exc") as printed:
            self.city._process_city(self.light, time.time())

        self.assertEqual(len(calls), CITY_DEADLOCK_RETRIES)
        printed.assert_called_once()

    def test_error_in_one_city_does_not_skip_the_next(self):
        seen = []

        def fails_first(city, key, now):
            seen.append(key)
            if key == self.light:
                raise RuntimeError("boom")

        with mock.patch.object(CityPopulation, "_process_due", fails_first), \
                mock.patch("traceback.print_exc"):
            self.city._process_city(self.light, time.time())
            self.city._process_city(self.dark, time.time())

        self.assertEqual(seen, [self.light, self.dark])


if __name__ == "__main__":
    unittest.main()

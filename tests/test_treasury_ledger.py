import unittest

from server.treasury_ledger import distribute_income


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConnection:
    """Serves contributor rows for SELECT and records the UPDATE share amounts."""

    def __init__(self, contributions):
        self.contributions = dict(contributions)
        self.updates = []

    def execute(self, sql, params=()):
        if sql.lstrip().startswith("SELECT"):
            rows = [{"character_id": cid, "contributed_copper": amount}
                    for cid, amount in sorted(self.contributions.items()) if amount > 0]
            return _Result(rows)
        character_id = params[-1]
        self.updates.append((character_id, params[0]))
        self.contributions[character_id] += params[0]
        return _Result([])


class DistributeIncomeTests(unittest.TestCase):
    key = (1, "light")

    def test_income_splits_pro_rata_and_sums_to_amount(self):
        connection = _FakeConnection({1: 300, 2: 100})
        assigned = distribute_income(connection, self.key, 100)
        self.assertEqual(assigned, 100)
        self.assertEqual(connection.contributions, {1: 375, 2: 125})

    def test_leftover_copper_goes_to_largest_remainder_then_lowest_id(self):
        # 10 split 1:1:1 gives 3 each with one left over; the tie goes to the lowest id.
        connection = _FakeConnection({1: 1, 2: 1, 3: 1})
        distribute_income(connection, self.key, 10)
        self.assertEqual(connection.contributions, {1: 5, 2: 4, 3: 4})
        self.assertEqual(sum(connection.contributions.values()) - 3, 10)

    def test_no_contributors_assigns_nothing(self):
        connection = _FakeConnection({})
        self.assertEqual(distribute_income(connection, self.key, 50), 0)
        self.assertEqual(connection.updates, [])

    def test_non_positive_amount_assigns_nothing(self):
        connection = _FakeConnection({1: 100})
        self.assertEqual(distribute_income(connection, self.key, 0), 0)
        self.assertEqual(connection.updates, [])


if __name__ == "__main__":
    unittest.main()

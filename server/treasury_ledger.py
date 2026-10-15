"""Per-player contributions to the city treasury.

The treasury total lives in city_population_state.treasury_copper. This module tracks
how much of that total each player contributed. Unassigned money is treasury minus the sum
of contributions. Callers update treasury_copper themselves; these helpers update only the
contribution rows and the mayor.

The mayor is the character with the largest contribution. Ties keep the current mayor.
The mayor may spend the whole treasury; everyone else spends only their own contribution.
"""

GLORY_POINTS_PER_COPPER = 1


def _split_by_contribution(rows, amount_copper):
    """Split amount_copper across rows pro-rata by contributed_copper.

    Shares are floored, and the leftover copper goes to the largest fractional remainders.
    Ties break by character_id so the result is deterministic. A share never exceeds its
    contribution when amount_copper <= the total, because a share can only be bumped above
    its floor when the amount is below the total of contributions.
    """
    total = sum(int(row["contributed_copper"]) for row in rows)
    if amount_copper <= 0 or total <= 0:
        return {}
    shares = []
    for row in rows:
        numerator = amount_copper * int(row["contributed_copper"])
        shares.append([int(row["character_id"]), numerator // total, numerator % total])
    leftover = amount_copper - sum(share for _, share, _ in shares)
    order = sorted(range(len(shares)), key=lambda index: (-shares[index][2], shares[index][0]))
    for index in order[:leftover]:
        shares[index][1] += 1
    return {character_id: share for character_id, share, _ in shares}


def _ranked_contributors(connection, key):
    return connection.execute(
        """SELECT character_id, contributed_copper FROM city_treasury_contributions
           WHERE world_id = %s AND faction = %s AND contributed_copper > 0
           ORDER BY contributed_copper DESC, character_id ASC""",
        (int(key[0]), key[1]),
    ).fetchall()


def mayor_of(connection, key):
    row = connection.execute(
        """SELECT mayor_character_id FROM city_population_state
           WHERE world_id = %s AND faction = %s""",
        (int(key[0]), key[1]),
    ).fetchone()
    if row is None or row["mayor_character_id"] is None:
        return None
    return int(row["mayor_character_id"])


def refresh_mayor(connection, key):
    """Recompute the mayor after contributions change. Returns the current mayor id."""
    rows = _ranked_contributors(connection, key)
    current = mayor_of(connection, key)
    if not rows:
        new_mayor = None
    else:
        top_amount = int(rows[0]["contributed_copper"])
        current_amount = next(
            (int(row["contributed_copper"]) for row in rows if int(row["character_id"]) == current),
            0,
        )
        if current is not None and current_amount == top_amount:
            new_mayor = current
        else:
            new_mayor = int(rows[0]["character_id"])
    if new_mayor != current:
        connection.execute(
            """UPDATE city_population_state SET mayor_character_id = %s
               WHERE world_id = %s AND faction = %s""",
            (new_mayor, int(key[0]), key[1]),
        )
    return new_mayor


def is_mayor(connection, key, character_id):
    mayor = mayor_of(connection, key)
    return mayor is not None and mayor == int(character_id)


def spendable_copper(connection, key, character_id):
    """Copper this character may spend: the whole treasury for the mayor, otherwise their contribution."""
    if is_mayor(connection, key, character_id):
        row = connection.execute(
            """SELECT treasury_copper FROM city_population_state
               WHERE world_id = %s AND faction = %s""",
            (int(key[0]), key[1]),
        ).fetchone()
        return 0 if row is None else int(row["treasury_copper"])
    return contribution_of(connection, key, character_id)


def spend_from_pool(connection, key, amount_copper):
    """Draw a mayor's expense pro-rata from all contributions.

    Returns {character_id: copper_spent} for contributors whose share was spent, so the caller
    can award glory. Any part beyond the total of contributions is unassigned money: it has no
    contributor and needs no row update. The caller awards that part to the faction and reduces
    treasury_copper.
    """
    amount_copper = int(amount_copper)
    if amount_copper <= 0:
        return {}
    rows = connection.execute(
        """SELECT character_id, contributed_copper FROM city_treasury_contributions
           WHERE world_id = %s AND faction = %s AND contributed_copper > 0
           ORDER BY character_id ASC FOR UPDATE""",
        (int(key[0]), key[1]),
    ).fetchall()
    total = sum(int(row["contributed_copper"]) for row in rows)
    shares = _split_by_contribution(rows, min(amount_copper, total))
    spent = {}
    for character_id, share in shares.items():
        if share <= 0:
            continue
        connection.execute(
            """UPDATE city_treasury_contributions
               SET contributed_copper = contributed_copper - %s
               WHERE world_id = %s AND faction = %s AND character_id = %s""",
            (share, int(key[0]), key[1], character_id),
        )
        spent[character_id] = share
    return spent


def award_glory(connection, key, character_id, amount_copper):
    """Credit glory for copper the character spent from their contribution."""
    points = int(amount_copper) * GLORY_POINTS_PER_COPPER
    if points <= 0:
        return
    connection.execute(
        """INSERT INTO character_glory (world_id, character_id, points)
           VALUES (%s, %s, %s)
           ON CONFLICT (world_id, character_id)
           DO UPDATE SET points = character_glory.points + EXCLUDED.points""",
        (int(key[0]), int(character_id), points),
    )


def award_faction_glory(connection, key, amount_copper):
    """Credit the faction's shared glory for unassigned treasury money that was spent."""
    points = int(amount_copper) * GLORY_POINTS_PER_COPPER
    if points <= 0:
        return
    connection.execute(
        """INSERT INTO faction_glory (world_id, faction, points)
           VALUES (%s, %s, %s)
           ON CONFLICT (world_id, faction)
           DO UPDATE SET points = faction_glory.points + EXCLUDED.points""",
        (int(key[0]), key[1], points),
    )


def contribution_of(connection, key, character_id):
    row = connection.execute(
        """SELECT contributed_copper FROM city_treasury_contributions
           WHERE world_id = %s AND faction = %s AND character_id = %s""",
        (int(key[0]), key[1], int(character_id)),
    ).fetchone()
    return 0 if row is None else int(row["contributed_copper"])


def add_contribution(connection, key, character_id, amount_copper):
    amount_copper = int(amount_copper)
    if amount_copper <= 0:
        return
    connection.execute(
        """INSERT INTO city_treasury_contributions
               (world_id, faction, character_id, contributed_copper)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (world_id, faction, character_id)
           DO UPDATE SET contributed_copper = city_treasury_contributions.contributed_copper + EXCLUDED.contributed_copper""",
        (int(key[0]), key[1], int(character_id), amount_copper),
    )


def remove_contribution(connection, key, character_id, amount_copper):
    """Reduce the player's contribution. The caller must check it covers the amount first."""
    amount_copper = int(amount_copper)
    if amount_copper <= 0:
        return
    connection.execute(
        """UPDATE city_treasury_contributions
           SET contributed_copper = contributed_copper - %s
           WHERE world_id = %s AND faction = %s AND character_id = %s""",
        (amount_copper, int(key[0]), key[1], int(character_id)),
    )


def distribute_income(connection, key, amount_copper):
    """Split income pro-rata across contributors and return the amount assigned.

    Shares are floored, and the leftover copper goes to the largest fractional remainders.
    Ties break by character_id so the result is deterministic. If nobody has contributed,
    nothing is assigned and the income stays unassigned in the treasury.
    """
    amount_copper = int(amount_copper)
    if amount_copper <= 0:
        return 0
    rows = connection.execute(
        """SELECT character_id, contributed_copper FROM city_treasury_contributions
           WHERE world_id = %s AND faction = %s AND contributed_copper > 0
           ORDER BY character_id FOR UPDATE""",
        (int(key[0]), key[1]),
    ).fetchall()
    total = sum(int(row["contributed_copper"]) for row in rows)
    if total <= 0:
        return 0
    shares = _split_by_contribution(rows, amount_copper)
    for character_id, share in shares.items():
        if share:
            connection.execute(
                """UPDATE city_treasury_contributions
                   SET contributed_copper = contributed_copper + %s
                   WHERE world_id = %s AND faction = %s AND character_id = %s""",
                (share, int(key[0]), key[1], character_id),
            )
    return amount_copper

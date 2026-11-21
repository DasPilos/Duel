import random


MAX_GROUP_BATTLE_PARTICIPANTS = 10
MIN_GROUP_BATTLE_PARTICIPANTS = 6
VALID_GROUP_BATTLE_SIZES = (6, 8, 10)
GROUP_BATTLE_TTL_SECONDS = 120


def fighter_potential(fighter):
    """Estimate combat potential without depending on UI or damage formulas."""
    stats = fighter.get("stats", {})
    return int(fighter.get("level", 1)) * 10 + sum(int(value) for value in stats.values())


def split_balanced_teams(participants, seed=None):
    """Split a valid group into two equal, near-balanced teams."""
    if len(participants) not in VALID_GROUP_BATTLE_SIZES:
        raise ValueError("Для группового боя нужно 6, 8 или 10 участников")

    randomizer = random.Random(seed)
    shuffled = list(participants)
    randomizer.shuffle(shuffled)
    shuffled.sort(key=fighter_potential, reverse=True)
    teams = [[], []]
    strengths = [0, 0]
    for participant in shuffled:
        if strengths[0] < strengths[1]:
            team_index = 0
        elif strengths[1] < strengths[0]:
            team_index = 1
        else:
            team_index = randomizer.randrange(2)
        teams[team_index].append(participant)
        strengths[team_index] += fighter_potential(participant)

    if not teams[0] or not teams[1]:
        raise ValueError("Невозможно сформировать две команды")
    return teams


def prepare_group_participants(participants):
    """Keep the largest valid even roster and drop latest overflow players."""
    if len(participants) < MIN_GROUP_BATTLE_PARTICIPANTS:
        raise ValueError("Для группового боя нужно минимум 6 участников")
    roster_size = min(MAX_GROUP_BATTLE_PARTICIPANTS, len(participants))
    if roster_size % 2:
        roster_size -= 1
    if roster_size not in VALID_GROUP_BATTLE_SIZES:
        raise ValueError("Для группового боя нужно 6, 8 или 10 участников")
    return list(participants[:roster_size])


def visible_group_targets(actor_id, teams, exchanges):
    """Return all living enemies and whether this actor may start an exchange."""
    actor_team = next(
        (team_index for team_index, team in enumerate(teams) if any(item["id"] == actor_id for item in team)),
        None,
    )
    if actor_team is None:
        raise ValueError("Боец не найден в командах")
    enemy_team = teams[1 - actor_team]
    result = []
    for enemy in enemy_team:
        if enemy.get("hp", 0) <= 0:
            continue
        already_attacking = any(
            exchange["attacker_id"] == actor_id and exchange["defender_id"] == enemy["id"]
            for exchange in exchanges
            if exchange.get("status") == "waiting_response"
        )
        result.append({**enemy, "target_available": not already_attacking})
    return result


def is_afk_draw(teams, afk_ids):
    """A draw occurs when both teams still have a living AFK fighter."""
    return all(
        any(item.get("hp", 0) > 0 and item["id"] in afk_ids for item in team)
        for team in teams
    )

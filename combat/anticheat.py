from collections import Counter


PAIR_REPEAT_WEIGHTS = ((12, 4), (6, 2))
SUSPICION_SOFT_CAP = 5
SUSPICION_REVIEW = 10


def normalized_pair(player_a, player_b):
    return tuple(sorted((str(player_a), str(player_b))))


def score_match(
    *,
    pair_matches_24h=0,
    pair_wins_24h=0,
    turns=0,
    median_turns=0,
    surrender=False,
    afk_turns=0,
    level_difference=0,
    same_device=False,
    new_account_farming=False,
    client_xp_submitted=False,
):
    signals = []
    suspicion = 0

    for threshold, weight in PAIR_REPEAT_WEIGHTS:
        if pair_matches_24h >= threshold:
            signals.append("pair_repeat")
            suspicion += weight
            break
    if pair_matches_24h >= 8 and pair_wins_24h / pair_matches_24h > 0.85:
        signals.append("pair_win_rate")
        suspicion += 3
    if median_turns and turns < median_turns * 0.5:
        signals.append("short_match")
        suspicion += 2
    if surrender:
        signals.append("surrender")
        suspicion += 2
    if afk_turns:
        signals.append("afk_turns")
        suspicion += 2
    if -2 <= level_difference <= 2 and pair_matches_24h >= 6:
        signals.append("repeat_tier_farm")
        suspicion += 1
    if same_device:
        signals.append("same_device")
        suspicion += 3
    if new_account_farming:
        signals.append("new_account_farm")
        suspicion += 3
    if client_xp_submitted:
        signals.append("client_xp_submitted")
        return {
            "signals": signals,
            "suspicion": suspicion,
            "action": "xp_denied",
        }

    action = "ok"
    if suspicion >= SUSPICION_REVIEW:
        action = "queued_review"
    elif suspicion >= SUSPICION_SOFT_CAP:
        action = "xp_capped"
    return {"signals": signals, "suspicion": suspicion, "action": action}


def aggregate_signals(events):
    """Return signal counts for moderation/reporting dashboards."""
    return Counter(signal for event in events for signal in event.get("signals", []))

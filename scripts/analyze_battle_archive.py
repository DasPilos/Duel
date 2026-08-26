"""Print aggregate stats over real battles saved in battle_archive/.

Usage: python -m scripts.analyze_battle_archive
"""
from collections import defaultdict

from combat.battle_archive import load_battles


def _side_summary(name, stats, wins, losses, draws):
    total = wins + losses + draws
    win_rate = 0 if total == 0 else round(100 * wins / total, 1)
    return (
        f"{name}: {total} боёв, win rate {win_rate}%, "
        f"попаданий {stats['hits']}, урон {stats['damage']}, "
        f"критов {stats['critical']}, уворотов {stats['dodges']}, "
        f"блоков {stats['blocks']}, макс. серия {stats['max_combo']}"
    )


def main():
    records = load_battles()
    if not records:
        print("battle_archive/ пуст: пока нет ни одного сохранённого боя.")
        return

    totals = defaultdict(lambda: {
        "hits": 0, "damage": 0, "critical": 0,
        "dodges": 0, "blocks": 0, "max_combo": 0,
        "wins": 0, "losses": 0, "draws": 0,
    })
    turns_sum = 0

    for record in records:
        turns_sum += record.get("turns", 0)
        winner = record.get("winner")
        for side_key, fighter_key in (("player", "player"), ("enemy", "enemy")):
            fighter = record.get(fighter_key, {})
            name = fighter.get("name", side_key)
            stats = record.get("stats", {}).get(side_key, {})
            bucket = totals[name]
            bucket["hits"] += stats.get("hits", 0)
            bucket["damage"] += stats.get("damage", 0)
            bucket["critical"] += stats.get("critical", 0)
            bucket["dodges"] += stats.get("dodges", 0)
            bucket["blocks"] += stats.get("blocks", 0)
            bucket["max_combo"] = max(bucket["max_combo"], stats.get("max_combo", 0))
            if winner == name:
                bucket["wins"] += 1
            elif winner == "Ничья":
                bucket["draws"] += 1
            else:
                bucket["losses"] += 1

    print(f"Всего боёв: {len(records)}, среднее число ходов: {round(turns_sum / len(records), 1)}\n")
    for name, stats in sorted(totals.items()):
        print(_side_summary(name, stats, stats["wins"], stats["losses"], stats["draws"]))


if __name__ == "__main__":
    main()

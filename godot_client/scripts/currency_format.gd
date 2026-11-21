extends RefCounted

# Деньги как в core/currency.py: 100 меди = 1 серебро, 100 серебра = 1 золото.

const COPPER_PER_SILVER := 100
const SILVER_PER_GOLD := 100
const COPPER_PER_GOLD := COPPER_PER_SILVER * SILVER_PER_GOLD


static func total_copper(character: Dictionary) -> int:
	return int(character.get("copper", 0)) + int(character.get("silver", 0)) * COPPER_PER_SILVER + int(character.get("gold", 0)) * COPPER_PER_GOLD


static func has_enough_copper(character: Dictionary, amount: int) -> bool:
	return amount >= 0 and total_copper(character) >= amount


# Как Currency.format_amount: «1 золото 2 серебра 3 меди»; ноль выводится как «0 меди».
static func format_amount(total: int) -> String:
	var value := maxi(0, total)
	var gold := floori(value / float(COPPER_PER_GOLD))
	var remainder := value % COPPER_PER_GOLD
	var silver := floori(remainder / float(COPPER_PER_SILVER))
	var copper := remainder % COPPER_PER_SILVER
	var parts := PackedStringArray()
	if gold > 0:
		parts.append("%d %s" % [gold, "золото" if gold == 1 else "золота"])
	if silver > 0:
		parts.append("%d %s" % [silver, "серебро" if silver == 1 else "серебра"])
	if copper > 0 or parts.is_empty():
		parts.append("%d %s" % [copper, "медь" if copper == 1 else "меди"])
	return " ".join(parts)

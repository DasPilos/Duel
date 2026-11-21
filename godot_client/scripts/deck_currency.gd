extends RefCounted

# Монеты Deck: склонение и вывод суммы как в deck/currency.py («1 монета», «2 монеты», «5 монет»).


static func coins_word(amount: int) -> String:
	var value := absi(amount)
	if 11 <= value % 100 and value % 100 <= 14:
		return "монет"
	var last := value % 10
	if last == 1:
		return "монета"
	if 2 <= last and last <= 4:
		return "монеты"
	return "монет"


static func format_coins(amount: int) -> String:
	return "%d %s" % [amount, coins_word(amount)]

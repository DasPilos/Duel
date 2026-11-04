"""Единая валюта Колоды — монеты: склонение и списание."""


def coins_word(amount):
    """Слово «монета» в нужной форме для числа amount."""
    value = abs(int(amount))
    if 11 <= value % 100 <= 14:
        return "монет"
    last = value % 10
    if last == 1:
        return "монета"
    if 2 <= last <= 4:
        return "монеты"
    return "монет"


def format_coins(amount):
    """Сумма в монетах: «250 монет», «1 монета», «2 монеты»."""
    amount = int(amount)
    return f"{amount} {coins_word(amount)}"


def spend_coins(balance, price):
    """Баланс после оплаты цены; при нехватке денег — ValueError."""
    balance = int(balance)
    price = int(price)
    if price < 0 or balance < price:
        raise ValueError("Недостаточно денег")
    return balance - price

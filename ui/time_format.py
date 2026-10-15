"""Formatting helpers shared by UI windows."""


def format_hms(seconds):
    """Форматирует секунды как ЧЧ:ММ:СС, отрицательные значения считаются нулём."""
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

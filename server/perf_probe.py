"""Замеры для поиска тормозов мира: печатает строку в stderr, если участок кода занял дольше порога.

Порог задаётся переменной PERF_PROBE_MS (по умолчанию 10 мс). Строки попадают в лог мира (logs/world_<id>.log).
"""

import functools
import gc
import os
import sys
import time

THRESHOLD_MS = float(os.environ.get("PERF_PROBE_MS", "10"))


def timed(label):
    """Декоратор метода: печатает время вызова, если оно больше порога."""

    def decorate(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            started = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                if elapsed_ms > THRESHOLD_MS:
                    stamp = time.strftime("%H:%M:%S")
                    print(f"[perf {stamp}] {label}: {elapsed_ms:.1f} мс", file=sys.stderr, flush=True)

        return wrapper

    return decorate


_gc_started = [0.0]


def _gc_callback(phase, info):
    """Пауза сборки мусора Python: без неё тик может стоять, а в замерах участков её не видно."""
    if phase == "start":
        _gc_started[0] = time.perf_counter()
    elif phase == "stop":
        elapsed_ms = (time.perf_counter() - _gc_started[0]) * 1000.0
        if elapsed_ms > THRESHOLD_MS:
            stamp = time.strftime("%H:%M:%S")
            print(f"[perf {stamp}] сборка мусора (поколение {info.get('generation')}): {elapsed_ms:.1f} мс",
                  file=sys.stderr, flush=True)


if _gc_callback not in gc.callbacks:
    gc.callbacks.append(_gc_callback)

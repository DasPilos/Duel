"""Read-only terminal dashboard for the game server host."""

import argparse
import datetime as dt
import json
import os
import select
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from zoneinfo import ZoneInfo

from server import config


CPU_STAT_PATH = Path("/proc/stat")
MEMINFO_PATH = Path("/proc/meminfo")
NET_DEV_PATH = Path("/proc/net/dev")
UPTIME_PATH = Path("/proc/uptime")
SAMPLE_SECONDS = 2.0
HISTORY_SIZE = 60


def parse_cpu_counters(text):
    row = next((line.split() for line in text.splitlines() if line.startswith("cpu ")), None)
    if row is None:
        raise ValueError("/proc/stat has no aggregate CPU row")
    values = [int(value) for value in row[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def cpu_percent(previous, current):
    if previous is None:
        return 0.0
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))


def parse_memory(text):
    values = {}
    for line in text.splitlines():
        key, _, remainder = line.partition(":")
        if key in {"MemTotal", "MemAvailable"}:
            values[key] = int(remainder.split()[0]) * 1024
    total = values["MemTotal"]
    available = values["MemAvailable"]
    used = max(0, total - available)
    return {"total": total, "used": used, "available": available,
            "percent": 100.0 * used / total if total else 0.0}


def parse_network(text):
    received = sent = 0
    for line in text.splitlines()[2:]:
        if ":" not in line:
            continue
        interface, values = line.split(":", 1)
        if interface.strip() == "lo":
            continue
        counters = values.split()
        if len(counters) >= 9:
            received += int(counters[0])
            sent += int(counters[8])
    return received, sent


def read_text(path):
    return Path(path).read_text(encoding="ascii", errors="replace")


def run_command(arguments, timeout=3):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True,
                                errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, str(error)
    if result.returncode:
        return None, (result.stderr or result.stdout).strip()
    return result.stdout.strip(), None


def service_state(unit):
    output, error = run_command(["systemctl", "is-active", unit])
    return output if error is None else "unknown"


def game_online_count(now=None):
    now = time.time() if now is None else float(now)
    try:
        import psycopg

        with psycopg.connect(config.DATABASE_URL, connect_timeout=2) as connection:
            row = connection.execute(
                """SELECT COUNT(DISTINCT user_id) AS amount FROM sessions
                   WHERE user_id <> 0 AND last_seen_at > %s""",
                (now - config.ONLINE_PLAYER_TTL_SECONDS,),
            ).fetchone()
        return int(row[0]), None
    except Exception as error:
        return None, str(error)


def api_health():
    request = urllib.request.Request(
        f"http://127.0.0.1:{config.PORT}/health", method="GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("status") == "ok", None
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        return False, str(error)


def recent_errors():
    output, error = run_command([
        "journalctl", "-u", "game-server.service", "-u", "postgresql.service", "-p", "err",
        "--since", "1 hour ago", "-n", "8", "--no-pager", "-o", "cat",
    ])
    if error:
        return [f"journalctl: {error}"]
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-6:]


def format_bytes(value):
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024


def format_duration(seconds):
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{days}d {hours:02d}:{minutes:02d}"


def graph(values, width=40):
    if not values:
        return "-" * width
    selected = list(values)[-width:]
    bars = " .:-=+*#%@"
    return "".join(bars[min(len(bars) - 1, int(value / 100 * (len(bars) - 1)))]
                   for value in selected).rjust(width)


class ServerMonitor:
    def __init__(self):
        self.previous_cpu = None
        self.previous_network = None
        self.previous_at = None
        self.cpu_history = deque(maxlen=HISTORY_SIZE)
        self.memory_history = deque(maxlen=HISTORY_SIZE)
        self.stop_requested = False

    def stop(self, _signum=None, _frame=None):
        self.stop_requested = True

    def sample(self):
        now = time.monotonic()
        current_cpu = parse_cpu_counters(read_text(CPU_STAT_PATH))
        cpu = cpu_percent(self.previous_cpu, current_cpu)
        self.previous_cpu = current_cpu

        memory = parse_memory(read_text(MEMINFO_PATH))
        self.cpu_history.append(cpu)
        self.memory_history.append(memory["percent"])

        network = parse_network(read_text(NET_DEV_PATH))
        elapsed = now - self.previous_at if self.previous_at is not None else 0
        rates = (0.0, 0.0)
        if self.previous_network is not None and elapsed > 0:
            rates = tuple(max(0, current - previous) / elapsed
                          for current, previous in zip(network, self.previous_network))
        self.previous_network = network
        self.previous_at = now

        uptime = float(read_text(UPTIME_PATH).split()[0])
        disk = shutil.disk_usage("/")
        stamp = dt.datetime.now(ZoneInfo(config.SERVER_TIMEZONE))
        game_status = service_state("game-server.service")
        database_status = service_state("postgresql")
        healthy, api_error = api_health()
        online, database_error = game_online_count()
        errors = recent_errors()
        ntp_status, _ = run_command(["timedatectl", "show", "-p", "NTPSynchronized", "--value"])
        started, _ = run_command([
            "systemctl", "show", "game-server.service", "--property=ActiveEnterTimestamp",
        ])
        if started:
            started = started.partition("=")[2] or "unknown"

        return {
            "host": socket.gethostname(), "time": stamp,
            "uptime": uptime, "cpu": cpu, "memory": memory,
            "disk": disk, "network_rates": rates,
            "game_status": game_status, "database_status": database_status,
            "api_healthy": healthy, "api_error": api_error,
            "online": online, "database_error": database_error,
            "ntp_status": ntp_status or "unknown",
            "service_started": started, "errors": errors,
            "load_average": os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0),
        }

    @staticmethod
    def _bar(value, width=24):
        filled = round(width * max(0, min(100, value)) / 100)
        return "[" + "#" * filled + "-" * (width - filled) + f"] {value:5.1f}%"

    def render(self, data, width=None):
        width = max(72, min(140, width or shutil.get_terminal_size((100, 30)).columns))
        separator = "=" * width
        mem = data["memory"]
        disk = data["disk"]
        rx, tx = data["network_rates"]
        online = "unknown" if data["online"] is None else str(data["online"])
        api_status = "OK" if data["api_healthy"] else "DOWN"
        title = f"DUEL SERVER MONITOR  {data['host']}  {data['time']:%Y-%m-%d %H:%M:%S %Z}"
        lines = [
            title[:width], separator,
            f"GAME       {data['game_status'].upper():<10}   API {api_status:<8}   ONLINE {online}",
            f"POSTGRES   {data['database_status'].upper():<10}   WORLD {config.WORLD_ID}       NTP {data['ntp_status']}",
            f"HOST UPTIME {format_duration(data['uptime'])}",
            f"SERVICE STARTED: {data['service_started']}",
            "", "HOST RESOURCES",
            f"CPU        {self._bar(data['cpu'])}     LOAD {data['load_average'][0]:.2f} / {data['load_average'][1]:.2f} / {data['load_average'][2]:.2f}",
            f"MEMORY     {self._bar(mem['percent'])}     {format_bytes(mem['used'])} / {format_bytes(mem['total'])} used",
            f"DISK /     {self._bar(100 * disk.used / disk.total if disk.total else 0)}     {format_bytes(disk.free)} free / {format_bytes(disk.total)}",
            f"NETWORK    RX {format_bytes(rx)}/s     TX {format_bytes(tx)}/s",
            "", "LOAD HISTORY (old -> new)",
            f"CPU    {graph(self.cpu_history, min(60, width - 8))}",
            f"MEM    {graph(self.memory_history, min(60, width - 8))}",
            "", "RECENT GAME / POSTGRES ERRORS (last hour)",
        ]
        if data["errors"]:
            for line in data["errors"][-6:]:
                lines.append(line.replace("\x1b", "?")[:width])
        else:
            lines.append("No error-level game-server journal entries")
        if data["api_error"]:
            lines.append(f"API: {data['api_error']}"[:width])
        if data["database_error"]:
            lines.append(f"DATABASE: {data['database_error']}"[:width])
        lines.extend([separator, "Refresh: 2s   Q: quit dashboard (service restarts it)"])
        return "\n".join(lines)

    def run(self, interval=SAMPLE_SECONDS):
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        try:
            while not self.stop_requested:
                data = self.sample()
                sys.stdout.write("\x1b[2J\x1b[H" + self.render(data))
                sys.stdout.flush()
                readable, _, _ = select.select([sys.stdin], [], [], interval)
                if readable and sys.stdin.read(1).lower() == "q":
                    self.stop_requested = True
        finally:
            sys.stdout.write("\x1b[0m\n")
            sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    args = parser.parse_args()
    monitor = ServerMonitor()
    if args.once:
        print(monitor.render(monitor.sample()))
    else:
        monitor.run()


if __name__ == "__main__":
    main()

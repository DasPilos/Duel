import datetime as dt
import shutil
import unittest
from zoneinfo import ZoneInfo

from ops.monitor import (
    ServerMonitor,
    cpu_percent,
    format_bytes,
    format_duration,
    graph,
    parse_cpu_counters,
    parse_memory,
    parse_network,
)


class ServerMonitorTests(unittest.TestCase):
    def test_cpu_parser_calculates_busy_time_between_samples(self):
        previous = parse_cpu_counters("cpu 100 0 50 800 50 0 0 0")
        current = parse_cpu_counters("cpu 120 0 80 830 70 0 0 0")

        self.assertEqual(previous, (1000, 850))
        self.assertEqual(cpu_percent(previous, current), 50.0)

    def test_cpu_first_sample_has_no_assumed_load(self):
        self.assertEqual(cpu_percent(None, (100, 40)), 0.0)

    def test_memory_parser_uses_available_memory(self):
        memory = parse_memory("MemTotal: 1000 kB\nMemAvailable: 250 kB\n")

        self.assertEqual(memory["used"], 750 * 1024)
        self.assertEqual(memory["percent"], 75.0)

    def test_network_parser_sums_non_loopback_interfaces(self):
        data = (
            "Inter-| Receive | Transmit\n"
            " face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n"
            "  lo: 99 0 0 0 0 0 0 0 101 0 0 0 0 0 0 0\n"
            "eth0: 1000 0 0 0 0 0 0 0 2000 0 0 0 0 0 0 0\n"
        )

        self.assertEqual(parse_network(data), (1000, 2000))

    def test_format_helpers_bound_graph_and_render_monitor_sections(self):
        self.assertEqual(format_bytes(1024 * 1024), "1.0 MiB")
        self.assertEqual(format_duration(90061), "1d 01:01")
        self.assertEqual(len(graph([0, 50, 100], width=8)), 8)
        monitor = ServerMonitor()
        monitor.cpu_history.extend((10, 50, 90))
        monitor.memory_history.extend((20, 40, 60))
        now = dt.datetime(2026, 10, 6, 12, tzinfo=ZoneInfo("Europe/Kyiv"))
        report = monitor.render({
            "host": "plotter-1", "time": now, "uptime": 3600,
            "cpu": 42.0,
            "memory": {"used": 3 * 1024 ** 3, "total": 8 * 1024 ** 3, "percent": 37.5},
            "disk": shutil._ntuple_diskusage(total=1000, used=400, free=600),
            "network_rates": (1024, 2048),
            "game_status": "active", "database_status": "active",
            "api_healthy": True, "api_error": None, "online": 3,
            "database_error": None, "service_started": "today", "ntp_status": "yes",
            "errors": [], "load_average": (0.5, 0.4, 0.3),
        }, width=80)

        self.assertIn("ONLINE 3", report)
        self.assertIn("CPU", report)
        self.assertIn("RECENT GAME / POSTGRES ERRORS", report)


if __name__ == "__main__":
    unittest.main()
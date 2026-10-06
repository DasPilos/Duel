# Z440 Server Monitor

`ops/monitor.py` is a local, read-only terminal dashboard for the Ubuntu host connected to the physical monitor. It is separate from the game server and exposes no monitoring HTTP port.

## Display and Data

The dashboard runs on virtual terminal `tty2`; Ubuntu Server does not need an X/Wayland desktop. It displays:

- Game API health, `game-server.service`, PostgreSQL service, and current online human accounts.
- Host CPU, load averages, memory, root filesystem, network throughput, and uptime.
- Kyiv server time, NTP synchronization status, game service start time, and recent game/PostgreSQL error-level journal entries.
- Short CPU and memory history graphs. Refresh interval is two seconds; press `Q` to exit the foreground dashboard.

The dashboard reads `/proc`, calls `systemctl`, `timedatectl`, and `journalctl`, requests `127.0.0.1:<PORT>/health`, and runs a read-only count query against PostgreSQL. No credentials are rendered or sent over the network. Give `dev-admin` membership in `adm` so it can read the system journal.

## Validate Manually

From the project root on Z440:

```bash
cd /home/dev-admin/game
/home/dev-admin/game/venv/bin/python -m ops.monitor --once
```

Run as `dev-admin`, with the same PostgreSQL environment/password file used by `game-server.service`. The dashboard reports database/API failures in place rather than stopping if an optional data source is unavailable.

## Install on tty2

The installer checks the project interpreter, `/dev/tty2`, and journal permissions before changing services. It disables the tty2 login prompt so the monitor can own that console; tty1 and SSH remain available.

```bash
sudo usermod -aG adm dev-admin
```

After updating group membership (log out/in, or reboot), run:

```bash
cd /home/dev-admin/game
sudo bash deploy/monitor/install.sh
```

The installer installs `game-monitor.service`, switches the attached display to tty2, and enables it at boot. It does not stop, restart, or configure `game-server.service` or PostgreSQL.

Check it over SSH:

```bash
systemctl is-active game-monitor.service
journalctl -u game-monitor.service -n 50 --no-pager
```

## Recovery

If the monitor is not useful or the display should return to a login prompt:

```bash
sudo systemctl disable --now game-monitor.service
sudo systemctl enable --now getty@tty2.service
sudo chvt 1
```

The game server continues independently. To return the display to the dashboard after recovery, start `game-monitor.service` again.

## Development and Tests

The monitor code is portable to import on Windows; host sampling itself requires Linux `/proc` and systemd. Unit tests exercise the parsing and render helpers:

```powershell
python -m unittest tests.test_server_monitor -q
```

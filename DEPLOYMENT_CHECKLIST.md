# Deployment Checklist

## Local Validation

- Confirm `DATABASE_URL` targets the intended development PostgreSQL database and `WORLD_ID` exists.
- Run the affected unittest modules; run `python -m unittest discover -s tests -q` before a release.
- Run `git diff --check` and review `git status --short`.
- Do not publish `bot_state.json`, local tasks, credentials, database files, or generated `client_package.zip`.

## Publish Source to GitHub

Use a focused branch and pull request for normal development. After merge, verify that `origin/main` contains the intended source and documentation. Source is the canonical client/server release; the generated ZIP is not versioned because it is a large derived artifact.

## Update Z440

Z440 uses `/home/dev-admin/game` and `game-server.service`. Before touching the server:

```powershell
ssh dev-admin@192.168.1.230 "git -C /home/dev-admin/game status --short; git -C /home/dev-admin/game rev-parse --short HEAD"
```

If the worktree has changes, stop and identify them. Preserve `bot_state.json` and `venv/`; never use `git reset --hard` or overwrite unrelated files. Deploy only the reviewed files or a clean merged commit. After the source is in place:

```powershell
ssh dev-admin@192.168.1.230 "cd /home/dev-admin/game && python3 -m py_compile server/main.py server/city_population.py server/world_roads.py"
ssh dev-admin@192.168.1.230 "sudo -n /usr/bin/systemctl restart game-server.service"
ssh dev-admin@192.168.1.230 "systemctl is-active game-server.service && curl -fsS http://127.0.0.1:8765/health"
```

Do not copy local PostgreSQL data to Z440. Production environment variables and PostgreSQL credentials stay on the server.

## Publish a Downloadable Client

Build locally from the same source revision:

```powershell
python scripts/build_client_package.py
Get-FileHash client_package.zip -Algorithm SHA256
```

Transfer `client_package.zip` separately to `/home/dev-admin/game/client_package.zip`; it is served by `http://192.168.1.230:8765/download/client`. Verify the downloaded size/hash and `HTTP 200`. Rebuild after client or asset changes. The archive is Python source, not an executable.

## After Deployment

- Verify service status and `/health`.
- Verify the deployed revision or the exact uploaded files.
- Confirm remote `bot_state.json` and `venv/` remain untouched.
- Tell testers whether they must download/restart the client. Client-only changes require an updated client package; server-only changes require a server restart.

The optional physical-monitor dashboard setup is documented separately in [SERVER_MONITOR.md](SERVER_MONITOR.md). It uses tty2 and must not replace the game-server service.

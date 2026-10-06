# Local AI Battle Commentator

## Current Setup

Z440 runs Ollama in the existing `dc-LLM` Docker project with `qwen2.5:7b-instruct` (Q4_K_M, about 4.7 GB). It was tested on the RTX 3090 with a short Russian battle prompt. The current model produced a concise, fact-safe reply; the first cold request took about 12 seconds including load, while generation itself took about 3.6 seconds. The server queues commentary off the HTTP request path and keeps the model warm for 30 minutes.

The model API must only bind to `127.0.0.1:11434`. Open WebUI can continue reaching Ollama through the Docker service name `ollama:11434`; the game server calls the loopback API. `deploy/ai/docker-compose.yml` records this secure binding and preserves the existing Docker volume names. Do not publish the Ollama API to the LAN: it has no authentication.

## Behavior

After `/api/battle/result` accepts and saves a human-versus-human result, the server queues one commentary event. The worker reads both characters from the current PostgreSQL world, derives the winner from the accepted `win`, `loss`, or `draw`, asks the local model for one Russian sentence, and posts it as `Летописец` to the shared `backyard` chat. The event is deduplicated by world and participant pair. NPC battles are ignored.

Only names, classes, and the accepted result are sent to the local model. It does not receive chat history, equipment, inventory, credentials, or database rows. It cannot edit state, decide battle results, award items, delete messages, or mute/ban anyone. If the model is unavailable or times out, the server posts a deterministic result-only line. A bounded queue prevents model latency from delaying the battle HTTP response.

This is battle commentary, not a general conversational chat bot and not an autonomous moderator. Moderation should be a separate shadow-mode feature with human review.

## Configuration

Defaults in `server/ai_commentator.py`:

- URL: `http://127.0.0.1:11434/api/chat`
- Model: `qwen2.5:7b-instruct`
- Timeout: 20 seconds
- Queue capacity: 32 events
- Shared chat location: `backyard`
- Disable the feature with `AI_BATTLE_COMMENTARY=0` in the game-server environment.

Set `OLLAMA_URL` or `OLLAMA_MODEL` in the game-server service environment only when intentionally changing the local endpoint/model. Keep the service bound to loopback.

## Tests and Rollout

```powershell
python -m unittest tests.test_ai_commentator tests.test_server tests.test_card_battle -q
```

After deploying server code, restart `game-server.service`. Test with an actual human-versus-human match: the first commentary may arrive several seconds after the result. If Ollama is stopped, battle completion should remain responsive and the fallback line should appear in chat.

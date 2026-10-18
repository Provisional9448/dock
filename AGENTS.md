# Agents

> Hackathon sprint in progress: read [HACKATHON.md](HACKATHON.md) first.


You are working on Dock, a modular freight voice/SMS toolkit. The product in this repo is detention prevention. Docs are the contract. Code stays small and runnable.

Read in this order: `docs/ARCHITECTURE.md`, `docs/VISION.md`, `docs/DEMO.md`, then the package you were asked to touch.

## How the pieces compose

Modules do not call each other in a graph. They read and write events.

```bash
uv run dock-events cat data/samples/harbor-rye.raw.jsonl \
  | uv run dock-clock --replay --as-of 2026-10-17T22:05:00Z \
  | uv run dock-notify \
  | uv run dock-proof --load LL-88421 --print
```

- stdin and stdout are JSONL except `dock-call plan` and `dock-proof --print`.
- stderr is for humans. Do not write logs to stdout.
- Sort by `occurred_at` when you display. Do not assume file order is time order.
- Derived events have deterministic ids. Appending twice is a no-op. Do not delete or rewrite a line to "fix" a replay.
- `dock-clock` drops facts after `--as-of`. Do not "helpfully" include the future unload when computing a warning.

`arrived` already carries party names and phones. Do not add a database so notify can look up Sam. If a new fact is required later, put it on the event.

## Conventions

- Python 3.11+, uv, pytest. Packages under `packages/dock-*`, import names `dock_events`, `dock_clock`, and so on.
- One module, one job. See the table in `docs/ARCHITECTURE.md`.
- Rules that change what a caller hears belong in code (`dock_call/plan.py`, `dock_intake/normalize.py`), not only in a prompt string.
- Do not import `guava` at module import time. The live functions import it inside the live branch.
- Do not open a socket from a provider `send` method in this starter. A new live send path checks `DOCK_SMS_MODE=live` or `DOCK_CALL_MODE=live` and still has a test that the default refuses.
- Money is `Decimal` in Python and a `"0.00"` string in JSON.
- Timestamps are timezone-aware. Store UTC with a trailing `Z`. Format `America/New_York` only at the edge, and label that zone ET.
- Fake data only. `+155555501xx`, `MC-FAKE-88421`, Harbor & Rye, Northwind, Red Kettle, Lantern Lane. Do not fetch a real load, MC, or phone number into the repo.
- Do not commit `.env` or put a key in a test, a fixture, or a default argument.
- Do not add auth, a queue, or a hosted deploy. The team asked for this starter to stay private.
- Match the existing style: small modules, dataclasses, argparse CLIs, exit code 1 with `dock-<name>: ...` on stderr.

## Test commands

```bash
uv sync
uv run pytest
uv run dock-events schema
uv run dock-web --port 8741
./examples/detention-pipe.sh
uv run python examples/build_sample.py
```

`uv run pytest` must pass with no `GUAVA_API_KEY`. If you add a test that needs Guava, skip it unless the package imports, and never let it dial.

When you change copy or clock math, regenerate `data/samples/harbor-rye.trail.jsonl` and read the diff. The web desk recomputes from the raw log, so a stale trail file fails the pipe test even if the page looks right.

## Touch these together

| Change | Also update |
| --- | --- |
| New event type | `model.py`, `schema_doc.py`, `docs/ARCHITECTURE.md`, a test |
| Clock phase or money | `tests/test_clock.py`, sample trail, `docs/ARCHITECTURE.md` numbers, `docs/DEMO.md` if a headline changes |
| Preset button label | `dock_web/presets.py` and `docs/DEMO.md` |
| Heads-up wording | `dock_notify/compose.py`, notify test, sample trail |
| Call rules | `dock_call/plan.py` and the plan test. Keep the zero-dollar rule. |

## Guava

The CLI and SDK are part of the environment. `.cursor/install.sh` (wired from `.cursor/environment.json`) installs the CLI with `curl -fsSL https://goguava.ai/install.sh | sh`, links it to `/usr/local/bin/guava`, and runs `uv sync --frozen`. `guava-sdk>=0.48` is a root dependency. Do not log in and do not write keys into the repo.

```bash
guava --version
uv run python -c "import guava"
```

Auth, only when a task needs a live call: `guava login`, or the `GUAVA_API_KEY` environment variable. `GUAVA_AGENT_NUMBER` is the from-number. Leave both unset for tests.

- Quickstart: <https://docs.goguava.ai/getting-started/quickstart>
- Docs index: <https://docs.goguava.ai/llms.txt>
- Coding-agent starter: <https://goguava.ai/docs/coding-agent-starter.md>

- Inbound: `agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])`.
- Outbound: `agent.call_phone(from_number=..., to_number=..., variables=...)`.
- Tests without audio: `agent.chat(variables=...)` and `agent.roleplay(prompt, variables=...)`.
- Outbound identity: `call.reach_person(...)`. Do not also call `set_voicemail_action`.
- Keep `purpose` to one line. Put the goal in `set_task` and the checklist.
- SMS, if you implement the provider: `guava.Client.send_sms` and `next_sms`. Guava documents these as of 2026-10-17. The Twilio adapter remains a stub beside them.

`packages/dock-intake/dock_intake/guava_inbound.py` and `dock_call/plan.py` `serve_outbound` are the seams. Extend those. Do not start a second agent framework.

## Leave the roadmap as docs

`dock-status`, `dock-docs`, fleet compliance, and crash intake are specified in `docs/ROADMAP.md` and nowhere else. Do not create empty packages for them in a drive-by refactor. Crash intake has extra constraints in that file. Read them before adding fields about an accident.

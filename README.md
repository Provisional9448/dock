# Dock

Dock is a small, open toolkit for freight voice and SMS agents. The first workflow is **detention prevention**: a driver arrives and the receiver is not ready to unload, so a free-time clock starts, the shipper and consignee get a heads-up while there is still time to fix it, and the broker keeps a timestamped trail. The trail is there so the charge is not a surprise on the invoice.

This starter was built for the Guava voice-agent hackathon on October 17, 2026. The code is intentionally thin. The docs are the map for human teammates and coding agents. It stays private to the team: do not publish the package or deploy it.

All names, phone numbers, and loads in this repo are fictional.

## Pitch

Appointment and pickup slips are the everyday failure. "Where is it?" is the high-volume question. Storage, demurrage, detention, and wait time are rarer and much more expensive, and they grow after free time. Missing paperwork stops crossings and billing. Surprise accessorials get fought at invoice time.

Dock starts with the expensive quiet one. A driver reports, by voice or SMS, that the dock will not take the trailer. The clock runs in the open. The people who can fix it hear about it before free time ends, with the estimate so far and the specific thing that stops the charge. Later, the same events are the proof pack.

The shape is Unix. Each module does one job, speaks JSONL, and can be piped. A bigger freight agent can reuse a module without taking the rest.

## Inbound-only hackathon sprint

The current sprint handles incoming shipment-status calls and confirmed on-site delay reports for one fictional load. See [docs/INBOUND_DEMO.md](docs/INBOUND_DEMO.md) for offline status, inbound listening and a read-only evidence view. No outbound calls, SMS or transfers are part of this sprint.

## 60-second demo

No carrier, no Guava account, no SMS provider.

1. `uv run dock-web --port 8741` and open [the desk](http://127.0.0.1:8741).
2. You are on the carrier view. Luis Ortega is at Harbor & Rye, door 4. Free time is running. The estimate is `$0.00`.
3. Press **30 min of free time left**. Switch to **Shipper**. Sam Okonkwo has a heads-up: `$0.00` so far, and the minute the clock starts costing money.
4. Press **15 min past free time**. The trail shows `$18.75`. Priya Shah's call is on the timeline: she asked for about 40 minutes, and the meter is already on.
5. Press **Unload started**. Switch to **Broker**. The clock has stopped. The pack supports `$56.25`. It says, on the page, that this is not an invoice.

The longer script, including playing the driver by SMS, is [docs/DEMO.md](docs/DEMO.md).

## Quickstart

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run dock-web --port 8741
```

The desk listens on `0.0.0.0:8741`. Open `http://127.0.0.1:8741`.

The same story as a pipe, writing a markdown trail and touching no network:

```bash
./examples/detention-pipe.sh
```

That is:

```bash
uv run dock-events cat data/samples/harbor-rye.raw.jsonl \
  | uv run dock-clock --replay --as-of 2026-10-17T22:05:00Z \
  | uv run dock-notify \
  | uv run dock-proof --load LL-88421 --out data/runtime/LL-88421-trail.md
```

Regenerate the committed sample trail after a clock or copy change:

```bash
uv run python examples/build_sample.py
uv run pytest
```

Copy `.env.example` to `.env` only when you are ready to try a live Guava call. Never commit `.env`. The Saturday demo does not need it.

## What runs, what is stubbed

| Module | What it does | In this starter |
| --- | --- | --- |
| `dock-events` | Schema and append-only JSONL log | Runs |
| `dock-clock` | Free-time clock, emits `charge_risk` | Runs |
| `dock-intake` | Driver text to events | Original text rules plus persistent structured inbound reports. `dock-inbound` listens only with `DOCK_INBOUND_MODE=live` |
| `dock-notify` | Heads-up with the estimate and how to avoid it | Composes events. Providers do not send |
| `dock-call` | Scripted outbound goal, rules in code | `plan` and `simulate` run. `call_phone` is gated |
| `dock-proof` | Timeline to a detention trail | Runs |
| `dock-web` | Shipper, carrier, and broker over the same events | Original sample in memory; optional read-only runtime log view |

There is no `dock-status`, `dock-docs`, fleet-compliance, or crash-intake code. Those are described in [docs/ROADMAP.md](docs/ROADMAP.md) only.

SMS sits behind a provider interface (`log`, `twilio`, `guava`). The Twilio and Guava adapters return a stub receipt and do not open a socket. Guava's current docs do include SMS (`client.send_sms`, `client.next_sms`); see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The web desk always uses the log provider.

## Repo map

```
docs/VISION.md          why detention, and what Dock refuses to be
docs/ARCHITECTURE.md    diagram, event schema, module contracts
docs/ROADMAP.md         later modules, docs only
docs/DEMO.md            Saturday script
AGENTS.md               conventions for coding agents
CONTRIBUTING.md         pick a module
.cursor/install.sh      Guava CLI, uv, and uv sync for cloud agents
packages/dock-*/        one package per module
data/samples/           fictional load, raw facts, derived trail
examples/               pipe and sample builder
tests/                  pytest
```

## Voice

Guava is the voice runtime. The Python package `guava-sdk` (pinned `>=0.48`) is a project dependency, so `uv sync` installs it. Cloud agents also get the Guava CLI from `.cursor/install.sh`, which runs on environment setup and links `guava` onto `/usr/local/bin`.

```bash
guava --version
uv run python -c "import guava"
```

Docs:

- Quickstart: <https://docs.goguava.ai/getting-started/quickstart>
- Full index: <https://docs.goguava.ai/llms.txt>
- Coding-agent starter: <https://goguava.ai/docs/coding-agent-starter.md>

Authenticate with `guava login`, or export `GUAVA_API_KEY` (and `GUAVA_AGENT_NUMBER` when you dial). Do not commit either value. The Saturday demo and `uv run pytest` do not need a key. Offline commands do not import Guava. Building an agent for SDK inspection imports it without starting a transport; listening requires the separate inbound gate.

## License

[MIT](LICENSE).

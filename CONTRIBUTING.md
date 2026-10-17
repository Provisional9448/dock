# Contributing

Pick one module and finish its job. The detention story is the acceptance test: `uv run pytest` stays green, and the Saturday desk still tells the Harbor & Rye story.

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before editing. The event log is the integration. If your change needs a new way for modules to talk, it is probably an event, not an import from a sibling's private helpers.

## Setup

```bash
uv sync
uv run pytest
uv run dock-web --port 8741
```

Python 3.11 or newer. Packages live in `packages/`. Tests live in `tests/` and import the installed modules. uv installs this workspace in editable mode.

Do not commit `.env`, API keys, or anything under `data/runtime/`. Phone numbers in samples stay in the `+155555501xx` fiction range. Do not paste a real MC number, CDL, or facility into the log.

This starter is private to the hackathon team. Do not publish the package.

## Pick a module

| Module | Status | A good first change |
| --- | --- | --- |
| `dock-events` | Runs | Add an event type end to end: `PAYLOAD_RULES`, `schema_doc.py`, a fixture line, a test, and a row in `docs/ARCHITECTURE.md`. |
| `dock-clock` | Runs | The daily sample from the roadmap: a second raw log with a two-day free time and a `$150` day, asserted in `tests/test_clock.py`. |
| `dock-intake` | Rules run, Guava listen is gated | More phrases a driver actually texts ("lumper", "need a door", "check-in desk") mapped to the existing types, with a test that refuses anything still unknown. |
| `dock-call` | Plan and dry run | A `roleplay` test for `receiver_delay` once `guava-sdk` is installed. Do not weaken the "quote dollars only after free time" rule to make a test pass. |
| `dock-notify` | Composes, does not send | A `GuavaSmsProvider.send` that calls `client.send_sms` behind `DOCK_SMS_MODE=live`, with the log provider still the default. |
| `dock-proof` | Runs | Golden-file the markdown against the broker checklist in the roadmap. Keep the "not an invoice" line. |
| `dock-web` | Runs | A second load on the same page. Read both logs. Do not give the roles different facts. |

Roadmap modules (`dock-status`, `dock-docs`, fleet compliance, crash intake) have no package yet. If you start one, add `packages/dock-status` (or whichever), a row in the root `pyproject.toml` workspace, and a paragraph in `docs/ROADMAP.md` that says it now has code. Read the crash section before creating any incident fields.

## Adding an event type

1. Add the name to `EVENT_TYPES` and the required payload to `PAYLOAD_RULES` in `packages/dock-events/dock_events/model.py`.
2. Add the same name to `schema_doc.py`.
3. Teach the one module that writes it to emit valid events. Round-trip them through `event_from_dict` in a test.
4. Document the type in `docs/ARCHITECTURE.md`.
5. If the web timeline should show it, add a label in `packages/dock-web/dock_web/static/index.html` and a line in `present.py`.

Money stays a two-decimal string. Timestamps stay timezone-aware UTC. Event ids stay inside the regex, which is why composed ids use a compact stamp instead of `2026-10-17T20:21:00Z`.

## Tests

```bash
uv run pytest
```

The pipe test compares CLI output to `data/samples/harbor-rye.trail.jsonl`. If you change clock math or heads-up copy on purpose, regenerate and review the diff:

```bash
uv run python examples/build_sample.py
uv run pytest
```

A red test that you do not understand is a stop, not a prompt to delete the assertion. The `$56.25` figure is checked in more than one place because that is the whole product.

## Review

- One job per module. `dock-proof` must not reimplement the clock. `dock-notify` must not decide free time. `dock-web` must not be the only place a rule exists.
- Live calls and live SMS stay behind the env gates. Tests must pass with those variables unset.
- New dependencies need a reason. The web server is the standard library on purpose.

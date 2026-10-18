# Inbound-only demo

This is the October 17 sprint: one fictional load, English, shipment status and confirmed on-site reports. No outbound calls, SMS, transfers or automatic dispatch notifications.

## Prepare and inspect offline

Run from the repo root on Zo:

```bash
uv sync --frozen
uv run --frozen pytest
uv run --frozen dock-inbound status --log data/runtime/inbound-demo.jsonl --as-of 2026-10-17T19:36:00Z
```

This seeds only recorded arrival/delay facts. Expected output: LL-88421 waiting at Harbor & Rye, last report 18:08 UTC, no confirmed ETA, 30 free minutes and $0.00 estimated detention. No prerecorded receiver call or future unload is copied.

The clock is explicitly pinned to fictional sample time, not the wall clock. 19:36 UTC is 3:36 PM ET in the shipment's timezone. Say “now” to report an observation at that pinned time. Past timestamps must include a timezone; future actual events are rejected.

Use a new runtime filename for a new rehearsal. Do not delete prior evidence or use a sample file as the runtime log.

## Receive an inbound call

First authenticate Guava on Zo and verify the account's included inbound channel. The SDK is installed; account access is not supplied by the repository. Keep credentials outside Git and do not paste secrets into a transcript. The .env file is not automatically loaded.

For an available inbound phone number, configure GUAVA_AGENT_NUMBER in the runtime environment, then:

```bash
DOCK_INBOUND_MODE=live uv run --frozen dock-inbound phone --log data/runtime/inbound-demo.jsonl --as-of 2026-10-17T19:36:00Z
```

Call that Guava number from your phone. The listener does not dial anyone.

If the account instead has an included browser calling surface:

```bash
DOCK_INBOUND_MODE=live uv run --frozen dock-inbound webrtc --log data/runtime/inbound-demo.jsonl --as-of 2026-10-17T19:36:00Z
```

An existing code can be passed with --webrtc-code. Use the Guava browser calling surface associated with the code. Custom embedding is not implemented. Verify allowance before using remote features; no paid upgrade is implied.

Leave DOCK_CALL_MODE and DOCK_SMS_MODE disabled. They are separate from DOCK_INBOUND_MODE. Starting an inbound listener needs network/account access; offline status and tests do not.

## Show saved evidence

After the runtime log exists:

```bash
uv run --frozen dock-web --host 127.0.0.1 --port 8742 --runtime-log data/runtime/inbound-demo.jsonl --as-of 2026-10-17T19:36:00Z
```

The read-only view uses saved inbound facts and derived clock/proof. Press **Refresh saved reports** after a call. No notices or call results are fabricated, and reset/text/preset mutations are refused in this mode.

This address is on Zo, not your laptop. A reachable private browser surface must already exist to open it remotely. If unavailable, use the offline status command and JSONL/proof output as the evidence display. No hosted service is deployed by this change.

Without --runtime-log, the original Saturday sample demo remains available. Its text box uses the original limited rules and is separate from the structured inbound agent. Do not use that fixture mode as proof of real calls.

## Combined demo launcher

After checking the included inbound allowance, use the guarded launcher to start the phone listener and its read-only desk in separate tmux sessions:

```bash
DOCK_INBOUND_MODE=live ./scripts/demo-up.sh
```

It runs `uv sync --frozen`, seeds through `dock-inbound status`, then starts `dock-web --runtime-log` and `dock-voice serve` against the same `DOCK_INBOUND_LOG`. The default log is `data/runtime/inbound-demo.jsonl`; `DOCK_INBOUND_AS_OF` defaults to `2026-10-17T19:36:00Z`. Override both for a fresh rehearsal. The web server binds Zo loopback on `PORT` (default 8741).

Keep Guava credentials and `GUAVA_AGENT_NUMBER` in your existing Guava login/runtime configuration or the private shell file `~/.config/dock/env.sh` (`DOCK_ENV` overrides that path). The tmux commands source that file themselves. Do not put secrets in Git. The launcher requires an explicit `DOCK_INBOUND_MODE=live` before sourcing configuration; it refuses existing `dockweb` or `dockvoice` sessions rather than killing them. It does not retry failed listeners. Inspect `/tmp/dockweb.log` and `/tmp/dockvoice.log` for readiness; creating a tmux session alone does not prove a live connection.

There is no launcher `replay` option. `dock-live replay` is a separate scripted simulation using its separate `live.jsonl` log; never direct it into the shared inbound log or present its scripted events as real call evidence.

## Two rehearsals

1. Call and ask for LL-88421. Check the agent states last reported status and admits no confirmed ETA. Report that unloading has **not** started and an expected start is “in 20 minutes.” Listen to the readback and confirm it. Refresh evidence: still waiting, expectation separate, clock not stopped.
2. Call again and ask for the load status. The saved report should be reflected. Report that unloading actually started “now,” then confirm the readback. Refresh evidence: actual unload event and stopped clock, $0.00 at this pinned free-time checkpoint.

For an accruing variant, start a fresh runtime log with --as-of 2026-10-17T20:21:00Z. The estimate should be $18.75; actual unloading at that pinned time stops further accrual.

Also try an unknown load, a correction, and decline confirmation. No fact should be invented or saved without confirmation. If a caller asks for dispatch, the agent must not claim it contacted anyone.

## Verification boundary

Offline tests exercise real event persistence/clock code and Guava handlers with simulated call objects. They do not prove speech recognition, natural-language extraction, turn timing or phone audio. Actual inbound rehearsals are required before calling this a live-ready demo.

Current build preflight: Guava CLI reports not authenticated; GUAVA_API_KEY and GUAVA_AGENT_NUMBER are unset. No live call or hosted roleplay was performed during implementation.

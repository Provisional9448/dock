# Inbound-only demo

This is the October 17 sprint: one fictional load, English, shipment status and confirmed on-site reports. No outbound calls, SMS or automatic dispatch notifications. Optional human transfer is disabled by default.

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

October 17 hosted text-test follow-up: three scripted Guava test sessions exercised an angry status request, pressure for a guaranteed ETA/refund/callback/transfer, and repeated personal abuse. After the conversation fix, all three spoke the recorded timestamp as 2:08 PM ET, omitted repeated action menus, and left the isolated event logs unchanged. Unsupported promises were refused. The abuse case warned the caller, allowed another turn, then ended after continued insults. These are single-run observations, not a guarantee of every future conversation or phone/audio behavior. The offline suite passed 78 tests.

Facility-local timestamp labels are formatted in code; UTC timestamps remain unchanged in storage. Call guidance acknowledges frustration briefly, keeps status questions read-only, and requires a warning before ending continued personal abuse. Swearing alone is not a reason to end the call. The running phone listener must be restarted separately to load code changes.


## Optional human handoff

An explicit request for a person qualifies, including before providing a load number.
Frustration or swearing alone does not initiate a transfer. Pending shipment reports
are discarded on handoff requests, never saved as a side effect.

Real transfers stay off until the operator verifies account/hackathon eligibility
and approves a destination. Configure `DOCK_TRANSFER_MODE=live`, one fixed
`DOCK_HUMAN_NUMBER` in international phone format, `DOCK_HUMAN_AVAILABLE=true`,
and `DOCK_HANDOFF_STATE` pointing to a dedicated private runtime file.
The availability flag is manual; this demo does not query a staffed queue.
Do not set the destination to the inbound agent's own number.

Limits: one transfer attempt per call and a ten-minute cooldown per incoming caller
number, shared through a locked state file. Failed attempts also consume the limit.
Missing caller identity or unavailable configuration means no transfer. Caller ID
is a throttling signal, not verified identity; this does not stop someone using
multiple numbers. Caller-provided destination numbers are never used.

The agent can report that a connection is being attempted, not that a human has
answered. The SDK command does not establish answer/no-answer outcomes here.
There is no automatic retry or promised callback. Keep the feature disabled for
normal inbound-only rehearsals until a real transfer test is separately approved.

Handoff verification: 109 offline tests passed. A separate 16-request/eight-process
probe allowed one fake transfer and denied the other 15 on cooldown. Hosted text
sessions with fake gate outcomes exercised a human request before a load number,
disabled transfer, and repeated requests after submission. The final pending-case
transcript retained uncertainty about the connection and invoked the fake gate once;
no shipment events changed. No real transfer or answer/no-answer handling was tested.


## Unresolved requests

The voice model interprets the caller's meaning using structured task choices, not
keyword or regex intent matching. If the caller cannot supply a shipment number,
there is no supported alternate lookup in this demo: explain that limitation and
offer a human. Do not collect names or addresses pretending they can be searched.
If the caller is still looking for the number, wait. For an unknown number, allow
one correction before offering escalation. Tool failures and requests requiring
human authority can also lead to an offer; uncertainty alone is not proof of a
blocker.

An offered escalation requires a separate caller acceptance before invoking the
handoff gate. Declining the offer must not transfer or cause repeated offers for
the same blocker. The caller can continue, supply a number later, explicitly ask
for a human, or end the call. Existing availability and attempt limits still apply;
no callback or successful connection is promised. Pending reports are not saved.

Verification: 121 offline tests pass. Hosted text tests with a fake handoff gate
verify missing-number routing and fresh consent before one request, refusal without
a request, and waiting for a number followed by a status lookup. Traced callbacks
confirm the acceptance goes through identification and a separate consent task.
Shipment event logs remain unchanged. These are model-driven text checks, not a
real phone-transfer test; live handoff remains disabled.

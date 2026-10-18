# Inbound session notes

Credit: Brian's agent, on branch `brian` (`docs/INBOUND_DEMO.md`, `docs/SHIPMENT_AGENT_PLAN.md`, and the inbound session, listener, and tests). This branch does not merge `brian`. It keeps the ideas that fit the event log and leaves the live desk alone.

The live path is unchanged. `dock-intake`, `normalize_message`, and `serve()` still behave as on `main`. `serve()` listens only when `DOCK_CALL_MODE=live`. The structured session is opt-in:

```bash
uv run dock-inbound status \
  --log data/runtime/inbound-demo.jsonl \
  --as-of 2026-10-17T19:36:00Z
```

`DOCK_INBOUND_MODE=live` is a separate switch for `dock-inbound phone` or `dock-inbound webrtc`. Setting it does not enable outbound calls or SMS. Offline status and the tests do not import Guava and do not dial.

## What landed

- One runtime JSONL log per rehearsal. It is seeded with LL-88421 `arrived` and `delay_reported` at or before the pinned `--as-of`. The sample's `call_result` and later unload are not copied. The sample file itself is refused, including through a symlink.
- A report is saved only after an explicit confirmation. The event id is a hash of the load and a stable action id, so a retry appends nothing.
- An actual observation cannot be stamped after the pinned clock. A caller time other than `now` must include a timezone; Dock does not guess one. `now` means the pinned clock.
- "Not started" and "they expect to start in 20 minutes" stay a `delay_reported` plus `expected_start`. They do not go through the substring classifier, and they do not write `unload_started`.
- The session never appends `notice_sent`, `call_result`, or clock lines. The estimate in `status` comes from `dock-clock` and is not an invoice. Unknown loads and a missed ETA stay unknown. Dispatch is not described as already contacted.
- `EventLog.read` takes the same file lock as append, so a status read does not observe a half-written line.

## What stayed on Brian's branch

- The replacement of `serve()` and the extra arrival phrases in `normalize_message`. Both would change the listener and the SMS box the live desk uses.
- `docs/INBOUND_DEMO.md`'s combined launcher, the read-only `--runtime-log` desk, and `tests/test_merge_runtime.py`. Those depend on `packages/dock-web` and `packages/dock-voice`, which other agents are editing. The "do not fabricate a notice or a call result" rule is enforced on the session log instead.

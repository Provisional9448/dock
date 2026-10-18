# Dispatcher board fixtures

Fictional loads for the desk in `site/03-dispatcher-board.html`. One JSONL file per load, in the `dock-events` envelope (`source: sample`). Party names and phones ride on `arrived`. There is no second database.

Demo clock: **Sat Oct 17, 2026, 3:50 PM ET** (`2026-10-17T19:50:00Z`).

Policy, same as load `LL-88421`: 120 free minutes, warn when 30 minutes or less remain, `$75.00` per hour, 15-minute steps rounded up, stop when unload starts.

```bash
cat data/samples/board/LL-*.jsonl \
  | uv run dock-clock --replay --as-of 2026-10-17T19:50:00Z
uv run python data/samples/board/check_board.py
```

`dock-clock` drops facts after `--as-of`. The only later fact in this set is Omar Haddad's arrival (`LL-88450` at 4:15 PM ET). He is early for a 4:30 PM appointment, so free time starts at the appointment. His 3:30 PM text ("About 45 out.") is a `call_result` with `goal: driver_eta`. A `delay_reported` with no arrival would start the clock at the text.

`facility` is the DC name. `payload.door` is the door (`door 4`, and so on). Omar has no door; the row is the appointment. Cities are `City, ST`, the same shape as the Harbor & Rye sample.

The top strip at 3:50 PM ET:

| Strip | From the replay |
| --- | --- |
| 4 at risk | 2 `accruing` (Dana, Marcus) and 2 `warning` (Luis 16 min left, Rosa 27 min left) |
| $56.25 accruing | $37.50 + $18.75 |
| +$37.50 every 15 min | two accruing loads × $18.75 |
| Next free time 4:06 PM | earliest free-time end still open, `LL-88421` |
| 5 heads-ups | the voice `notice_sent` lines already in the files |

Those five are inbound calls (outbound calling is off). `dock-notify` will compose extra SMS if you run it on read. Count the voice notices for the strip, not the derived SMS.

Regenerate the JSONL with `uv run python data/samples/board/build_board.py` after editing the load table. `check_board.py` is the assertion.

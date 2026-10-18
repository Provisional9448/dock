# Saturday sample demo

For the inbound-only agent and saved reports, use [INBOUND_DEMO.md](INBOUND_DEMO.md). This document describes the original curated fixture demo.

You can run this with one laptop and no carrier on the phone. The date on the desk is Saturday, October 17, 2026, pinned to the sample. You move that clock with buttons. You do not wait out two hours of free time.

Everyone in the story is fictional.

| Who you can play | Person | Company |
| --- | --- | --- |
| Driver, via the SMS box | Luis Ortega, truck 1841 | Red Kettle Freight |
| Shipper view | Sam Okonkwo | Northwind Orchards, Fresno |
| Consignee who "answered" | Priya Shah | Harbor & Rye Grocery DC, Elizabeth, door 4 |
| Broker view | Alex Kim | Lantern Lane Logistics |

Load `LL-88421`, PO `PO-44190`, 18 pallets of citrus. Appointment 2:00 PM ET. Luis arrives 2:06 PM ET. Free time is 120 minutes, so it ends 4:06 PM ET. After that the sample policy is `$75.00` an hour in 15-minute steps (`$18.75` a step). The clock stops when unload starts.

## Start

```bash
uv sync
uv run dock-web --port 8741
```

Open http://127.0.0.1:8741. The banner should say the desk is fictional and that no call or SMS leaves the machine. If it says it cannot find the sample, you are not in the repo root. Run the command from the root, or pass `--root`.

## Play the carrier, then the shipper

1. Leave the role on **Carrier** and the clock on **Just arrived**.
   You should see Luis at Harbor & Rye, a delay that door 4 is occupied, stamp `ON FREE TIME`, headline `1h 56m free`, estimate `$0.00`.
2. Press **30 min of free time left**. Switch to **Shipper**.
   Sam has one SMS. It says the estimate is `$0.00`, free time ends 4:06 PM ET, and that starting the unload before then keeps the trail at zero. The delivery status on the card is `logged`.
3. Switch back to **Carrier** and press **15 min past free time**.
   The stamp is `ACCRUING` and the headline is `$18.75 on the trail`. The timeline has Priya's call at 3:40 PM ET: she said they could start in about 40 minutes. That 40 minutes is up, and unload has not started. Open **Shipper** again. Sam has a second SMS with `$18.75`.
4. Press **Unload started**. Open **Broker**.
   The stamp is `CLOCK STOPPED`. The headline is `$56.25 supported`. The proof pack is on the page. It includes the appointment, the arrival, both heads-ups, Priya's summary, and the sentence that this is not an invoice. 42 minutes past free time billed as 45, and `45 / 60 * 75 = 56.25`.

If a button does nothing, look at the note under the clock. A red line there is the error.

## Play the driver

Stay on **Carrier**. The three chips fill the text box. **Log driver SMS** stamps the message with the demo clock, not your laptop's clock.

- At **Just arrived**, send "Still waiting. Door is occupied." A new `delay_reported` line shows up. The dollars do not change. Waiting is already the story.
- The phrase "They started unloading." is an `unload_started` at the current demo time. If you send it during free time, the sample's 4:48 PM unload is no longer the first stop, and the estimate can drop to `$0.00` because unload "started" early. That is the clock being consistent. Press **Reset sample** to go back to the curated facts.

"hello?" is rejected. Intake only knows arrival, not-ready, unload started, and unload finished. The page returns that as an error rather than logging a vague event.

## What you should not expect

- No phone rings. `dock-call plan` will print the opening line if you want to read it. It does not dial.
- No SMS is delivered to the 555 numbers. Those numbers are reserved fiction.
- Refreshing the browser resets the desk to **Just arrived**. Extra driver texts live in the server process only. **Reset sample** clears them without a restart.
- The wall clock can be any day. The desk stays on the sample Saturday until you press a preset.

## CLI, if the room has no browser

```bash
./examples/detention-pipe.sh
```

Open `data/runtime/LL-88421-trail.md`. You should find `$0.00`, `$18.75`, and `$56.25`, Priya's sentence, and "This is not an invoice."

To see only the warning, and to watch later facts get held back:

```bash
uv run dock-events cat data/samples/harbor-rye.raw.jsonl \
  | uv run dock-clock --as-of 2026-10-17T19:36:00Z
```

Stderr should mention events held back. Stdout should have a `charge_risk` of phase `warning` and should not yet have the unload.

## Narration you can say out loud

"Luis checked in six minutes late. The door was still full. With half an hour of free time left we texted the shipper, estimate zero, and we called the DC. Priya asked for forty minutes. Forty minutes later the trail says eighteen seventy-five and the trailer is still closed. When they finally start, the pack supports fifty-six twenty-five. We are not sending an invoice. We are showing the timestamps before anybody is surprised by one."

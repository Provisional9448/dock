# Dock: 4-minute demo video script

Fictional load, real Guava voice agent. Outbound calling is disabled at the hackathon, so every
"Dock calls the shipper" moment is shown as **an inbound call to the same agent**: the caller says
"I'm the shipper" and hears exactly the heads-up Dock would have dialed out with.

**Before you hit record (2 min)**
- Box: `dock-web --live` on 8741 and `dock-voice serve` are running (see "Run it" below), or use the public desk.
- Open the live desk full screen: https://dock-desk-production.up.railway.app (or http://127.0.0.1:8741).
- Click **New run**. The clock reads **2:04 PM ET**, stamp **NO CLOCK**.
- Phone on speaker, ready to dial **(240) 212-5485**. Screen recorder captures system audio + mic.
- Backup if a call fails: in a terminal, `uv run dock-live replay --pause 6` plays the whole story into the same log.

| Time | Shot | What you say / do | What the screen shows |
|---|---|---|---|
| 0:00–0:30 | Title card, then the desk at NO CLOCK | "Detention: a truck waits at a dock, free time runs out, and the carrier bills $75 an hour. Nobody hears about it until the invoice, and then everybody fights it. Appointment slips are 80% of the email we see from a real forwarder; detention is rare but the most expensive line. Dock is an open-source voice agent that runs the clock in the open, warns the people who can fix it **before** it costs money, and keeps the proof." | Load bar: LL-88421, 18 pallets citrus, Fresno → Harbor & Rye door 4. |
| 0:30–1:15 | **Live inbound driver call** (phone on speaker, desk visible) | Say first: "Luis already checked in at the receiving window at 2:06. The clerk said no doors, wait in the truck, maybe 40 minutes. He doesn't need directions. He needs that on the record before it turns into a fight over a bill." Dial (240) 212-5485. Agent: AI disclosure, "Are you the driver, the shipper, the consignee, or the broker?" You, one line per question: **"I'm the driver."** / **"Checked in, waiting for a door."** / **"I checked in at the receiving window at 2:06."** / **"Dana at receiving."** / **"No doors open, wait in the truck, they'll call me. Maybe 40 minutes."** Agent reads it back: checked in 2:06, Dana said about 40 minutes so around 2:46, free time ends 4:06, estimate $0.00, shipper and broker get warned before free time runs out. | The carrier column shows `arrived` at **2:06** (when it happened) and `delay_reported` with Dana's words (when he told Dock). Stamp **ON FREE TIME**, free time ends **4:06 PM ET**. If you dial before the demo clock reaches 2:06, Dock moves the demo clock to 2:08 so the check-in is in the past. |
| 1:15–1:35 | **The clock** | "Every view reads one append-only JSONL log. dock-clock does the math on read, so nobody has to remember to start a timer." Click **30 min of free time left**. | Stamp **FREE TIME LOW**, shipper column: "$0.00 so far, charges start at 4:0x." dock-notify's heads-ups appear on the trail. |
| 1:35–2:30 | **Shipper call-in = the outbound heads-up** | "Outbound calling is off at this hackathon, so the shipper calls in and hears exactly what Dock would have called them with." Dial again. You: **"I'm the shipper."** Agent reads the live clock: "Red Kettle's driver, Luis, has been waiting at Harbor and Rye door 4 since 2:0x. Free time ends at 4:0x, 30 minutes from now. Estimate $0.00. If the unload starts before 4:0x, it stays at zero." Ask: "How much is it so far?" (answered from the clock mid-call). Agent: "What can you do, and by when?" You: **"I'll call the DC and get them started in 20 minutes."** | Shipper column: the blue voice bubble is what was spoken. Trail gains `notice_sent` (voice, spoken) and `call_result` with your commitment. |
| (optional) | **Driver call-back** | Dial again: **"I'm the driver."** / **"Still waiting."** / **"Dana says another 20."** Agent logs the new estimate with the time you said it. Later: **"They started unloading at 4:48."** stops the clock at **$56.25**. | New `delay_reported` line; the record shows every promise and when it was made. |
| 2:30–2:50 | Accruing | Click **15 min past free time**. "The commitment slipped. Now it's money, and it's on the record." | Stamp **ACCRUING**, carrier headline **$18.75 on the trail** in red, "Last call" card shows the commitment. |
| 2:50–3:15 | Unload + **broker proof pack** | Type in the Driver SMS box: "They started unloading." → **Log driver SMS** (SMS intake; same log). "Unload started, the clock stops itself." Point at the broker column. "The broker gets a proof pack: every line is a timestamped event: arrival, delay, the heads-up, who said what on the call, the unload. Then the math. And it says on the page: this is not an invoice." Click **Export trail .md**. | Stamp **CLOCK STOPPED**, "$X supported", minute math, proof rows. |
| 3:15–3:45 | **Architecture: Unix pipes** | Cut to terminal: `./examples/detention-pipe.sh` then `cat data/runtime/LL-88421-trail.md`. "Each module does one job and speaks JSONL: dock-intake, dock-events, dock-clock, dock-notify, dock-proof, dock-call, dock-voice, dock-web. Same pipe on the command line as behind the phone line. A bigger freight agent can take one part without the rest." | The pipe in the desk footer; terminal output with $0.00 / $18.75 / $56.25. |
| 3:45–4:00 | **Open source + close** | "MIT on GitHub at Provisional9448/dock. Next: status calls, missing paperwork, fleet compliance, crash intake, all as more parts on the same log. Dock: no invoice shock." | Repo page, then the desk at CLOCK STOPPED. |

## Lines to keep exact
- Opening of every call (compliance): "Hi, this is Dock, an automated AI assistant for detention on load LL-88421. This call may be recorded for the load trail."
- "This is not an invoice."

## If something breaks on camera
- Call doesn't connect: `uv run dock-live replay --pause 6` and narrate over the desk; the shipper line becomes the blue voice bubble.
- Desk not updating: refresh; the log is on disk, nothing is lost.
- Wrong state: **New run** archives the log (`data/runtime/live-*.jsonl.bak`) and resets the clock to 2:04 PM ET.

## Run it
```bash
uv sync
guava login                                   # once; or export GUAVA_API_KEY
export GUAVA_AGENT_NUMBER=+12402125485        # your number from `guava numbers list`
uv run dock-web --live --port 8741 &          # desk at http://127.0.0.1:8741
uv run dock-voice serve                       # inbound line; never dials out
# Public desk instead of local: point the agent at it
#   DOCK_LIVE_URL=https://dock-desk-production.up.railway.app DOCK_WRITE_TOKEN=... uv run dock-voice serve
# No phone? test the agent with Guava's simulated caller:
uv run dock-voice roleplay driver   # or driver-update, shipper, consignee, broker
uv run dock-live replay --pause 4   # scripted fallback for the video
```

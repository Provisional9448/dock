# Dock: 4-minute demo video script

Fictional load, real Guava voice agent. Outbound calling is disabled at the hackathon, so every
"Dock calls the shipper" moment is shown as **an inbound call to the same agent**: the caller says
(Doc knows Sam by caller ID) and hears exactly the heads-up Dock would have dialed out with.

**Before you hit record (2 min)**
- Box: `dock-web --live` on 8741 and `dock-voice serve` are running (see "Run it" below), or use the public desk.
- Open the live desk full screen: **http://127.0.0.1:8741** (the box desk; it shares one log with the phone line). The Railway desk only gets calls when `DOCK_REMOTE=1`.
- Click **New run**. The clock reads **2:04 PM ET**, stamp **NO CLOCK**.
- Phone on speaker, ready to dial **(240) 212-5485**. Screen recorder captures system audio + mic.
- Backup if a call fails: in a terminal, `uv run dock-live replay --pause 6` plays the whole story into the same log.

| Time | Shot | What you say / do | What the screen shows |
|---|---|---|---|
| 0:00–0:30 | Title card, then the desk at NO CLOCK | "Detention: a truck waits at a dock, free time runs out, and the carrier bills $75 an hour. Nobody hears about it until the invoice, and then everybody fights it. Appointment slips are 80% of the email we see from a real forwarder; detention is rare but the most expensive line. Dock is an open-source voice agent that runs the clock in the open, warns the people who can fix it **before** it costs money, and keeps the proof." | Load bar: LL-88421, 18 pallets citrus, Fresno → Harbor & Rye door 4. |
| 0:30–1:15 | **Live inbound driver call** (phone on speaker, desk visible) | Say first: "Luis already checked in at the receiving window at 2:06. The clerk said no doors, wait in the truck, maybe 40 minutes. He doesn't need directions. He needs that written down before it turns into a fight over a bill." Dial (240) 212-5485 from the AgentLine demo phone (+1 205-351-6709 = Luis by caller ID). Doc: **"Hey Luis, Doc on 8 8 4 2 1. Automated line, it's recorded. What's going on?"** You: **"Checked in at the receiving window at 2:06. Dana said no doors, wait in the truck, maybe 40 minutes."** Doc (no money talk; drivers are paid for waiting): **"Got it, checked in 2:06, Dana said no doors, wait in the truck, maybe 40 minutes. Call me when they pull you in. Anything else?"** You: **"No, that's it."** Doc: **"Thanks Luis, talk soon."** Right after, the trail shows two queued notices: **Heads-up call to shipper (outbound disabled in demo)** with the payer script, and **Message to broker**. | The carrier column shows `arrived` at **2:06** (when it happened) and `delay_reported` with Dana's words (when he told Doc). Stamp **ON FREE TIME**, free time ends **4:06 PM ET**. If you dial before the demo clock reaches 2:06, Doc moves the demo clock to 2:08 so the check-in is in the past. |
| 1:15–1:35 | **Shipper acts on the heads-up** | Restart the line as Sam first: `DOCK_CALLER_ROLE=shipper ./scripts/demo-up.sh` (same phone, now Sam by caller ID). Narrate: "Doc queued a heads-up call to the shipper, who pays detention on this load. Outbound calling is off here, so the shipper calls in." Dial. Doc: **"Hey Sam, Doc on 8 8 4 2 1. Automated line, it's recorded. What's up?"** You: **"Any update on my load?"** Doc: "Luis checked in at Harbor and Rye at 2:06 Eastern, they told him about 40 minutes. Free time runs out at 4:06, so about 2 hours left. After that Red Kettle charges $75 an hour. Want to give Harbor and Rye receiving a call and call me back with what they say?" You: **"I'll call them now."** / **"No, that's it."** Hang up, dial again. Doc: "Hey Sam… What's up?" You: **"I called the warehouse manager. They'll have him in door 4 in 20 minutes."** Doc: **"Got it, the warehouse manager says door 4 by 2:2x. I'll let Lantern Lane know. Anything else?"** You: **"No, that's it."** Doc: "Thanks Sam, bye." | Trail: `call_result` *Receiver promise relayed by Sam Okonkwo (shipper)* with the time, and *Message to broker*. |
| 1:35 | **The clock** | "Every view reads one append-only JSONL log. dock-clock does the math on read, so nobody has to remember to start a timer." Click **30 min of free time left**. | Stamp **FREE TIME LOW**, shipper column: "$0.00 so far, charges start at 4:0x." dock-notify's heads-ups appear on the trail. |
| 1:35–2:30 | **Shipper call-in = the outbound heads-up** (on this fictional load the shipper pays detention; the carrier, Red Kettle, invoices; Dock keeps the record that backs the invoice) | "Outbound calling is off at this hackathon, so the shipper calls in and hears exactly what Dock would have called them with." Dial again (line still set to Sam). You: **"Any update?"** Doc, payer-focused: "Luis checked in at Harbor and Rye at 2:06 Eastern… Free time runs out at 4:06, so about 30 minutes left. After that Red Kettle charges $75 an hour. Want to give Harbor and Rye receiving a call and call me back with what they say?" Ask: "How much is it so far?" (answered from the clock mid-call). Doc: "What do you want to do?" You: **"I'll call the DC and get them started in 20 minutes."** / **"No, that's it."** | Shipper column: the blue voice bubble is what was spoken. Trail gains `notice_sent` (voice, spoken) and `call_result` with your commitment. |
| (optional) | **Driver call-back** | Restart as Luis (`./scripts/demo-up.sh`), dial: **"Still waiting. Dana says another 20."** Agent logs the new estimate with the time you said it. Later: **"They started unloading at 4:48."** stops the clock at **$56.25**. | New `delay_reported` line; the record shows every promise and when it was made. |
| 2:30–2:50 | Accruing | Click **15 min past free time**. "The commitment slipped. Now it's money, and it's on the record." | Stamp **ACCRUING**, carrier headline **$18.75 on the trail** in red, "Last call" card shows the commitment. |
| 2:50–3:15 | Unload + **broker proof pack** | Type in the Driver SMS box: "They started unloading." → **Log driver SMS** (SMS intake; same log). "Unload started, the clock stops itself." Point at the broker column. "The broker gets a proof pack: every line is a timestamped event: arrival, delay, the heads-up, who said what on the call, the unload. Then the math. And it says on the page: this is not an invoice." Click **Export trail .md**. | Stamp **CLOCK STOPPED**, "$X supported", minute math, proof rows. |
| 3:15–3:45 | **Architecture: Unix pipes** | Cut to terminal: `./examples/detention-pipe.sh` then `cat data/runtime/LL-88421-trail.md`. "Each module does one job and speaks JSONL: dock-intake, dock-events, dock-clock, dock-notify, dock-proof, dock-call, dock-voice, dock-web. Same pipe on the command line as behind the phone line. A bigger freight agent can take one part without the rest." | The pipe in the desk footer; terminal output with $0.00 / $18.75 / $56.25. |
| 3:45–4:00 | **Open source + close** | "MIT on GitHub at Provisional9448/dock. Next: status calls, missing paperwork, fleet compliance, crash intake, all as more parts on the same log. Dock: no invoice shock." | Repo page, then the desk at CLOCK STOPPED. |

## Lines to keep exact
- Opening of every call (AI + recording disclosure, one short phrase): known caller "Hey Luis, Doc on 8 8 4 2 1. Automated line, it's recorded. What's going on?"; unknown number "Hey, Doc on 8 8 4 2 1, Red Kettle's automated line, it's recorded. Who's this?"
- Caller ID: `data/samples/parties.json` `caller_ids` maps the AgentLine demo phone +1 205-351-6709 to Luis; `DOCK_CALLER_ROLE=shipper|consignee|broker` makes that phone play that party for a take. Fictional +1 555 numbers map to each party.
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

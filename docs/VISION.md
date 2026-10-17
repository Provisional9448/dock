# Vision

Dock is a toolkit of freight-agent parts. It is not a TMS, not a dialer, and not an invoice. The parts share one append-only event log so a human team and a pile of coding agents can build the next part without inventing a second integration.

## The pattern we are copying, without the real freight

These are recurring shapes from freight operations, abstracted. The sample data is fictional on purpose.

- Appointment and pickup times slip more than anything else. A door that was "ready at 14:00" is still occupied at 14:40.
- "Where is it?" is a high-volume inbound question. It is annoying, and it is usually answerable from events the company already has.
- Storage, demurrage, detention, and driver wait time are less common and much more expensive. They start after free time and then grow, by the hour for live detention and by the day for storage and demurrage.
- Missing paperwork (BOL, POD, customs) delays a crossing or a bill even when the truck moved fine.
- Accessorial charges that show up for the first time on an invoice get disputed. The argument is almost never about the arithmetic. It is about whether anyone was told while there was still time to act.

## Why detention prevention is the first product

A driver at a closed door is a fact with a clock on it. The people who can open the door (shipper, consignee, warehouse) are not the person sitting in the truck. If they hear about it during free time, with a plain estimate and a plain instruction, some of those charges never start. If they hear about it only on the invoice, the charge is already a fight.

The product, in one pass:

1. The driver arrives and reports, by voice or SMS, that the receiver is not ready to unload or de-van.
2. A free-time clock starts. Early arrivals do not burn free time before the appointment.
3. Before free time ends, and again if it does end, the agent tells the shipper and the consignee the estimate so far and what stops it.
4. An outbound call can ask the dock for a commit time. The rules of that call are code, not a paragraph of vibes.
5. Every step is an event. The broker can show the trail later. The trail is explicitly not an invoice and not a legal demand.

Shipper, carrier, and broker look at the same events. They do not get three databases that drift.

## Unix, on purpose

Freight agents get big and tangled because every feature wants to own the load record. Dock goes the other way.

- One module, one job.
- Plain text in, plain text out. JSONL events.
- Compose with pipes and with a shared append-only log.
- A module must be usable inside a larger agent without importing the web app.
- Derived facts (`clock_started`, `charge_risk`, `notice_sent`, `claim_drafted`) are events too. They are not hidden columns.

That costs a little ceremony. It means the clock can be tested with no phone, the proof pack can be tested with no clock code of its own, and a new teammate can own one directory.

## Who the three views are for

- **Carrier.** Dispatch and the driver. Did we arrive, is the clock running, what did we report, what will the trail say about us.
- **Shipper.** The person who can call their customer or the warehouse. The heads-up, the time free time ends, the dollars so far, and the sentence that says how to keep the number at zero.
- **Broker.** The person who will be on the email when someone disputes the charge. Both sides' notices, the call result, and the proof pack.

The web desk is a view. It does not invent a parallel story.

## What this starter will not become

- It will not send a real SMS or place a real call unless someone deliberately opens the live gate. The default path logs the message it would have sent.
- It will not pretend a policy rate is a carrier's tariff. The `$75.00` an hour and the `120` free minutes are the policy on the sample load.
- It will not include lumper, layover, or truck-ordered-not-used in the detention number.
- It will not give legal advice, take a crash report, or store a real CDL. Those show up on the roadmap as future modules with their own constraints.
- It will not require Guava, Twilio, or a database to run the demo.

## Success for the hackathon team

A new person can clone the repo, run the tests, play the Saturday desk, and pick a module from [CONTRIBUTING.md](../CONTRIBUTING.md) without asking where the load object lives. The load, for Dock, is the sequence of events with that `load_id`.

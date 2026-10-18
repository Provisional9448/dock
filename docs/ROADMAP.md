# Roadmap

This file is the only place the later modules exist. Do not scaffold them until someone is actually building that one. The detention path is the thing that has to stay true while those ideas wait.

## Current sprint override: inbound only

Brian scoped the October 17 build to inbound shipment-status and on-site delay calls, with an 8 PM Pacific deadline. Status is implemented inside dock-intake for this single-load slice; no empty dock-status package is added. See [INBOUND_DEMO.md](INBOUND_DEMO.md). The outbound/SMS priorities below are later backlog, not tonight's build order.

## Starter and later backlog

Detention prevention, as shipped in this starter:

- `dock-events`, `dock-clock`, `dock-intake` (rules), `dock-notify` (log only), `dock-call` (plan and dry run), `dock-proof`, `dock-web`.

The next five tasks, in the order they unblock a real Saturday-plus-one demo:

1. **Live Guava outbound for `receiver_delay`.** Keep the plan in `dock-call`. Add a roleplay test (`agent.roleplay`) that checks the opening line, the zero-dollar rule during free time, and the voicemail rule. Only after that test is boring, allow `DOCK_CALL_MODE=live` to call `agent.call_phone`.
2. **A Guava SMS provider next to the Twilio stub.** Map `send` onto `guava.Client.send_sms` and replies onto `next_sms`. Leave the provider interface in place. The web desk stays on the log provider.
3. **A second sample load on a daily clock.** Storage or demurrage: two free days, then `$150` a day. The clock already accepts that shape (`--free-minutes 2880 --increment-minutes 1440 --rate-usd-per-hour 6.25`, because `6.25 * 24 = 150`). The sample and the desk do not show it yet.
4. **`dock-status`.** An inbound "where is my load?" line. It reads the log and answers. It appends a `status_requested` event and does not invent location.
5. **Broker checklist for the proof pack.** Sit with the fields a broker actually argues (appointment, arrival, notices, free-time end, unload start, rate, what was excluded) and golden-file `dock-proof` against that list.

## dock-status

Inbound voice on a Guava number (`agent.listen_phone`). The caller asks where a load is. The expert reads the same JSONL log, answers from events it can point at, and says when it does not know. It must not scrape a tracking site and it must not update the clock. A useful first answer for the sample load is: arrived at Harbor & Rye door 4, unload started or not, last heads-up that went out.

New event, when someone builds it: `status_requested`, with the question and the load id. Payload design belongs in `docs/ARCHITECTURE.md` at the same time as the code.

## dock-docs

Chase missing paperwork. BOL, POD, customs packets. The pattern matches detention: something is missing, time is passing, the person who has the document gets a specific ask, and the trail shows who was asked and when. Different clock. A missing POD delays billing. A missing customs packet delays a crossing. Do not reuse detention dollars for document delay. New events would look like `doc_missing`, `doc_requested`, `doc_received`. The intake rules and the notify provider can be reused. The clock should be a sibling module, not a mode flag buried in `dock-clock`, if the time base is "business days until the crossing" rather than "minutes until unload."

## Fleet compliance

CDL, insurance, and maintenance expiries. Same urge as detention: tell someone before the date, not after the truck is held at a gate. This is a different log, or at least a different `load_id` space (a power unit, not a freight bill). Do not put a driver's license number in the detention sample. When this exists, the event payloads should carry expiry dates and document types, and the real document images should live somewhere that is not this git repo.

## Crash intake prep

First notice after a crash is a different product with a different duty of care. This starter does not collect incident data and should not grow a casual form for it.

If a later module exists, it should be a structured checklist that hands off to a human: location, injuries yes or no, cargo secure yes or no, who was told. It should not estimate fault, not advise the driver what to say to the other party, and not store photos in the event log. Voice is a reasonable intake channel. The Guava task would collect fields and stop. The proof pack for a crash is a transcript plus the checklist, marked as an internal note, not a claim against another motor carrier.

Write that module's privacy rules before its schema. Do not copy the detention event types over.

## Explicitly later

- A scheduler that runs `dock-clock` every few minutes against the log. The starter expects a person or a pipe to pass `--as-of`.
- Multi-load inbox for the web desk. The clock already groups by `load_id`. The page shows one load.
- Auth. The desk is a local demo. Do not add accounts in passing.

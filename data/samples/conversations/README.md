# Dock sample tracking requests and partner threads

**All data here is fictional.** Every person, company, phone number, link, tracking code, PRO, container, BOL, load and amount is invented. Links point to `example.com`. The samples copy common freight-coordination patterns (phrasing, cadence, chasing behavior) and contain no real messages.

The fixtures match `../docs/`: Red Kettle Freight (carrier code RKFX, demo), Northwind Orchards in Fresno, Harbor & Rye Grocery DC in Elizabeth NJ, driver Luis Ortega, truck 1841, trailer RKF-53R-2207, container ABCU1234567, load LL-88421, PO-44190, PRO RK-PRO-884210, BOL RK-BOL-50318, appointment HR-APT-30957, detention $75/hr after 2 hours free. Supporting invented roles: Sam Okafor (ops lead at the demo broker Orchard Line Logistics), Dana Whitcomb (Red Kettle dispatch), Keisha Barnwell (Harbor & Rye receiving), Tomás Reyes (Harbor & Rye transportation desk).

## Inbound tracking requests (client → Dock assistant)
| File | What it shows |
|---|---|
| `01-whatsapp-tracking-link-arrival.md` | A live-truck tracking link plus a one-time "report when it reaches the DC" condition |
| `02-whatsapp-more-links-same-instructions.md` | More links (PRO page, container page) under "same instructions", "use the link again", and a dead link replaced |
| `03-whatsapp-group-every-2-hours.md` | Added to a carrier group, with a report wanted every 2 hours |
| `04-whatsapp-let-me-know-when-out.md` | "Let me know when it's out of the yard", followed by quick chasing ("?", "what time it got there?") |

## Partner conversation threads
| File | What it shows |
|---|---|
| `05-thread-dispatch-driver-checkins.md` | Dispatcher and driver check-ins (gate, door, loaded), equipment IDs with the BOL photo, ETA as a range |
| `06-thread-dock-delay-detention.md` | Receiver dock delay, free-time warning, detention at $75/hr, approval that depends on POD times |
| `07-thread-pod-paperwork-chase.md` | POD chase: promise, nudge, partial scan, request for the full page, done |
| `08-thread-customer-status-chase.md` | Customer asks by PO, gets same-day re-asks, status with source times, early warning about an extra charge |

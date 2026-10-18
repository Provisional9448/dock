# Hackathon sprint: read this first (humans and agents)

**Code freeze: 8:30 PM PT, Sat Oct 17 2026.** Deliverables: this repo + a 4-minute demo video.

## Rules that shape the build
- Outbound calling is disabled. Show outbound ability with **inbound** calls: a caller plays the shipper and hears the heads-up Dock would have called them with.
- Two rounds of judging.
- Fictional data only (see docs/DEMO.md). No secrets in the repo; keys come from env (`GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`).

## Demo we're building
1. One Guava inbound line. Driver path: report arrival, door, delay -> events appended to the JSONL log -> `dock-clock` runs. Shipper path: agent reads the clock and speaks the heads-up, logs `notice_sent`.
2. Live web views (carrier / shipper / broker + trail) reading the same log, matching the mocks in `site/`.
3. Scripted replay mode as a fallback for the video.
4. `docs/DEMO-SCRIPT.md`: 4-minute shot list.

## Who owns what (avoid collisions)
| Lane | Owner | Paths |
|---|---|---|
| Guava voice agent, SMS intake | Anthony's agent | `packages/dock-intake`, `packages/dock-call`, any new `packages/dock-voice` |
| Live web app | Anthony's agent | `packages/dock-web`, `site/` |
| **Open for Brian's agent** | Brian | see below |

### Open lanes (pick one, say so in the PR title)
- `packages/dock-proof`: export the timestamped proof pack as Markdown/PDF for the broker view.
- [taken: cloud agent] `packages/dock-notify`: message templates for heads-ups at 30 min left, free time ended, every 15 min accruing; pure functions + tests.
- [taken: cloud agent] Tests: scenario tests for `dock-clock` edge cases (late arrival, clock stop, midnight).
- README: crisp top section for judges (problem, 3-line pitch, how to run, architecture diagram).

## How to contribute
- Branch from `main`, keep PRs small, open a PR; don't push to `main` directly during the sprint.
- Run tests before pushing (see AGENTS.md).
- Don't edit files in someone else's lane without saying so in the PR.

## Live status (updated 6:55 PM PT)
- Pitch: shipper, consignee, broker, carrier all on the same page.
- Box build (in progress): Guava inbound voice agent (`packages/dock-voice`) handling track/status/driver-report/doc requests from any party; live web views; replay mode; `docs/DEMO-SCRIPT.md`.
- Merged: PR #1 `dock-notify` heads-up SMS + voice script.
- Merged: PR #2 `dock-clock` scenario tests + timezone fix.
- Merged: PR #3 `dock-track` tracking-request intake.
- Merged: PR #4 `data/samples/board/` 8-load dispatcher fixtures. The dispatcher board cloud agent was cancelled at 6:15 PM; dock-web is open again.
- Merged: PR #5 README judges section.
- 6:16 PM call fix: the line now speaks the driver read-back from the local clock right away and writes the log in the background (the Railway desk rejected the write with 403, which stalled the call). `demo-up.sh` now has the line and the local desk (http://127.0.0.1:8741) share one log on the box; the Railway desk gets a background copy. Call transcript + WAV are saved to `demo/calls/` after hangup (retries ~2 min).
- Per-party voice (6:45 PM): the driver call only confirms his update (no money). The payer (shipper or consignee, per-load `payer_role` in `parties.json`; fictional: the shipper pays on LL-88421, FOB-destination style) gets the free-time cutoff, what a charge would be, and what to do. The other side gets status only. The broker gets status, the exposure, and the fact that the carrier invoices off the timestamped record. Dock never bills.
- After each driver update the desk shows "Heads-up call to shipper (outbound disabled in demo)" and "Message to broker" with the full text. Nothing is dialed or sent.
- Take 5 (7:19 PM, driver, AgentLine call_CRQ0tK51Xa1qN37o, 57 s, $0.10; AgentLine spend $2.78 of the $3 cap): caller ID worked (+1 205-351-6709 -> Luis, no role question), events hit the local desk and mirrored to Railway. Guava's own transcript (demo/calls/20261017-192020-driver-67944ad7a8291a4a.txt) has "Luis" and "2:06"; "Louise" and "02:06" were AgentLine's caller-side speech-to-text. Fixed after: Doc confirmed twice (the model said "Got it, 2:06 … Thanks, Luis" before the read-back), the read-back said "Clerk said" (now "the clerk said"), and "You still there?" came 15 s after the greeting started (now a soft "Take your time." only after ~20 s of silence). Shipper contact renamed Sam -> Dan Okonkwo.
- Caller ID + dispatcher wording (6:53 PM): Doc knows the caller from the number (AgentLine demo phone +1 205-351-6709 = Luis; `DOCK_CALLER_ROLE=shipper ./scripts/demo-up.sh` makes it Dan), greets by name and only asks "Who's this?" for unknown numbers. Every line follows Anthony's principles (7:12 PM): short, plain, natural; state the situation; each party gets only what they act on. No "load record" / "load trail" / "Logged".
- Shipper call-back (6:50 PM): the payer's heads-up invites them to call Harbor & Rye receiving and call back. "Warehouse manager says door 4 in 20 minutes" is logged as a receiver promise with time and who said it, read back short, and the broker gets a message.
- The clock's heads-up texts (dock-notify) now go to the payer plus a broker status message. Sample trail regenerated.
- Public desk: the Railway desk write token was fixed at 6:40 PM. The voice line writes to the box desk first and copies to Railway in the background; both desks show the same events.
- Driver story rewritten: Luis already checked in at receiving at 2:06 and was told "no doors, wait in the truck, maybe 40 min"; he calls Dock to put that check-in and the promise on the record (no directions). Voice prompts, roleplays, fixtures, `docs/DEMO-SCRIPT.md` updated. Line fixes from the 6:10 test call: says "Eastern" not "ET", correct time left, rate with every $ figure, asks "Anything else?" before hanging up, skips the role question if the caller opens with it.
- Done: fictional docs in `data/samples/docs/`; fictional tracking requests + partner threads in `data/samples/conversations/`; cleaned mocks incl. dispatcher board in `site/`.
- **Note for Brian:** the demo runs on main's `dock-voice` line, which took a real call at 6:10 PM via AgentLine. Your `brian` branch (dock-inbound) overlaps the voice CLI, the desk, `scripts/demo-up.sh` and `docs/DEMO-SCRIPT.md`, so we're holding it until after the 8:30 freeze rather than merging it now. Please put new work on main's layout in separate folders, or ping Anthony. PR #5 (README judges section) is merged; the dock-web board agent was cancelled at 6:15 PM.
- Still open for Brian: `packages/dock-proof` export.

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

## Live status (updated 5:48 PM PT)
- Pitch: shipper, consignee, broker, carrier all on the same page.
- Box build (in progress): Guava inbound voice agent (`packages/dock-voice`) handling track/status/driver-report/doc requests from any party; live web views; replay mode; `docs/DEMO-SCRIPT.md`.
- Merged: PR #1 `dock-notify` heads-up SMS + voice script.
- Merged: PR #2 `dock-clock` scenario tests + timezone fix.
- Cloud agent: `packages/dock-track` tracking-request intake (PR coming).
- Cloud agent: `data/samples/board/` 8-load dispatcher fixtures (PR coming).
- Done: fictional docs in `data/samples/docs/`; fictional tracking requests + partner threads in `data/samples/conversations/`; cleaned mocks incl. dispatcher board in `site/`.
- Still open for Brian: `packages/dock-proof` export, README judges section.

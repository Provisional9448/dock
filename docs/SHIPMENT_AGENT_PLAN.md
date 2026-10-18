# Dock inbound-only demo plan

Updated: October 17, 2026, 5:40 PM Pacific.
Deadline: 8:00 PM Pacific today — approximately 2 hours 20 minutes.
Status: Inbound-only offline candidate implemented and independently reviewed. 40 tests and a runtime HTTP smoke check pass. Guava authentication, account entitlement and two inbound audio rehearsals remain unverified. This replaces the broader plan in e527a5a.

## Tonight's outcome

A person calls Dock, asks about fictional shipment LL-88421, reports an on-site unloading delay, and receives a useful response grounded in recorded facts. A second status inquiry reflects the confirmed report.

Brian's constraint is inbound-only, using the available free-tier allowance. No outbound calls, SMS, transfers or campaigns. Account entitlements have not been independently verified; check the selected inbound channel before spending time on integration. Do not enable billable extras or change the subscription.

One load, English, one inbound Guava agent, two tasks:
1. Check shipment status.
2. Report an on-site delay or actual unloading start.

## Demo conversation

- Caller: “What is the status of LL-88421?”
- Dock: gives last reported facility/stage and update time, and admits when no confirmed ETA exists.
- Caller: “I'm the driver. They still haven't started unloading.”
- Dock: confirms the report, records it, explains remaining free time or the code-calculated detention estimate, and says what information is still needed.
- Caller: “They expect to start in 20 minutes.”
- Dock: records a reported expectation, not actual unloading or a guarantee.
- Later caller: “They started unloading now.”
- Dock: confirms actual start, records it, and the existing clock stops according to sample policy.

When human intervention is needed, say dispatch must review it and record an unresolved note. Do not claim dispatch was contacted or promise a callback. General transit delays receive an honest limited response; automated transit-delay handling is outside tonight's scope and must not start detention.

## Keep and cut

| Keep tonight | Remove from tonight |
| --- | --- |
| Inbound phone OR browser audio, whichever is available first | Outbound follow-up, reach_person, voicemail workflows |
| One fictional load and existing clock | Multi-load UI, GPS/TMS integrations |
| Status, unknown ETA, on-site delay, actual unload | Broad freight workflows and transit-delay automation |
| Guava structured fields and contextual answers | Spanish, warm transfers, campaigns, SMS |
| Append accepted facts using existing JSONL mechanism | New database, queue, scheduler or agent framework |
| Existing dashboard with only a minimal status refresh if time permits | Dashboard redesign, custom voice UI, hosting migration |
| A few focused checks and two real inbound rehearsals | Large roleplay/evaluation suite |

## Guava showcase

Use the existing SDK 0.48.0 seams:
- add_info / on_question: timestamped shipment facts; questions are read-only.
- Field / set_task / on_task_complete: collect and confirm operational reports.
- on_session_end: preserve outcome/partial progress honestly.
- One inbound transport: listen_phone if the account has an available inbound number, otherwise listen_webrtc if included and reachable.

The showcase is a natural status conversation that changes into structured delay intake and persists a verified update. A browser widget/transcript is optional presentation polish, not a prerequisite. Reuse an available Guava call surface if possible rather than build custom browser plumbing. Zo's service quota and private browser reachability are existing uncertainties.

Use offline handler tests first. Hosted roleplay is optional only if included in the allowance and useful; do not assume it is free. The key evidence is an actual inbound audio conversation.

## Timeboxed build sequence (Pacific)

| Time | Deliverable | Cutoff |
| --- | --- | --- |
| 5:40–5:55 PM | Check Guava auth presence without revealing secrets, inbound entitlement and a reachable call surface; prove a basic inbound greeting | If blocked, report the exact account/access requirement immediately. Continue offline handlers, but don't call them a live demo. |
| 5:55–6:30 PM | One load-scoped snapshot and inbound status conversation, including unknown load / missing ETA | Reuse fixtures and existing code. No new package scaffolding unless needed for a runnable module. |
| 6:30–7:05 PM | Structured on-site delay/unload intake, confirmation, append to existing JSONL log, next call reads the accepted update | Negated or predicted unloading must never stop the clock. |
| 7:05–7:25 PM | Minimal evidence display using existing dashboard, or a printed event/proof view if UI integration takes too long | No hosting or UI redesign work. |
| 7:25–7:45 PM | Focused regressions and two complete inbound rehearsals | Fix blockers only; no new features. |
| 7:45–8:00 PM | Freeze code, verify local commit, prepare short demo instructions and fallback recording if available | No feature additions after 7:45. |

These are budget targets, not completion promises. If work starts late, remove presentation polish first. By 7:05, a live inbound status conversation is the minimum useful result. If delay writes cannot be made reliable, keep delay capture explicitly as an unconfirmed note and report that limitation; never demonstrate a false clock update.

## Smallest implementation

Extend the existing inbound adapter and reuse the clock/event modules. Keep one owner and a single runtime JSONL path. No changes to outbound adapters or providers.

Before writing, verify the branch baseline and preserve unrelated changes. Use stable call/session and action identity for repeated event callbacks. Confirmed facts survive restart through the existing append mechanism. Do not promise unimplemented exactly-once guarantees.

Read status for the selected load and explicit demo as-of time; omit future fixture facts. Seed the runtime demo only with facts through its starting time, not the prewritten future call result/unload. Keep fixtures immutable.

For the first slice, actual arrival comes from the fictional sample. Intake accepts on-site delay or unload observations; it does not reinterpret a transit report as on-site arrival. Reuse existing event types and optional payload fields where valid. Only introduce a new event type if necessary, with model/schema/docs/tests together.

Never pass free-form negative sentences through the existing naive substring normalizer. Collect structured state and confirmation, then validate before creating unload_started. Reported expected start stays separate from actual start. Money and free time come from dock-clock, never model arithmetic.

Do not say “saved” until append succeeds. Unconfirmed partial fields are not shipment facts. Read-only questions and dashboard refreshes cannot mutate operational state or send anything.

Keep outbound/SMS paths disabled. No auth secrets or real shipment/customer data in Git. Fictional sample policy remains 120 free minutes, $75/hour, 15-minute increments, explicitly an estimate rather than invoice.

## Required acceptance checks

1. Correct known-load status and observed timestamp; unknown load and absent ETA do not produce invented facts.
2. “Not started unloading” and “will start in 20 minutes” never create unload_started.
3. Confirmed actual unloading stops the clock; existing sample arithmetic stays correct.
4. Accepted report appears in a subsequent call; restart retains it and repeated callback does not duplicate it.
5. Two complete inbound audio rehearsals; identify any remaining presentation limitation.
6. Zero outbound calls, SMS or transfer attempts; default offline tests need no credentials.

## Finish and evidence

Deliver runnable inbound command, demo steps, task-owned commit hash, observed rehearsal results and explicit remaining blockers. No push, merge, deploy or paid account changes are authorized by this plan update.

Documentation already reviewed: repo AGENTS.md, ARCHITECTURE.md, VISION.md, DEMO.md and ROADMAP.md; Guava coding-agent starter, inbound callbacks/tasks, WebRTC widget and testing guides. Prior broad features remain historical research, not tonight's requirements.

Sources:
- https://goguava.ai/docs/coding-agent-starter.md
- https://goguava.ai/docs/webrtc-widgets
- https://docs.goguava.ai/guides/agent-testing

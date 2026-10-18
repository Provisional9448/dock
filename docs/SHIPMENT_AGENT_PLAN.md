# Dock shipment-status and delay voice agent — build plan

Date: 2026-10-17 (America/Los_Angeles)
Status: Proposed implementation plan; documentation only. Brian confirmed status calls and context-appropriate delay handling as the product goal. Feature priorities below are recommendations.
Repository baseline: Provisional9448/dock, branch brian, 02dac62c2f866852e37e2a73d9f1c8ec7a8f6a71.
Guava Python SDK inspected: 0.48.0. Documentation read on 2026-10-17 Pacific.

## Outcome and scope

A caller can ask where a shipment stands, hear the latest supported facts, report a delay, and get the appropriate next step. Dock records what was reported, what it actually did, and what remains unresolved.

Shipment-status voice is now first-demo scope. This deliberately promotes dock-status from the existing roadmap and supersedes the earlier outbound-only demo recommendation. Detention prevention remains the first detailed delay workflow; ordinary transit delays must not automatically start detention charges.

First demo: one fictional load, inbound status and delay conversations over Guava browser audio (phone channel when configured), existing detention calculations, persistent event trail, dashboard evidence, and one controlled outbound dock follow-up. English/Spanish is a showcase candidate after the English path passes. SMS preview remains the default.

No runtime implementation, calls, SMS, account changes, deployments or push are part of writing this plan.

## What the caller experiences

| Situation | Agent behavior | Recorded result |
| --- | --- | --- |
| “Where is LL-88421?” | Resolve the exact load; give last reported location/stage, timestamp and any supported ETA. Explicitly distinguish reported location from live GPS. | Status request and answer evidence |
| Missing/incorrect load reference | Ask for the load reference or one useful correction; do not guess a different shipment. | Unresolved lookup |
| “When will it arrive?” with no ETA | Say no confirmed ETA is available; offer a dispatch follow-up without promising a time. | Follow-up request, if confirmed |
| Driver reports traffic or a missed appointment | Capture cause, reported location, revised ETA if known, and time of report. Confirm key facts. | Delay report; no automatic detention charge |
| Driver is on site and receiver is not ready | Confirm arrival, appointment, unloading state and reason. Use the existing policy clock to explain free time and estimated charges. | Validated operational facts and clock evidence |
| Free time remains | Explain the deadline and that current estimated detention is zero. Ask what can start unloading before the deadline. | Proposed or completed follow-up distinguished |
| Free time has expired | State the code-calculated estimate, rate and as-of time. Ask for a realistic unload commitment. | Actual call outcome and reported commitment |
| “They have not started unloading” | Keep waiting status; never create unload_started. | Delay fact only |
| “They expect to start in 20 minutes” | Record a prediction, not an actual unload start or guaranteed commitment. Confirm timezone/absolute time when needed. | Reported expected start with source |
| Caller requests a human or disputes the charge | Explain the limit, record the issue and request handoff. Transfer only when a configured destination is available. | Escalation requested/completed/failed |
| Missing, stale or conflicting evidence | State the uncertainty, retain both sources, and ask one question that resolves it. | Unresolved issue with evidence |

Caller role and a load number are not production authentication. The first demo uses fictional records in a private setting. A real customer deployment needs a separately designed access policy.

## Guava features selected from the documentation

| Feature | Dock use | Priority and limits |
| --- | --- | --- |
| WebRTC widget and listen_webrtc | “Talk to Dock” inside the existing dashboard, with browser microphone and transcript/chat panel | Core showcase. Requires Guava credentials and an agent code; microphone requires a suitable browser origin. Zo localhost is not the user's laptop. Verify a reachable private surface; existing hosting quota is a known blocker. No public deployment implied. |
| on_question and add_info | Supply a load-scoped, timestamped status snapshot and answer follow-ups from the event log | Core. on_question can run speculatively and concurrently; it must not send messages, change shipment state or launch calls. Do not assume it fires for every utterance. Refresh context after accepted updates. |
| Field, set_task, get_field, on_task_complete | Collect and confirm load reference, delay reason, observed time and unload state | Core. Structured collection does not prove factual correctness: validate before writing events. Use Say only where exact wording matters. |
| on_action_request / on_action | Offer supported actions, then execute the selected action through a checked handler | Core. Suggesting an action is not authorization or completion. Duplicate/concurrent execution must not duplicate side effects. |
| reach_person | Reach the receiving contact, handle voicemail, wrong number, unavailability and refusal distinctly | Core outbound slice. Use its voicemail option, not set_voicemail_action as well; avoid repeating the introduction. |
| on_session_end | Record termination and partial progress when someone hangs up | Core. Cache confirmed facts during the call; do not issue call commands after session end. |
| roleplay, test, patch and MockCall | Reproduce status, delay, ambiguity and failure conversations | Core verification. Mock/unit tests offline; hosted roleplays are separate integration runs and may consume service credits. They are not offline tests or proof of phone audio quality. |
| set_language_mode | English primary, Spanish secondary for a driver conversation | Showcase extension. Preserve load IDs, times and amounts across languages; verify with a fluent reviewer. Installed SDK exposes both languages. |
| Warm transfers using Runner, RemoteCall and a conference | Brief a dispatcher on the load and delay before connecting the caller | Stretch. Requires a second call and an available test recipient; handle decline/no-answer without claiming transfer succeeded. |
| Client SMS and campaigns | Optional explicit status/summary SMS; later controlled retries | Later. Agentic Tenacity is currently pre-call SMS only, not post-call follow-up. Phone/SMS permissions and approved test numbers must be verified. |

Do not add document RAG for live shipment facts. The event log already owns those facts. DocumentQA becomes useful only when an actual policy-document question enters scope.

## Architecture and ownership

Keep the existing Python modules and append-only JSONL integration boundary. Use Guava directly; no second agent framework, database, queue or new hosted service.

- dock-status: implement the already-planned module when its slice starts. Own load-scoped status projection and read-only answers.
- dock-intake: own validation and conversion of confirmed driver/receiver reports into events.
- dock-clock: remain the sole owner of detention time and money calculations.
- dock-call: own outbound goals, Guava conversation adapters and actual call outcomes; extend the existing seam.
- dock-events: own schema validation, append locking and duplicate identity handling.
- dock-notify: own previews and, later, explicit delivery.
- dock-web and dock-proof: read the same runtime event history.

One Dock conversation design with status, report-delay and request-help tasks is sufficient. A dedicated outbound call session is needed to contact the receiver; the optional warm-transfer extension needs a second leg because the original caller must remain connected. Neither requires a new orchestration platform.

Use one task owner and sequential implementation slices because schemas, callbacks and the dashboard share mutable contracts. Documentation research and fixture design can be independent; defer parallel writers until boundaries stabilize.

## Data contract and invariants

Every answer uses a single load_id and an explicit as_of. Filter future demo facts and avoid leaking other loads. Surface source event IDs and latest observed time in the UI; voice gives concise human-readable provenance.

Proposed schema additions, finalized with model.py, schema_doc.py, ARCHITECTURE.md and tests in the same implementation slice:
- status_requested: question, call/session correlation, answer fact IDs and outcome.
- Extend delay_reported with scope (transit or on_site), observed time, reported ETA/expected start, confirmation state and source. A transit delay must not exercise the clock's existing delay-only fallback.
- Extend call_result for structured commitments and distinct contact/call failures. Map Guava outcomes explicitly; current schema does not represent every documented outcome.
- A minimal follow-up/escalation event only if needed to represent requested versus actually completed work.

Reuse arrived, unload_started and unload_done only for confirmed actual events. Do not represent “expected,” “not yet” or historical statements as present completion. Preserve occurrence time separately from recorded time.

Generate stable event identities from call/session plus logical action identity; persist append deduplication. Use an explicit action attempt/result record before enabling outbound side effects. A crash or timeout after dispatch is “outcome unknown,” requiring reconciliation rather than blind redial.

Runtime data stays in the existing ignored runtime area, separate from immutable fixtures. Dashboard GET requests only read/project data; they never send SMS or initiate calls. Demo reset selects a fresh runtime session instead of erasing evidence.

## Build slices and exit checks

1. **Shared facts and persistence.** Add a load-scoped status projection and runtime log seam; fix semantic intake errors and prevent transit delays from starting detention. Exit: restart preserves accepted facts; future events are excluded; unknown load has no invented answer; duplicate event append is a no-op.
2. **Inbound Guava status conversation.** Build agent handlers with credential-free unit tests, then opt-in chat/test/roleplay runs. Exit: caller gets current status, source time and honest unknown ETA; corrections to the load reference work; questions create no operational side effects.
3. **Delay conversation.** Collect structured facts, confirm consequential times/states and persist them. Exit: negated, hypothetical and past unload statements cannot stop the clock; arrival/appointment logic and existing money examples stay correct.
4. **Outbound dock follow-up.** Apply actual call rules, reach the contact and capture a commitment/outcome. Exit: voicemail, refusal, wrong number, dial failure and interrupted calls remain distinct; no caller is told an action completed before evidence exists. Live test uses only an approved recipient and enabled gate.
5. **Dashboard showcase.** Integrate browser calling where reachable; display transcript, sourced status, delay, estimate, next action and actual result. Exit: browser interaction is observed, refresh sends nothing, and fixture/simulated/live data are labeled. If hosting remains blocked, demonstrate via an available authorized Guava surface or phone channel with the local dashboard; do not call the embedded experience complete.
6. **Polish and optional features.** Add Spanish with review, then warm handoff or explicit SMS only if the core story passes. Do not make both optional integrations critical to finishing.

## Demo story and acceptance

Use fictional LL-88421. A broker asks for status. Dock gives the latest on-site update and says it has no confirmed unload time. A driver reports the receiver is still not ready. Dock confirms the facts, shows free time and a zero-dollar estimate, then an operator starts the controlled receiver follow-up. The recipient gives an expected start. Dock records that as a prediction. Later a confirmed unload report stops the clock and updates broker proof.

Show simulated time jumps clearly. Preserve the original sample math: 120 free minutes, $75/hour, 15-minute billing steps; $18.75 at 15 minutes past free time, $56.25 when 42 elapsed minutes round to 45. These are fictional policy estimates, not an invoice.

Required cases: known status; unknown load; absent/stale ETA; mid-call correction; transit delay; receiver delay before/after free time; negated unload; predicted unload; actual unload; duplicate callback; restart; caller hangup; outbound wrong person/voicemail/refusal/failure; requested human unavailable.

Hard checks cover facts, money, events and absence of unauthorized effects. Conversation rubric checks clarity, useful questions and no unsupported promises. Measure response latency from actual runs and report observations; do not invent a performance target or claim roleplay proves audio latency. Keep offline pytest independent of credentials.

## Prerequisites, risks and stop conditions

- Installed SDK methods were inspected, but no Guava session was run for this plan. Credentials, account permissions, browser reachability and live phone behavior remain unverified.
- Documentation spans old goguava.ai pages and newer docs.goguava.ai guides. Match installed signatures before implementation; do not silently upgrade the SDK.
- Existing intake discards inbound normalized events; dashboard state is currently in memory; outbound rules/results are incomplete; SMS adapters are stubs. These are implementation work, not configuration-only fixes.
- Never dial fixture phone numbers. Live recipients and credentials are runtime configuration outside Git.
- Keep DOCK_CALL_MODE and DOCK_SMS_MODE default refusal. Hosted Guava roleplay requires its own explicit test mode because it is a remote service even without dialing.
- Before implementation, update ROADMAP.md and VISION.md to reflect the promoted status scope; update architecture/schema docs only alongside concrete changes. Preserve the original offline demo.
- Stop a slice when its exit checks pass. Roll back task-owned code via Git if needed; preserve runtime evidence. No push, merge or deploy without authorization.

## Documentation consulted

- Repository: AGENTS.md, docs/ARCHITECTURE.md, docs/VISION.md, docs/DEMO.md, docs/ROADMAP.md.
- [Coding-agent starter](https://goguava.ai/docs/coding-agent-starter.md): Agent, tasks, fields, questions/actions, reach_person, session end and language mode.
- [WebRTC widget](https://goguava.ai/docs/webrtc-widgets)
- [Agent testing](https://docs.goguava.ai/guides/agent-testing)
- [Warm transfers](https://docs.goguava.ai/guides/warm-transfers)
- [Agentic Tenacity](https://docs.goguava.ai/guides/agentic-tenacity)
- [Documentation index](https://docs.goguava.ai/llms.txt)

Next implementation task: slice 1, then the inbound status roleplay. This replaces the prior proposal to start with outbound-only roleplay.

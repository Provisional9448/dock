# Dock

Dock is a phone agent that tracks truck waiting time at the loading dock, so drivers, shippers, receivers and brokers all see the same clock.

## The problem

A truck arrives for its appointment, but the receiver isn't ready to unload. After the free time runs out (often two hours), the carrier can bill a detention charge. Usually the shipper only finds out when the invoice shows up, and then everyone argues over whose times are right.

Dock logs the driver's check-in and starts the free-time clock. Anyone on the load can call and hear the same facts: when the clock started, how much free time is left, what the charge would be so far, and what would stop it. The broker gets a timestamped record of each event, so the charge isn't a surprise.

## Try it

- **Call (240) 212-5485.** Say whether you're the driver, shipper, receiver or broker. Try load number LL-88421.
- **Website:** https://dock-landing-production.up.railway.app (you can talk to the agent in your browser)
- **Live desk:** https://dock-desk-production.up.railway.app (shows the load as calls update it)

## Run it locally

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and a [Guava](https://docs.goguava.ai/getting-started/quickstart) account for the phone line.

```bash
uv sync
guava login
./scripts/demo-up.sh
```

This starts the phone agent and the desk at http://127.0.0.1:8741. Without `guava login`, only the desk starts. Run the tests with `uv run pytest`.

## How it's built

Each part is a small Python package in `packages/`. They share one append-only event log.

- `dock-voice`: the phone agent (built on Guava)
- `dock-events`: the event log and its format
- `dock-clock`: the free-time clock and charge estimate
- `dock-intake`: turns driver calls and texts into events
- `dock-notify`: writes the heads-up messages
- `dock-call`: plans outbound calls
- `dock-track`: handles "where is my load?" requests
- `dock-proof`: builds the timestamped record for the broker
- `dock-web`: the live desk
- `dock-landing`: the website

Details are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). If you want to contribute, start with [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

All names, phone numbers and loads in this repo are made up.

Built at the Guava voice-agent hackathon on October 17, 2026.

## License

[MIT](LICENSE)

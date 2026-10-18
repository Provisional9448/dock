# Dock landing

Static page for the public demo line. No login, no user data, no backend.

## Local

From the repo root:

```bash
python3 packages/dock-landing/serve.py
```

Open http://127.0.0.1:8080. The process listens on `0.0.0.0`. Set `PORT` to use another port.

The same files work with the stdlib server, bound to localhost:

```bash
python3 -m http.server 8080 --directory packages/dock-landing --bind 127.0.0.1
```

## Railway

Add a **new** service after this merges. Leave the existing desk service as it is (repo-root `Dockerfile`, `dock-web --live`).

This package does not share code with the rest of the repo, so it is an isolated monorepo service. Config-as-code (`railway.toml`) is not used: new Railway services cannot opt into it.

| Setting | Value |
| --- | --- |
| Source | `Provisional9448/dock`, branch `main` |
| Root directory | `/packages/dock-landing` |
| Builder | Dockerfile |
| Dockerfile path | `Dockerfile` (the one in that directory) |
| Custom start command | empty. The image runs `python -u serve.py` |
| Variables | none. Railway sets `PORT`. Do not add a key |
| Public networking | generate a domain. The server binds `0.0.0.0:$PORT` |
| Health check path | `/` |
| Watch paths | `/packages/dock-landing/**` |

Watch paths are matched from the repo root even when a root directory is set. A push that does not touch this directory should not redeploy the page, and a push that only touches this directory should not be what redeploys the desk.

# Dock landing (alternate)

Static page. No build step. Three.js loads from a CDN in the browser.

```bash
python3 serve.py
```

Open http://127.0.0.1:8080. `PORT` overrides the port. The process binds `0.0.0.0`.

On Railway, set the service root to `packages/dock-landing-alt` so this Dockerfile is the build. The phone button dials the demo line. The orb mic stays off until someone presses **Try the orb**.

"""The public landing page is static, and the server honors PORT."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "packages" / "dock-landing"
HTML = (PAGE / "index.html").read_text()


def test_page_copy() -> None:
    assert "Talk to an agent" in HTML
    assert 'href="tel:+12402125485"' in HTML
    assert "(240) 212-5485" in HTML
    assert "LL-88421" in HTML
    assert "It’s LL-88421, this is Dan at Northwind Orchards." in HTML
    assert "Role alone never verifies." in HTML
    assert "general information only" in HTML
    assert "Waiting time," in HTML
    assert 'src="hero.js"' in HTML
    assert "Try the orb" not in HTML and 'id="talk"' in HTML and "data-webrtc-code" in HTML
    for phrase in (
        "Northwind Orchards",
        "Dan",
        "Harbor &amp; Rye",
        "Priya",
        "Lantern Lane",
        "Alex",
        "Red Kettle",
        "Luis",
        "4:06",
        "$75 an hour",
        "https://github.com/Provisional9448/dock",
    ):
        assert phrase in HTML
    assert "Second Shift" not in HTML
    assert "Sam Okonkwo" not in HTML
    assert 'href="styles.css"' in HTML


def test_railway_contract() -> None:
    server = (PAGE / "serve.py").read_text()
    docker = (PAGE / "Dockerfile").read_text()
    css = (PAGE / "styles.css").read_text()
    hero = (PAGE / "hero.js").read_text()
    assert 'ThreadingHTTPServer(("0.0.0.0", port), Handler)' in server
    assert 'os.environ.get("PORT", "8080")' in server
    assert "python" in docker and "serve.py" in docker and "hero.js" in docker
    assert "PORT=8080" in docker
    assert "prefers-reduced-motion" in css
    assert "unpkg.com/three@" in hero
    assert "prefers-reduced-motion" in hero
    click = hero.find('addEventListener("click"')
    mic = hero.find("getUserMedia")
    assert 0 <= click < mic
    assert "createAnalyser" in hero
    assert "simulated" in hero


def test_server_respects_port() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = os.environ.copy()
    env["PORT"] = str(port)
    proc = subprocess.Popen(
        [sys.executable, str(PAGE / "serve.py")],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        assert proc.stderr is not None
        ready = proc.stderr.readline().decode()
        assert str(port) in ready
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
            body = response.read().decode()
            assert response.status == 200
            assert "Talk to an agent" in body
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/styles.css", timeout=5) as response:
            assert response.status == 200
            assert "font-weight" in response.read().decode()
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_bad_port_exits() -> None:
    env = os.environ.copy()
    env["PORT"] = "nope"
    result = subprocess.run(
        [sys.executable, str(PAGE / "serve.py")],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 1
    assert "PORT" in result.stderr

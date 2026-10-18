"""The compatibility serve command must never construct the legacy agent."""
from pathlib import Path
import importlib.util
import sys

import pytest


@pytest.mark.parametrize('custom', [False, True])
def test_serve_routes_before_guava_or_legacy_import(root, monkeypatch, tmp_path, custom):
    from dock_intake import inbound_cli
    # Load directly so this check also works before the merged workspace is synced.
    spec = importlib.util.spec_from_file_location('voice_cli_under_test', root / 'packages/dock-voice/dock_voice/cli.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(cli, '_root', lambda: tmp_path)
    monkeypatch.setitem(sys.modules, 'guava', None)
    monkeypatch.setitem(sys.modules, 'dock_voice.agent', None)
    monkeypatch.setitem(sys.modules, 'dock_web.live', None)
    monkeypatch.delenv('DOCK_INBOUND_LOG', raising=False)
    monkeypatch.delenv('DOCK_INBOUND_AS_OF', raising=False)
    if custom:
        monkeypatch.setenv('DOCK_INBOUND_LOG', str(tmp_path / 'custom.jsonl'))
        monkeypatch.setenv('DOCK_INBOUND_AS_OF', '2026-10-17T20:21:00Z')
    calls = []
    def fake_main(args):
        calls.append(args)
        return 7
    monkeypatch.setattr(inbound_cli, 'main', fake_main)
    assert cli.main(['serve']) == 7
    assert calls == [[
        'phone', '--root', str(tmp_path),
        '--log', str(tmp_path / ('custom.jsonl' if custom else 'data/runtime/inbound-demo.jsonl')),
        '--as-of', '2026-10-17T20:21:00Z' if custom else '2026-10-17T19:36:00Z',
    ]]

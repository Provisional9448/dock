from __future__ import annotations

import sys
from io import StringIO


def run_cli(main, args: list[str], stdin: str = "") -> tuple[int, str, str]:
    old = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = StringIO(stdin)
    sys.stdout = StringIO()
    sys.stderr = StringIO()
    try:
        code = main(args)
        return code, sys.stdout.getvalue(), sys.stderr.getvalue()
    finally:
        sys.stdin, sys.stdout, sys.stderr = old

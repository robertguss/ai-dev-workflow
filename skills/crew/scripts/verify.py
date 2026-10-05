#!/usr/bin/env python3
"""Run a step's verify commands once, before commit, without reading their output.

  verify.py --issue ID [--timeout SECONDS] -- "command one" "command two" ...

Runs each command from the repository root, writes the full output to a log file,
and prints one JSON object: per command its exit code and the last few output
lines (where test runners put their counts). The driver compares that with the
builder's report; the full log is there only when something disagrees.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import crewlog  # noqa: E402

TAIL_LINES = 5
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def text_of(output: bytes | str | None) -> str:
    # TimeoutExpired carries bytes even when run() was asked for text.
    return output.decode(errors="replace") if isinstance(output, bytes) else output or ""


def tail(text: str) -> list[str]:
    lines = [line.rstrip() for line in ANSI.sub("", text).splitlines() if line.strip()]
    return [line[:200] for line in lines[-TAIL_LINES:]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--timeout", type=int, default=900, help="seconds per command")
    parser.add_argument("commands", nargs="+")
    args = parser.parse_args()

    # The checkout being landed: a crew's worktree, not the main checkout crewlog tags records with.
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or "."
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    log_path = crewlog.LOG.parent / "verify" / f"{args.issue}-{stamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    with log_path.open("w") as log:
        for command in args.commands:
            start = time.perf_counter()
            try:
                out = subprocess.run(command, shell=True, cwd=root, capture_output=True, text=True, timeout=args.timeout)
                code, output = out.returncode, out.stdout + out.stderr
            except subprocess.TimeoutExpired as e:
                code, output = "timeout", text_of(e.stdout) + text_of(e.stderr)
            log.write(f"$ {command}\n{output}\n[exit {code}]\n\n")
            results.append({"command": command, "exit": code, "seconds": round(time.perf_counter() - start, 1), "tail": tail(output)})

    ok = all(r["exit"] == 0 for r in results)
    crewlog.append("verify", issue=args.issue, ok=ok, log=str(log_path),
                   commands=[{k: r[k] for k in ("command", "exit", "seconds")} for r in results])
    print(json.dumps({"issue": args.issue, "ok": ok, "log": str(log_path), "results": results}))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

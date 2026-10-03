#!/usr/bin/env python3
"""Keep the crew layout in the driver's Herdr tab, always:

    +-----------------+-----------------+
    |                 |  oracle (Fable) |
    |  driver (Opus)  +-----------------+
    |                 | builder (Sonnet)|
    +-----------------+-----------------+

  panes.py setup              create the oracle and builder panes if missing; print pane IDs
  panes.py check              verify the layout; exit 1 and list problems if it is wrong
  panes.py restart ROLE       fresh Claude session for oracle|builder in the same pane

Run from the driver's pane (it reads $HERDR_PANE_ID and $HERDR_TAB_ID). Prints JSON.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

ROLE_ARGS = {
    "oracle": ["--model", "fable", "--effort", "high"],
    "builder": ["--model", "sonnet", "--effort", "medium"],
}
# Dropped from the driver's own launch command before reuse: they pick a model or resume old work.
DROP_WITH_VALUE = {"--model", "--effort", "--resume", "-r", "--session-id", "--agent", "--advisor"}
DROP_FLAGS = {"--continue", "-c", "--fork-session"}


def herdr(*args: str) -> dict:
    out = subprocess.run(["herdr", *args], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(json.dumps({"error": f"herdr {' '.join(args)}", "detail": (out.stderr or out.stdout).strip()}))
    return json.loads(out.stdout) if out.stdout.strip().startswith("{") else {}


def env(name: str) -> str:
    value = os.environ.get(name)
    if os.environ.get("HERDR_ENV") != "1" or not value:
        sys.exit(json.dumps({"error": "not inside a Herdr pane"}))
    return value


def names() -> dict[str, str]:
    tab = env("HERDR_TAB_ID").replace(":", "-").lower()  # agent names are [a-z0-9_-]
    return {role: f"{role}-{tab}" for role in ("driver", "oracle", "builder")}


def claude_proc(pane: str) -> dict | None:
    procs = herdr("pane", "process-info", "--pane", pane)["result"]["process_info"]["foreground_processes"]
    return next((p for p in procs if p["argv"] and os.path.basename(p["argv"][0]) == "claude"), None)


def launch_args(role: str) -> list[str]:
    """The driver's own claude arguments (permission mode etc.) with the role's model and effort."""
    proc = claude_proc(env("HERDR_PANE_ID"))
    kept, skip = [], False
    for arg in (proc["argv"][1:] if proc else []):
        if skip:
            skip = False
            continue
        if arg in DROP_WITH_VALUE:
            skip = True
        elif arg.split("=", 1)[0] in DROP_WITH_VALUE or arg in DROP_FLAGS or not arg.startswith("-"):
            continue
        else:
            kept.append(arg)
    return kept + ROLE_ARGS[role]


def agents_in_tab() -> dict[str, str]:
    """Agent name -> pane ID, for live agents in the driver's tab."""
    tab = env("HERDR_TAB_ID")
    agents = herdr("agent", "list")["result"]["agents"]
    return {a["name"]: a["pane_id"] for a in agents if a.get("name") and a["tab_id"] == tab}


def start(role: str, pane: str) -> None:
    herdr("agent", "start", names()[role], "--kind", "claude", "--pane", pane, "--timeout", "90000", "--", *launch_args(role))
    herdr("pane", "rename", pane, role)


def setup() -> dict:
    me = env("HERDR_PANE_ID")
    live = agents_in_tab()
    n = names()
    if n["driver"] not in live:
        herdr("agent", "rename", me, n["driver"])
    oracle = live.get(n["oracle"])
    if not oracle:
        oracle = herdr("pane", "split", me, "--direction", "right", "--ratio", "0.5", "--cwd", os.getcwd(), "--no-focus")["result"]["pane"]["pane_id"]
        start("oracle", oracle)
    builder = live.get(n["builder"])
    if not builder:
        builder = herdr("pane", "split", oracle, "--direction", "down", "--ratio", "0.5", "--cwd", os.getcwd(), "--no-focus")["result"]["pane"]["pane_id"]
        start("builder", builder)
    herdr("pane", "rename", me, "driver")
    return {"driver": me, "oracle": oracle, "builder": builder} | check()


def check() -> dict:
    me = env("HERDR_PANE_ID")
    live = agents_in_tab()
    n = names()
    panes = {p["pane_id"]: p["rect"] for p in herdr("pane", "layout", "--pane", me)["result"]["layout"]["panes"]}
    ids = {"driver": me, "oracle": live.get(n["oracle"]), "builder": live.get(n["builder"])}
    problems = [f"no live {role} agent" for role, pane in ids.items() if not pane]
    if not problems:
        d, o, b = (panes[ids[r]] for r in ("driver", "oracle", "builder"))
        if len(panes) != 3:
            problems.append(f"tab has {len(panes)} panes, expected 3")
        if d["x"] != 0 or o["x"] <= d["x"] or b["x"] != o["x"]:
            problems.append("driver must be the left column; oracle and builder share the right column")
        if not o["y"] < b["y"]:
            problems.append("oracle must be above the builder")
    return {"layout_ok": not problems, "problems": problems}


def restart(role: str) -> dict:
    pane = agents_in_tab().get(names()[role])
    if not pane:
        sys.exit(json.dumps({"error": f"no live {role} agent; run setup"}))
    # Claude Code exits on /exit; a lone ctrl+c only arms "press again to exit".
    herdr("pane", "send-text", pane, "/exit")
    herdr("pane", "send-keys", pane, "enter")
    for keys in ([], ["ctrl+c", "ctrl+c"], ["ctrl+d", "ctrl+d"]):
        if keys:
            herdr("agent", "send-keys", pane, *keys)
        for _ in range(8):
            if claude_proc(pane) is None:
                break
            time.sleep(1)
        if claude_proc(pane) is None:
            break
    else:
        sys.exit(json.dumps({"error": f"{role} pane {pane} did not return to the shell"}))
    start(role, pane)
    return {"restarted": role, "pane": pane} | check()


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup":
        result = setup()
    elif command == "check":
        result = check()
    elif command == "restart" and len(sys.argv) > 2 and sys.argv[2] in ROLE_ARGS:
        result = restart(sys.argv[2])
    else:
        sys.exit(__doc__)
    print(json.dumps(result))
    if result.get("layout_ok") is False:
        sys.exit(1)


if __name__ == "__main__":
    main()

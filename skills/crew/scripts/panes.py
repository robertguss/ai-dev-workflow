#!/usr/bin/env python3
"""Keep the crew layout in the driver's Herdr tab, always:

    +-----------------+-----------------+
    |                 |     oracle      |
    |     driver      +-----------------+
    |                 |     builder     |
    +-----------------+-----------------+

  panes.py setup              create the oracle and builder panes if missing; print pane IDs
  panes.py check              verify the layout; exit 1 and list problems if it is wrong
  panes.py restart ROLE       fresh session for oracle|builder in the same pane
  panes.py args ROLE          the Herdr agent kind and arguments for a new driver|steward|oracle|builder session

Each role runs on the runtime the project's `## Crew` section picks (runtimes.py).

Run from the driver's pane (it reads $HERDR_PANE_ID and $HERDR_TAB_ID). Prints JSON.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import crewlog  # noqa: E402
import runtimes  # noqa: E402


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


def agent_proc(pane: str) -> dict | None:
    """The pane's foreground agent process (any runtime), with its runtime."""
    procs = herdr("pane", "process-info", "--pane", pane)["result"]["process_info"]["foreground_processes"]
    proc = next((p for p in procs if p["argv"] and runtimes.by_process(p["argv"][0])), None)
    return proc and proc | {"runtime": runtimes.by_process(proc["argv"][0])}


def session(pane: str) -> dict | None:
    """The pane's agent session: pid, runtime, session ID and session file (None until its first prompt)."""
    proc = agent_proc(pane)
    if not proc:
        return None
    return {"pid": proc["pid"], "runtime": proc["runtime"].name} | proc["runtime"].session(proc["pid"])


def launch(role: str) -> tuple[str, list[str]]:
    """The Herdr agent kind and arguments for a new session of `role`: the role's runtime, model and effort,
    plus the caller's own settings (permission mode, sandbox) when the caller runs the same runtime."""
    runtime, model, effort = runtimes.for_role(role, crewlog.repo())
    proc = agent_proc(env("HERDR_PANE_ID"))
    own = runtimes.reusable_args(runtime, proc["argv"][1:]) if proc and proc["runtime"] is runtime else []
    return runtime.kind, own + runtime.launch_args(role, model, effort)


def agents_in_tab() -> dict[str, str]:
    """Agent name -> pane ID, for live agents in the driver's tab."""
    tab = env("HERDR_TAB_ID")
    agents = herdr("agent", "list")["result"]["agents"]
    return {a["name"]: a["pane_id"] for a in agents if a.get("name") and a["tab_id"] == tab}


def start(role: str, pane: str) -> None:
    kind, launch_args = launch(role)
    args = ["herdr", "agent", "start", names()[role], "--kind", kind, "--pane", pane, "--timeout", "90000", "--", *launch_args]
    # Herdr releases an exited agent's name a moment after the process ends.
    for _ in range(10):
        out = subprocess.run(args, capture_output=True, text=True)
        if out.returncode == 0 or "agent_name_taken" not in (out.stderr + out.stdout):
            break
        time.sleep(2)
    if out.returncode != 0:
        sys.exit(json.dumps({"error": f"start {role}", "detail": (out.stderr or out.stdout).strip()}))
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
    ended = session(pane)
    # Both runtimes exit on /exit. Codex's command menu takes the first enter to pick the command; in
    # Claude Code the second lands on an empty shell prompt. A lone ctrl+c only arms "press again to exit".
    herdr("pane", "send-text", pane, "/exit")
    herdr("pane", "send-keys", pane, "enter")
    time.sleep(1)
    if agent_proc(pane):
        herdr("pane", "send-keys", pane, "enter")
    for keys in ([], ["ctrl+c", "ctrl+c"], ["ctrl+d", "ctrl+d"]):
        if keys:
            herdr("agent", "send-keys", pane, *keys)
        for _ in range(8):
            if agent_proc(pane) is None:
                break
            time.sleep(1)
        if agent_proc(pane) is None:
            break
    else:
        sys.exit(json.dumps({"error": f"{role} pane {pane} did not return to the shell"}))
    if ended and ended["transcript"]:
        # `crewlog.py usage` adds up sessions ended mid-step from these records.
        crewlog.append("session", role=role, pane=pane, runtime=ended["runtime"], model=runtimes.for_role(role, crewlog.repo())[1],
                       session_id=ended["session_id"], transcript=str(ended["transcript"]))
    start(role, pane)
    return {"restarted": role, "pane": pane} | check()


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup":
        result = setup()
    elif command == "check":
        result = check()
    elif command == "restart" and len(sys.argv) > 2 and sys.argv[2] in ("oracle", "builder"):
        result = restart(sys.argv[2])
    elif command == "args" and len(sys.argv) > 2 and sys.argv[2] in runtimes.ROLES:
        kind, args = launch(sys.argv[2])
        result = {"kind": kind, "args": args}
    else:
        sys.exit(__doc__)
    print(json.dumps(result))
    if result.get("layout_ok") is False:
        sys.exit(1)


if __name__ == "__main__":
    main()

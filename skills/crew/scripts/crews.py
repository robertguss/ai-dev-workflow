#!/usr/bin/env python3
"""Start, list and stop the project's crews. The steward runs this from its own pane.

  crews.py list                 the repository's crews (name, branch, worktree, workspace, driver pane),
                                and whether the steward's ticker runs
  crews.py start --land BRANCH  a new crew: a worktree on branch crew-N off origin/BRANCH, opened as its
                                own Herdr workspace, with a driver started and told to begin
  crews.py stop NAME --land BRANCH
                                close a crew whose work has all landed: its workspace, worktree and branch
  crews.py tick [--every SECONDS]
                                run in a pane beside the steward: prompt it for a pass every SECONDS
                                (default 600) while it is idle; exits when the steward is gone

Each crew's driver builds its own oracle and builder (`panes.py setup`). Prints JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import crewlog  # noqa: E402
import panes  # noqa: E402

CREW = re.compile(r"^crew-(\d+)$")


def git(*args: str, cwd: str | None = None) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    if out.returncode != 0:
        sys.exit(json.dumps({"error": f"git {' '.join(args)}", "detail": (out.stderr or out.stdout).strip()}))
    return out.stdout.strip()


def agent_name(tab: str, role: str) -> str:
    return f"{role}-{tab.replace(':', '-').lower()}"


def steward_name() -> str:
    return agent_name(panes.env("HERDR_TAB_ID"), "steward")


def crews() -> list[dict]:
    root = crewlog.repo()
    worktrees = panes.herdr("worktree", "list", "--cwd", root)["result"]["worktrees"]
    agents = panes.herdr("agent", "list")["result"]["agents"]
    out = []
    for w in worktrees:
        if not CREW.match(w.get("branch") or ""):
            continue
        ws = w.get("open_workspace_id")
        driver = next((a["pane_id"] for a in agents if ws and a.get("name", "").startswith("driver-")
                       and a["pane_id"].startswith(f"{ws}:")), None)
        # No driver: the crew died (or is mid-replacement, for a moment).
        out.append({"crew": w["branch"], "branch": w["branch"], "path": w["path"], "workspace": ws, "driver": driver,
                    "live": driver is not None})
    return out


def exclude_crew_dir(root: str) -> None:
    """Each crew keeps its handoff in an untracked .crew/ directory."""
    exclude = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=root)) / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    lines = exclude.read_text().splitlines() if exclude.exists() else []
    if ".crew/" not in lines:
        exclude.write_text("\n".join(lines + [".crew/"]) + "\n")


def start(land: str) -> dict:
    root = crewlog.repo()
    git("fetch", "--quiet", "origin", land, cwd=root)
    # Never reuse a number: issues keep the label of the crew that built them.
    used = [int(m.group(1)) for b in git("branch", "--list", "crew-*", "--format=%(refname:short)", cwd=root).split()
            if (m := CREW.match(b))]
    used += [int(m.group(1)) for r in crewlog.records(repo_path=root) if r["kind"] == "crew" and (m := CREW.match(r["crew"]))]
    name = f"crew-{max(used, default=0) + 1}"
    exclude_crew_dir(root)
    # Created from the steward's workspace, which is the repository's own.
    made = panes.herdr("worktree", "create", "--workspace", panes.env("HERDR_WORKSPACE_ID"), "--branch", name,
                       "--base", f"origin/{land}", "--label", name, "--no-focus")["result"]
    pane, tab, path = made["root_pane"]["pane_id"], made["tab"]["tab_id"], made["worktree"]["path"]
    kind, launch_args = panes.launch("driver")
    args = ["herdr", "agent", "start", agent_name(tab, "driver"), "--kind", kind, "--pane", pane,
            "--timeout", "90000", "--", *launch_args]
    # The new workspace's shell may still be starting.
    for _ in range(10):
        out = subprocess.run(args, capture_output=True, text=True)
        if out.returncode == 0:
            break
        time.sleep(2)
    else:
        sys.exit(json.dumps({"error": f"start driver for {name}", "detail": (out.stderr or out.stdout).strip(),
                             "workspace": made["workspace"]["workspace_id"]}))
    panes.herdr("pane", "rename", pane, "driver")
    kickoff = (f"Use the crew skill. Your role: driver. You are {name}, working in the worktree {path} on branch "
               f"{name}; you land on {land}. The steward is the agent {steward_name()}.")
    panes.herdr("agent", "prompt", pane, kickoff)
    crewlog.append("crew", event="start", crew=name, land=land, workspace=made["workspace"]["workspace_id"], path=path)
    return {"started": name, "workspace": made["workspace"]["workspace_id"], "driver": pane, "path": path}


def stop(name: str, land: str) -> dict:
    crew = next((c for c in crews() if c["crew"] == name), None)
    if not crew:
        sys.exit(json.dumps({"error": f"no crew {name}"}))
    path = crew["path"]
    if dirty := git("status", "--porcelain", cwd=path):
        sys.exit(json.dumps({"error": f"{name} has uncommitted work", "detail": dirty}))
    git("fetch", "--quiet", "origin", land, cwd=path)
    if unlanded := git("log", "--oneline", f"origin/{land}..HEAD", cwd=path):
        sys.exit(json.dumps({"error": f"{name} has commits not on origin/{land}", "detail": unlanded}))
    if crew["workspace"]:
        panes.herdr("worktree", "remove", "--workspace", crew["workspace"])
    else:
        git("worktree", "remove", path, cwd=crewlog.repo())
    if git("branch", "--list", name, cwd=crewlog.repo()):
        git("branch", "-D", name, cwd=crewlog.repo())
    crewlog.append("crew", event="stop", crew=name, land=land)
    return {"stopped": name}


def ticking() -> bool:
    """Whether a ticker is running for this tab's steward."""
    lock = crewlog.LOG.parent / f"tick-{steward_name()}.pid"
    try:
        os.kill(int(lock.read_text()), 0)
        return True
    except (OSError, ValueError):
        return False


def tick(every: int) -> None:
    """Keep the steward's passes coming, on any runtime. One ticker per steward: a second one exits."""
    name = steward_name()
    if ticking():
        sys.exit(json.dumps({"error": f"a ticker for {name} is already running"}))
    lock = crewlog.LOG.parent / f"tick-{name}.pid"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(os.getpid()))
    missing = 0
    while True:
        time.sleep(every if not missing else 60)
        out = subprocess.run(["herdr", "agent", "get", name], capture_output=True, text=True)
        if out.returncode != 0:
            # A replacement steward takes the name over within seconds; give it a few minutes.
            missing += 1
            if missing >= 5:
                print(json.dumps({"stopped": f"{name} is gone"}))
                return
            continue
        missing = 0
        if json.loads(out.stdout)["result"]["agent"].get("agent_status") in ("idle", "done"):
            subprocess.run(["herdr", "agent", "prompt", name, "Tick: run a steward pass if anything changed in Linear or the crews."],
                           capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    p = sub.add_parser("start"); p.add_argument("--land", required=True)
    p = sub.add_parser("stop"); p.add_argument("name"); p.add_argument("--land", required=True)
    p = sub.add_parser("tick"); p.add_argument("--every", type=int, default=600)
    args = parser.parse_args()
    if args.command == "tick":
        return tick(args.every)
    if args.command == "list":
        result = {"crews": crews(), "ticker": ticking()}
    elif args.command == "start":
        result = start(args.land)
    else:
        result = stop(args.name, args.land)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Which Ready issues can be built alongside the work already in flight?

  parallel.py --input FILE [--shared "glob glob ..."]

FILE is JSON gathered from Linear:

  {"active": [{"id": "ABC-1", "footprint": ["src/auth/"]}],
   "ready":  [{"id": "ABC-2", "footprint": ["src/billing/invoice.ts"], "blocked_by": ["ABC-1"]}]}

`active` is every issue a crew holds (a `crew-N` label, not Done), except split parents.
`ready` is the Ready queue in pull order; `blocked_by` lists only unfinished blockers.
A footprint lists the files and directories the issue will change; a glob counts as
the directory before its first wildcard.

Two issues conflict when a path of one contains or equals a path of the other, when
both touch the shared spine (lockfiles, migrations, CI and the project's `Shared:`
globs), or when either has no footprint. Prints:

  compatible  Ready issues, in order, that conflict with no active issue and are unblocked
  lanes       active issues plus those Ready issues a greedy pass can add without conflict:
              how many crews the queue can keep busy
  addable     how many of those are Ready issues: the most new work the queue offers crews
  conflicts   why each other Ready issue must wait
"""

from __future__ import annotations

import argparse
import json
from fnmatch import fnmatch
from pathlib import Path

SHARED = [
    "package-lock.json", "**/package-lock.json", "pnpm-lock.yaml", "**/pnpm-lock.yaml", "yarn.lock", "**/yarn.lock",
    "bun.lock", "bun.lockb", "Cargo.lock", "Gemfile.lock", "poetry.lock", "uv.lock", "go.sum", "composer.lock",
    "mix.lock", "Package.resolved", "**/Package.resolved", "Podfile.lock",
    "migrations/**", "**/migrations/**", "db/migrate/**", "**/db/migrate/**", "db/schema.rb", "**/schema.prisma",
    "**/schema.sql", ".github/workflows/**",
]


def parts(path: str) -> tuple[str, ...]:
    segments = [p for p in path.strip().strip("/").split("/") if p and p != "."]
    cut = next((i for i, p in enumerate(segments) if any(c in p for c in "*?[")), len(segments))
    return tuple(segments[:cut])


def overlap(a: str, b: str) -> bool:
    """One path equals or contains the other, segment by segment."""
    pa, pb = parts(a), parts(b)
    n = min(len(pa), len(pb))
    return pa[:n] == pb[:n]


def touches_shared(footprint: list[str], shared: list[str]) -> bool:
    return any(fnmatch(p.strip(), g) or fnmatch(p.strip().rstrip("/") + "/", g) for p in footprint for g in shared)


def conflict(x: dict, y: dict, shared: list[str]) -> str | None:
    fx, fy = x.get("footprint") or [], y.get("footprint") or []
    if not fx or not fy:
        return f"{(x if not fx else y)['id']} has no footprint"
    if touches_shared(fx, shared) and touches_shared(fy, shared):
        return f"both {x['id']} and {y['id']} touch the shared spine"
    for a in fx:
        for b in fy:
            if overlap(a, b):
                return f"{x['id']} and {y['id']} both change {a if len(parts(a)) >= len(parts(b)) else b}"
    return None


def plan(active: list[dict], ready: list[dict], shared: list[str]) -> dict:
    compatible, conflicts = [], {}
    for r in ready:
        why = [f"blocked by {', '.join(r['blocked_by'])}"] if r.get("blocked_by") else []
        why += [c for a in active if (c := conflict(r, a, shared))]
        if why:
            conflicts[r["id"]] = list(dict.fromkeys(why))
        else:
            compatible.append(r["id"])
    lanes = list(active)
    for r in ready:
        if r["id"] in compatible and not any(conflict(r, x, shared) for x in lanes):
            lanes.append(r)
    return {"compatible": compatible, "lanes": len(lanes), "addable": len(lanes) - len(active),
            "lane_issues": [x["id"] for x in lanes], "conflicts": conflicts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True)
    parser.add_argument("--shared", default="", help="the project's extra shared globs, space-separated")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text())
    print(json.dumps(plan(data.get("active", []), data.get("ready", []), SHARED + args.shared.split())))


if __name__ == "__main__":
    main()

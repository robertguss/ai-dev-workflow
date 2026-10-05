#!/usr/bin/env python3
"""The crew's evaluation log: Jev's decisions next to what actually happened.

Every record is one JSON line in ~/.local/state/crew/log.jsonl, tagged with the
repository and issue. jev.py writes `decision` records, verify.py writes `verify`
records; the driver writes the rest:

  crewlog.py step     --issue ID                      a step starts (usage is measured from here)
  crewlog.py review   --issue ID --phase P --reviewer oracle|driver --verdict sign-off|changes
                      --p1 N --p2 N --p3 N [--decision DID] [--round N]
  crewlog.py usage    --issue ID                      tokens and estimated cost per role since `step`
  crewlog.py override --issue ID --decision DID --by driver|user --to oracle|self|keep|fresh --why TEXT
  crewlog.py escape   --issue ID --commit SHA --why TEXT    a bug later traced to a crew commit
  crewlog.py mismatch --issue ID --why TEXT           verify.py disagreed with the builder's report
  crewlog.py feedback --issue ID --text TEXT          the user's own verdict on a decision or step
  crewlog.py report   [--days N] [--repo PATH]        how well the gate and fresh checks are doing
  crewlog.py replay   [--flag-at F] [--stakes-at S]   re-run past gate decisions with other thresholds (default: jev.py's)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG = Path(os.environ.get("CREW_LOG", Path.home() / ".local/state/crew/log.jsonl"))
# Estimated $ per million tokens: (input, output, cache read). Cache writes are priced at 1.25x input.
PRICES = {"driver": (4.0, 20.0, 0.20), "builder": (2.0, 10.0, 0.20), "oracle": (10.0, 50.0, 0.25)}


def repo() -> str:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return out.stdout.strip() or os.getcwd()


def append(kind: str, **fields) -> dict:
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind, "repo": repo()}
    record |= {k: v for k, v in fields.items() if v is not None}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as log:
        log.write(json.dumps(record) + "\n")
    return record


def records(days: int | None = None, repo_path: str | None = None) -> list[dict]:
    if not LOG.exists():
        return []
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    out = []
    for line in LOG.open():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and datetime.fromisoformat(r["at"]) < since:
            continue
        if repo_path and r.get("repo") != repo_path:
            continue
        out.append(r)
    return out


# ---------- usage ----------


def usage_since(transcript: Path, since: datetime) -> dict:
    total, seen = Counter(), set()
    for line in transcript.open():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = entry.get("message")
        if entry.get("type") != "assistant" or not isinstance(message, dict) or not message.get("usage"):
            continue
        # Claude Code writes one line per content block, each repeating its message's usage: count each message once.
        if message_id := message.get("id"):
            if message_id in seen:
                continue
            seen.add(message_id)
        stamp = entry.get("timestamp")
        if stamp and datetime.fromisoformat(stamp.replace("Z", "+00:00")) < since:
            continue
        for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            total[key] += message["usage"].get(key) or 0
    return dict(total)


def cost(role: str, u: dict) -> float:
    inp, out, cache_read = PRICES[role]
    return round((
        u.get("input_tokens", 0) * inp
        + u.get("cache_creation_input_tokens", 0) * inp * 1.25
        + u.get("cache_read_input_tokens", 0) * cache_read
        + u.get("output_tokens", 0) * out
    ) / 1e6, 4)


def cmd_usage(args) -> dict:
    sys.path.insert(0, str(Path(__file__).parent))
    import panes  # noqa: E402

    starts = [r for r in records(repo_path=repo()) if r["kind"] == "step" and r.get("issue") == args.issue]
    if not starts:
        sys.exit(json.dumps({"error": f"no `step` record for {args.issue}"}))
    since = datetime.fromisoformat(starts[-1]["at"])
    live = panes.agents_in_tab()
    roles = {role: live.get(name) for role, name in panes.names().items()}
    roles["driver"] = roles["driver"] or os.environ.get("HERDR_PANE_ID")
    per_role = {}
    for role, pane in roles.items():
        if not pane:
            continue
        proc = panes.claude_proc(pane)
        if not proc:
            continue
        session = json.loads((Path.home() / f".claude/sessions/{proc['pid']}.json").read_text())
        transcript = next(Path.home().glob(f".claude/projects/*/{session['sessionId']}.jsonl"))
        u = usage_since(transcript, since)
        per_role[role] = u | {"usd": cost(role, u)}
    return append("usage", issue=args.issue, since=starts[-1]["at"], roles=per_role,
                  usd=round(sum(r["usd"] for r in per_role.values()), 4), counted="per-message")


# ---------- report ----------


def outcome_of(decision: dict, reviews: list[dict]) -> str:
    mine = [r for r in reviews if r.get("decision") == decision["id"]]
    first = next((r for r in mine if r.get("round", 1) == 1), mine[0] if mine else None)
    if not first:
        return "no review logged"
    serious = (first.get("p1", 0) or 0) + (first.get("p2", 0) or 0)
    if decision.get("audit"):
        return "MISS (spot check found P1/P2)" if serious else "spot check clean"
    if decision["send_to"] == "oracle":
        return "oracle found P1/P2" if serious else "oracle found nothing serious"
    return "driver found P1/P2" if serious else "driver found nothing serious"


def cmd_report(args) -> None:
    rs = records(args.days, args.repo)
    decisions = [r for r in rs if r["kind"] == "decision"]
    gates = [d for d in decisions if d.get("command") == "gate"]
    freshes = [d for d in decisions if d.get("command") == "fresh"]
    reviews = [r for r in rs if r["kind"] == "review"]
    print(f"Crew log: {LOG}  ({len(rs)} records{f', last {args.days} days' if args.days else ''})\n")

    print("== Review gate ==")
    outcomes = Counter(outcome_of(g, reviews) for g in gates)
    sends = Counter(("audit" if g.get("audit") else g["send_to"]) for g in gates)
    print(f"  {len(gates)} decisions: {dict(sends)}")
    for outcome, n in outcomes.most_common():
        print(f"    {n:>3}  {outcome}")
    escapes = [r for r in rs if r["kind"] == "escape"]
    self_issues = {g.get("issue") for g in gates if g["send_to"] == "self"}
    escaped_self = [e for e in escapes if e.get("issue") in self_issues]
    print(f"  bugs found later: {len(escapes)} ({len(escaped_self)} on steps the driver reviewed itself)")
    for g in gates:
        o = outcome_of(g, reviews)
        if o.startswith("MISS") or (g.get("issue") in {e.get("issue") for e in escaped_self}):
            print(f"    MISS {g.get('issue')} {g['phase']} stakes={g['stakes']} flags={g['flags']}  {g.get('title', '')}")
    near = [g for g in gates if g["send_to"] == "self" and (g["stakes"] >= 1.2 or max(g["flags"].values()) >= 0.5)]
    print(f"  close calls sent to the driver (stakes >= 1.2 or a flag >= 0.5): {len(near)}")
    for g in near[-10:]:
        print(f"    {g.get('issue')} {g['phase']} stakes={g['stakes']} top flag={max(g['flags'].items(), key=lambda kv: kv[1])}  {g.get('title', '')}")

    print("\n== Fresh sessions ==")
    by_role = Counter((f["role"], f["fresh"]) for f in freshes)
    for (role, fresh), n in sorted(by_role.items()):
        print(f"  {role:<8} {'fresh' if fresh else 'kept':<6} {n}")
    for reason, n in Counter(f["why"].split(" (")[0].split(":")[0] for f in freshes if f["fresh"]).most_common():
        print(f"    {n:>3}  {reason}")

    print("\n== Builder reports ==")
    verifies = [r for r in rs if r["kind"] == "verify"]
    mismatches = [r for r in rs if r["kind"] == "mismatch"]
    print(f"  {len(verifies)} pre-commit verify runs, {sum(1 for v in verifies if not v.get('ok'))} failed; "
          f"{len(mismatches)} reports contradicted by them")
    for m in mismatches[-10:]:
        print(f"    {m['at'][:16]} {m.get('issue', '')} {m.get('why', '')}")

    print("\n== Cost (estimated) ==")
    # Usage records from before `counted` existed added each message's tokens once per content block.
    usage = [r for r in rs if r["kind"] == "usage" and r.get("counted") == "per-message"]
    overcounted = sum(1 for r in rs if r["kind"] == "usage" and r.get("counted") != "per-message")
    per_role = Counter()
    for u in usage:
        for role, v in u.get("roles", {}).items():
            per_role[role] += v["usd"]
    oracle_reviews = sum(1 for r in reviews if r.get("reviewer") == "oracle")
    print(f"  {len(usage)} steps measured: " + ", ".join(f"{role} ${usd:.2f}" for role, usd in per_role.most_common()))
    if overcounted:
        print(f"  ({overcounted} earlier steps left out: their tokens were counted 2-3x over)")
    if oracle_reviews and per_role["oracle"]:
        print(f"  oracle reviews: {oracle_reviews}, about ${per_role['oracle'] / oracle_reviews:.2f} each")

    print("\n== Overrides and feedback ==")
    for r in rs:
        if r["kind"] in ("override", "feedback"):
            print(f"  {r['at'][:16]} {r['kind']:<8} {r.get('issue', '')} {r.get('by', '')} {r.get('to', '')} {r.get('why', r.get('text', ''))}")


def cmd_replay(args) -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    import jev  # noqa: E402

    flag_at = jev.FLAG_AT if args.flag_at is None else args.flag_at
    stakes_at = jev.STAKES_AT if args.stakes_at is None else args.stakes_at
    rs = records(args.days, args.repo)
    reviews = [r for r in rs if r["kind"] == "review"]
    gates = [r for r in rs if r["kind"] == "decision" and r.get("command") == "gate"]
    changed, saved, added, lost = [], 0, 0, 0
    for g in gates:
        # A spot check was logged as `oracle`, but the gate itself had said `self`.
        was = "self" if g.get("audit") else g["send_to"]
        would = jev.decide_gate(g["stakes"], g["flags"], flag_at, stakes_at)["send_to"]
        if would != was:
            o = outcome_of(g, reviews)
            changed.append((g, was, would, o))
            if would == "self" and "P1/P2" in o and "oracle" in o:
                lost += 1
            if would == "self":
                saved += 1
            else:
                added += 1
    print(f"flag_at={flag_at} stakes_at={stakes_at}: {len(changed)} of {len(gates)} decisions change")
    print(f"  {added} more oracle reviews, {saved} fewer; {lost} of the dropped ones had P1/P2 findings the driver would now have to catch")
    for g, was, would, o in changed:
        print(f"  {g.get('issue')} {g['phase']}: {was} -> {would}  [{o}] stakes={g['stakes']}  {g.get('title', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("step"); p.add_argument("--issue", required=True)
    p = sub.add_parser("review")
    for flag in ("--issue", "--phase", "--reviewer", "--verdict"):
        p.add_argument(flag, required=True)
    for flag in ("--p1", "--p2", "--p3", "--round"):
        p.add_argument(flag, type=int, default=1 if flag == "--round" else 0)
    p.add_argument("--decision")
    p = sub.add_parser("usage"); p.add_argument("--issue", required=True)
    p = sub.add_parser("override")
    for flag in ("--issue", "--by", "--to", "--why"):
        p.add_argument(flag, required=True)
    p.add_argument("--decision")
    p = sub.add_parser("escape")
    for flag in ("--issue", "--commit", "--why"):
        p.add_argument(flag, required=True)
    p = sub.add_parser("mismatch")
    for flag in ("--issue", "--why"):
        p.add_argument(flag, required=True)
    p = sub.add_parser("feedback"); p.add_argument("--issue"); p.add_argument("--text", required=True)
    for name in ("report", "replay"):
        p = sub.add_parser(name); p.add_argument("--days", type=int); p.add_argument("--repo")
    p.add_argument("--flag-at", type=float); p.add_argument("--stakes-at", type=float)  # default: jev.py's cutoffs
    args = parser.parse_args()

    if args.command == "report":
        return cmd_report(args)
    if args.command == "replay":
        return cmd_replay(args)
    if args.command == "usage":
        result = cmd_usage(args)
    else:
        fields = {k: v for k, v in vars(args).items() if k != "command"}
        result = append(args.command, **fields)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

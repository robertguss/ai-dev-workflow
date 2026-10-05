#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["typesafe-sdk>=0.7.2"]
# ///
"""Jev judgments for the crew loop. Prints one JSON object; the driver follows it.

  jev.py gate  --issue ID --phase plan|diff --brief FILE [--report FILE] [--previous-report FILE] [--files "a b"]
      Does this step need the (costly) Fable oracle, or can the driver review it itself?
  jev.py fresh --issue ID --role builder|oracle|driver|steward --pane PANE [--next FILE]
      Should this pane's Claude session be restarted fresh before the next step?
  jev.py ready --issue ID --text FILE
      Steward: release this shaped issue to Ready, rewrite it, or ask the user?
  jev.py escalate --issue ID --text FILE --question FILE
      Steward: may it answer this driver's question itself, or must the user?
  jev.py duplicate --issue ID --other ID --text FILE --other-text FILE
      Steward: do these two issues ask for the same change?

Jev answers the fuzzy questions; the thresholds below decide. Every decision is
logged by crewlog.py with an `id`; log the review that follows with `--decision <id>`.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import crewlog  # noqa: E402
import panes  # noqa: E402

MODEL = "jev-1.13.0"
FNOX_GLOBAL = Path.home() / ".config/fnox/config.toml"

# gate: any risk flag at or above FLAG_AT, or stakes at or above STAKES_AT, sends the step to Fable.
FLAG_AT = 0.7
STAKES_AT = 1.5
# ready and escalate: the user decides anything at or above these, so they start cautious.
ASK_FLAG_AT = 0.5
ASK_STAKES_AT = 1.2
# ready: below this an issue is too unclear to build and the steward rewrites it.
CLEAR_AT = 0.6
DUPLICATE_AT = 0.8
# Spot checks: this share of steps judged routine still go to the oracle, so the log can
# show what the gate misses. Set CREW_AUDIT_RATE=0 to turn off.
AUDIT_RATE = float(os.environ.get("CREW_AUDIT_RATE", "0.1"))
# fresh: context sizes (tokens) per role. Above HARD always restart. The builder and oracle work
# one step's code, so they also restart above SOFT when the next step is unrelated; the driver and
# steward carry the whole project, and every step is a different issue, so only HARD applies to them.
CONTEXT = {
    "builder": {"soft": 60_000, "hard": 150_000},
    "oracle": {"soft": 60_000, "hard": 120_000},
    "driver": {"hard": 250_000},
    "steward": {"hard": 250_000},
}
# Below this a session has barely been used: restarting it gains nothing, so Jev is not asked.
FRESH_FLOOR = 20_000
STRUGGLING_AT = 0.7
RELATED_AT = 0.5

# {subject} names what is judged: the step, an issue, or a decision a driver asks for.
RISKS = {
    "security": "Does {subject} change authentication, authorization, secrets, permissions, or who can see data?",
    "data": "Can {subject} change or delete stored data in a way that is hard to undo, such as a migration, backfill, or deletion of records?",
    "concurrency": "Does {subject} involve concurrency, locking, retries, caching, or consistency between services?",
    "money": "Does {subject} affect payments, refunds, billing, or charges?",
    "contract": "Does {subject} change a public API, schema, or contract that other systems or clients depend on?",
    "architecture": "Is {subject} a long-lived design decision that is expensive to reverse later?",
}
SUBJECTS = {
    "gate": "the step in `step`",
    "ready": "the work in `issue`",
    "escalate": "the decision asked in `question`, for the work in `issue`,",
}
STAKES_LEVELS = [
    "Cosmetic or obvious at once, and trivial to revert",
    "A visible bug for some users, fixed with a normal patch",
    "Real harm that is hard to undo: lost or corrupted data, a security hole, wrong charges, or broken clients",
]


def api_key() -> str:
    if key := os.environ.get("TYPESAFE_API_KEY"):
        return key
    for args in (["fnox", "get", "TYPESAFE_API_KEY"], ["fnox", "-c", str(FNOX_GLOBAL), "get", "TYPESAFE_API_KEY"]):
        try:
            out = subprocess.run(args, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    sys.exit(json.dumps({"error": "no TYPESAFE_API_KEY in the environment or fnox"}))


def ask(state: dict, questions: dict):
    from typesafe_sdk import TypeSafeClient

    with TypeSafeClient(api_key=api_key()) as client:
        return client.system_one(state=state, questions=questions, model=MODEL)


def read(path: str | None, limit: int = 12_000) -> str:
    return Path(path).read_text()[:limit] if path else ""


# ---------- gate ----------


def risk_questions(command: str) -> dict:
    from typesafe_sdk import Noul, Score

    subject = SUBJECTS[command]
    questions = {"stakes": Score(
        instructions=f"If {subject} ships with a subtle mistake, how bad is the damage?",
        criteria=STAKES_LEVELS,
    )}
    return questions | {name: Noul(instructions=text.format(subject=subject)) for name, text in RISKS.items()}


def risks_of(response) -> tuple[float, dict[str, float]]:
    return response.scores["stakes"].score, {name: response.nouls[name].noul for name in RISKS}


def gate_questions(has_report: bool) -> dict:
    from typesafe_sdk import Noul

    questions = risk_questions("gate")
    if has_report:
        questions["stuck"] = Noul(
            instructions="Does `step.builder_report` describe the same failure as `step.previous_report`, "
            "or say the builder is stuck, blocked, or going in circles?"
        )
    return questions


def decide_gate(stakes: float, flags: dict[str, float], flag_at: float = FLAG_AT, stakes_at: float = STAKES_AT) -> dict:
    """The gate's one rule. `crewlog.py replay` calls it with other cutoffs."""
    fired = sorted(name for name, p in flags.items() if p >= flag_at)
    send = "oracle" if fired or stakes >= stakes_at else "self"
    why = (
        f"risk flags: {', '.join(fired)}" if fired
        else f"stakes {stakes:.2f} >= {stakes_at}" if stakes >= stakes_at
        else f"routine: stakes {stakes:.2f}, no risk flags"
    )
    return {"send_to": send, "why": why, "stakes": round(stakes, 2), "flags": {k: round(v, 2) for k, v in flags.items()}}


def cmd_gate(args) -> dict:
    step = {"brief": read(args.brief)}
    if args.files:
        step["changed_files"] = args.files.split()
    if args.report:
        step["builder_report"] = read(args.report, 4_000)
        step["previous_report"] = read(args.previous_report, 4_000) or "none"
    response = ask({"step": step}, gate_questions(bool(args.report)))
    flags = {name: response.nouls[name].noul for name in response.nouls}
    result = {"command": "gate", "phase": args.phase} | decide_gate(response.scores["stakes"].score, flags)
    if result["send_to"] == "self" and random.random() < AUDIT_RATE:
        result |= {"send_to": "oracle", "audit": True, "why": f"spot check (would be self: {result['why']})"}
    first_line = step["brief"].strip().splitlines()[0] if step["brief"].strip() else ""
    return result | {"title": first_line[:120], "brief": step["brief"][:6_000]}


# ---------- steward ----------


def high_stakes(stakes: float, flags: dict[str, float]) -> list[str]:
    """Why the user must decide, or [] when the steward may."""
    reasons = []
    if fired := sorted(name for name, p in flags.items() if p >= ASK_FLAG_AT):
        reasons.append(f"risk flags: {', '.join(fired)}")
    if stakes >= ASK_STAKES_AT:
        reasons.append(f"stakes {stakes:.2f} >= {ASK_STAKES_AT}")
    return reasons


def decide_ready(stakes: float, flags: dict[str, float], clear: float) -> dict:
    if clear < CLEAR_AT:
        action, why = "rewrite", f"unclear ({clear:.2f} < {CLEAR_AT})"
    elif reasons := high_stakes(stakes, flags):
        action, why = "ask", "; ".join(reasons)
    else:
        action, why = "release", f"clear ({clear:.2f}), stakes {stakes:.2f}, no risk flags"
    return {"action": action, "why": why, "stakes": round(stakes, 2), "clear": round(clear, 2),
            "flags": {k: round(v, 2) for k, v in flags.items()}}


def cmd_ready(args) -> dict:
    from typesafe_sdk import Noul

    text = read(args.text)
    questions = risk_questions("ready") | {"clear": Noul(
        instructions="Does `issue` say what to build and give observable acceptance criteria, so that two competent "
        "engineers working only from it and the codebase would build the same thing?"
    )}
    response = ask({"issue": text}, questions)
    stakes, flags = risks_of(response)
    return decide_ready(stakes, flags, response.nouls["clear"].noul) | {"text": text[:6_000]}


def cmd_escalate(args) -> dict:
    issue, question = read(args.text), read(args.question)
    response = ask({"issue": issue, "question": question}, risk_questions("escalate"))
    stakes, flags = risks_of(response)
    reasons = high_stakes(stakes, flags)
    return {"to": "user" if reasons else "steward", "why": "; ".join(reasons) or f"stakes {stakes:.2f}, no risk flags",
            "stakes": round(stakes, 2), "flags": {k: round(v, 2) for k, v in flags.items()}, "text": (issue + question)[:6_000]}


def cmd_duplicate(args) -> dict:
    from typesafe_sdk import Noul

    response = ask({"a": read(args.text), "b": read(args.other_text)}, {"same": Noul(
        instructions="Do `a` and `b` ask for the same change, so that building either one would make the other unnecessary?"
    )})
    p = response.nouls["same"].noul
    return {"other": args.other, "duplicate": p >= DUPLICATE_AT, "p": round(p, 2)}


# ---------- fresh ----------


def context_and_history(transcript: Path, prompts: int = 4) -> tuple[int, list[str]]:
    """Current context size (last assistant turn's input) and the last few prompts the session received."""
    tokens, history = 0, []
    for line in transcript.open():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        if entry.get("type") == "assistant" and (usage := message.get("usage")):
            tokens = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        elif entry.get("type") == "user" and isinstance(message.get("content"), str):
            history.append(message["content"][:600])
    return tokens, history[-prompts:]


def pane_tail(pane: str, lines: int = 60) -> str:
    out = subprocess.run(
        ["herdr", "agent", "read", pane, "--source", "recent-unwrapped", "--lines", str(lines)],
        capture_output=True, text=True,
    )
    return out.stdout[-6_000:]


def decide_fresh(role: str, tokens: int, related: float | None, struggling: float) -> dict:
    limits = CONTEXT[role]
    if tokens >= limits["hard"]:
        fresh, why = True, f"context {tokens:,} >= {limits['hard']:,}"
    elif struggling >= STRUGGLING_AT:
        fresh, why = True, f"recent output looks stuck ({struggling:.2f})"
    elif role == "builder" and related is not None and related < RELATED_AT:
        fresh, why = True, f"next step unrelated to its recent work ({related:.2f})"
    elif "soft" in limits and related is not None and related < RELATED_AT and tokens >= limits["soft"]:
        fresh, why = True, f"next step unrelated ({related:.2f}) and context {tokens:,} >= {limits['soft']:,}"
    else:
        fresh, why = False, f"keep: context {tokens:,}, related {related if related is None else round(related, 2)}"
    return {"fresh": fresh, "why": why, "tokens": tokens, "related": related, "struggling": round(struggling, 2)}


def cmd_fresh(args) -> dict:
    from typesafe_sdk import Noul

    session = panes.session(args.pane)
    if not session:
        sys.exit(json.dumps({"error": f"no Claude session in pane {args.pane}"}))
    tokens, history = context_and_history(session["transcript"]) if session["transcript"] else (0, [])
    if tokens < FRESH_FLOOR:
        return {"command": "fresh", "role": args.role, "pane": args.pane, "session": session["session_id"],
                "fresh": False, "why": f"keep: barely used ({tokens:,} tokens)", "tokens": tokens}
    state = {"recent_prompts": history, "recent_output": pane_tail(args.pane)}
    questions = {"struggling": Noul(
        instructions="Does `recent_output` show the agent repeating a failed fix, going in circles, "
        "contradicting its instructions, or losing track of the task?"
    )}
    # Relatedness only matters to roles with a SOFT limit.
    asks_related = bool(args.next) and "soft" in CONTEXT[args.role]
    if asks_related:
        state["next_step"] = read(args.next, 6_000)
        questions["related"] = Noul(
            instructions="Is `next_step` about the same feature and the same files as the work in `recent_prompts`?"
        )
    response = ask(state, questions)
    related = response.nouls["related"].noul if asks_related else None
    return {"command": "fresh", "role": args.role, "pane": args.pane, "session": session["session_id"]} | decide_fresh(
        args.role, tokens, related, response.nouls["struggling"].noul
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    gate = sub.add_parser("gate")
    gate.add_argument("--issue", required=True)
    gate.add_argument("--phase", choices=["plan", "diff"], required=True)
    gate.add_argument("--brief", required=True)
    gate.add_argument("--report")
    gate.add_argument("--previous-report")
    gate.add_argument("--files")
    fresh = sub.add_parser("fresh")
    fresh.add_argument("--issue", required=True)
    fresh.add_argument("--role", choices=list(CONTEXT), required=True)
    fresh.add_argument("--pane", required=True)
    fresh.add_argument("--next")
    p = sub.add_parser("ready")
    for flag in ("--issue", "--text"):
        p.add_argument(flag, required=True)
    p = sub.add_parser("escalate")
    for flag in ("--issue", "--text", "--question"):
        p.add_argument(flag, required=True)
    p = sub.add_parser("duplicate")
    for flag in ("--issue", "--other", "--text", "--other-text"):
        p.add_argument(flag, required=True)
    args = parser.parse_args()

    commands = {"gate": cmd_gate, "fresh": cmd_fresh, "ready": cmd_ready, "escalate": cmd_escalate, "duplicate": cmd_duplicate}
    start = time.perf_counter()
    result = {"id": uuid.uuid4().hex[:8], "issue": args.issue, "command": args.command}
    result |= commands[args.command](args)
    result["ms"] = round((time.perf_counter() - start) * 1000)
    crewlog.append("decision", **result)
    result.pop("brief", None)
    result.pop("text", None)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

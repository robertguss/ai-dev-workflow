#!/usr/bin/env python3
"""Which agent runs each crew role, and how to read its sessions.

The project's `## Crew` section (in CLAUDE.md or AGENTS.md) picks the runtime:

  Runtime: codex                  every role on Codex (default: the runtime of whoever starts the role)
  Runtime: codex oracle=claude    every role on Codex except the oracle
  Models: builder=gpt-6-luna:low  optional per-role model[:effort] overrides

Each runtime knows its Herdr agent kind, its launch arguments, how to find a running
session's file from its process, and how to read context size and token use from it.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

ROLES = ("steward", "driver", "builder", "oracle")
# The model and effort each role gets on each runtime, unless `Models:` overrides it.
DEFAULTS = {
    "claude": {"steward": ("opus", "high"), "driver": ("opus", "high"), "builder": ("sonnet", "medium"),
               "oracle": ("fable", "high")},
    "codex": {"steward": ("gpt-6-astra", "high"), "driver": ("gpt-6-astra", "high"), "builder": ("gpt-6.1-sol", "medium"),
              "oracle": ("gpt-6-astra", "xhigh")},
}
# Estimated $ per million tokens: (input, output, cache read); cache writes at 1.25x input. Matched by
# substring of the model name. A model without prices is logged with its tokens and no cost.
PRICES = {"opus": (4.0, 20.0, 0.20), "sonnet": (2.0, 10.0, 0.20), "fable": (10.0, 50.0, 0.25)}
# Tools the Claude builder and oracle never use; denying them keeps their definitions out of every call.
CLAUDE_UNUSED_TOOLS = ["--disallowedTools", "Artifact,Workflow,ScheduleWakeup,SendFeedback,ReportFindings"]


def _ts(stamp: str | None) -> datetime | None:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else None


def _lines(path: Path):
    for line in path.open():
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


class Claude:
    name = kind = "claude"

    def launch_args(self, role: str, model: str, effort: str) -> list[str]:
        return ["--model", model, "--effort", effort, *(CLAUDE_UNUSED_TOOLS if role in ("builder", "oracle") else [])]

    # Dropped from the caller's own launch command before reuse: they pick a model or resume old work.
    drop_with_value = {"--model", "--effort", "--resume", "-r", "--session-id", "--agent", "--advisor"}
    drop_flags = {"--continue", "-c", "--fork-session"}
    # Kept with the value that follows them (a bare word is otherwise taken for a prompt and dropped).
    keep_with_value = {"--permission-mode", "--settings", "--add-dir", "--mcp-config", "--allowedTools", "--allowed-tools"}

    def session(self, pid: int) -> dict:
        session_id = json.loads((Path.home() / f".claude/sessions/{pid}.json").read_text())["sessionId"]
        return {"session_id": session_id, "transcript": next(Path.home().glob(f".claude/projects/*/{session_id}.jsonl"), None)}

    def context(self, transcript: Path, prompts: int = 4) -> tuple[int, list[str], int | None]:
        """Current context size (the last turn's input), the last few prompts, and the window if known."""
        tokens, history = 0, []
        for entry in _lines(transcript):
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            if entry.get("type") == "assistant" and (usage := message.get("usage")):
                tokens = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            elif entry.get("type") == "user" and isinstance(message.get("content"), str):
                history.append(message["content"][:600])
        return tokens, history[-prompts:], None

    def usage_since(self, transcript: Path, since: datetime) -> dict:
        total, seen = Counter(), set()
        for entry in _lines(transcript):
            message = entry.get("message")
            if entry.get("type") != "assistant" or not isinstance(message, dict) or not message.get("usage"):
                continue
            # Claude Code writes one line per content block, each repeating its message's usage: count each once.
            if message_id := message.get("id"):
                if message_id in seen:
                    continue
                seen.add(message_id)
            if (stamp := _ts(entry.get("timestamp"))) and stamp < since:
                continue
            for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                total[key] += message["usage"].get(key) or 0
        return dict(total)


class Codex:
    name = kind = "codex"

    def launch_args(self, role: str, model: str, effort: str) -> list[str]:
        return ["-m", model, "-c", f'model_reasoning_effort="{effort}"']

    drop_with_value = {"-m", "--model", "-c", "--config", "-p", "--profile"}
    drop_flags: set[str] = set()
    keep_with_value = {"-a", "--ask-for-approval", "-s", "--sandbox", "--add-dir", "--enable", "--disable"}

    def session(self, pid: int) -> dict:
        """Codex holds its rollout file open; none exists before the first prompt."""
        out = subprocess.run(["lsof", "-p", str(pid), "-Fn"], capture_output=True, text=True).stdout
        rollout = next((Path(line[1:]) for line in out.splitlines()
                        if line.startswith("n") and re.search(r"/rollout-[^/]*\.jsonl$", line)), None)
        session_id = re.search(r"([0-9a-f]{8}-[0-9a-f-]{27})\.jsonl$", rollout.name).group(1) if rollout else f"codex-{pid}"
        return {"session_id": session_id, "transcript": rollout}

    def context(self, transcript: Path, prompts: int = 4) -> tuple[int, list[str], int | None]:
        tokens, window, history = 0, None, []
        for entry in _lines(transcript):
            payload = entry.get("payload") or {}
            if payload.get("type") == "token_count" and (info := payload.get("info")):
                tokens = info["last_token_usage"]["input_tokens"]
                window = info.get("model_context_window") or window
            elif entry.get("type") == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
                text = " ".join(c.get("text", "") for c in payload.get("content", []) if isinstance(c, dict))
                if not text.startswith(("# AGENTS.md", "<")):  # injected instructions and environment context
                    history.append(text[:600])
        return tokens, history[-prompts:], window

    def usage_since(self, transcript: Path, since: datetime) -> dict:
        """Token use since `since`, from the running totals Codex records with each turn."""
        before, last = None, None
        for entry in _lines(transcript):
            payload = entry.get("payload") or {}
            if payload.get("type") != "token_count" or not payload.get("info"):
                continue
            total = payload["info"]["total_token_usage"]
            if (stamp := _ts(entry.get("timestamp"))) and stamp < since:
                before = total
            last = total
        if not last:
            return {}
        delta = {k: (last.get(k) or 0) - ((before or {}).get(k) or 0) for k in ("input_tokens", "cached_input_tokens", "output_tokens")}
        return {"input_tokens": delta["input_tokens"] - delta["cached_input_tokens"], "output_tokens": delta["output_tokens"],
                "cache_read_input_tokens": delta["cached_input_tokens"], "cache_creation_input_tokens": 0}


RUNTIMES = {"claude": Claude(), "codex": Codex()}


def by_process(argv0: str):
    return RUNTIMES.get(Path(argv0).name)


def reusable_args(runtime, argv: list[str]) -> list[str]:
    """The caller's own settings (permission mode, sandbox) from its argv, without model, resume or prompt."""
    kept, skip, keep_next = [], False, False
    for arg in argv:
        if skip:
            skip = False
        elif keep_next:
            kept.append(arg)
            keep_next = False
        elif arg in runtime.drop_with_value:
            skip = True
        elif arg.split("=", 1)[0] in runtime.drop_with_value or arg in runtime.drop_flags or not arg.startswith("-"):
            continue
        else:
            kept.append(arg)
            keep_next = arg in runtime.keep_with_value
    return kept


def crew_config(root: str) -> dict[str, str]:
    """The `## Crew` section's fields, from CLAUDE.md or AGENTS.md at the repository root."""
    for name in ("CLAUDE.md", "AGENTS.md"):
        path = Path(root) / name
        if not path.exists():
            continue
        text = path.read_text()
        if (m := re.search(r"^## Crew\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)):
            fields = {}
            for line in m.group(1).splitlines():
                if (f := re.match(r"^\s*([A-Z][A-Za-z]*):\s*(.+?)\s*$", line)):
                    fields[f.group(1)] = f.group(2)
            return fields
    return {}


def for_role(role: str, root: str, default: str | None = None) -> tuple:
    """(runtime, model, effort) for a role in this project. Without a `Runtime:` default, a role runs on
    `default` (the caller's runtime: a crew started from Codex stays on Codex), else Claude Code."""
    fields = crew_config(root)
    words = fields.get("Runtime", "").split()
    name = next((w for w in words if "=" not in w), default or "claude")
    name = dict(w.split("=", 1) for w in words if "=" in w).get(role, name)
    model, effort = DEFAULTS[name][role]
    override = dict(w.split("=", 1) for w in fields.get("Models", "").split() if "=" in w).get(role)
    if override:
        model, _, chosen = override.partition(":")
        effort = chosen or effort
    return RUNTIMES[name], model, effort


def cost(model: str, u: dict) -> float | None:
    prices = next((p for key, p in PRICES.items() if key in model), None)
    if not prices:
        return None
    inp, out, cache_read = prices
    return round((
        u.get("input_tokens", 0) * inp
        + u.get("cache_creation_input_tokens", 0) * inp * 1.25
        + u.get("cache_read_input_tokens", 0) * cache_read
        + u.get("output_tokens", 0) * out
    ) / 1e6, 4)

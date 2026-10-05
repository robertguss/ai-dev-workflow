# Jev decisions

`scripts/jev.py` asks TypeSafe's Jev model a few typed questions and applies
cutoffs in code; the cutoffs and questions live at the top of `jev.py`, the one
place to read or change them. A call costs a fraction of a cent and under a
second. The key comes from `TYPESAFE_API_KEY`, else fnox (project config, then
`~/.config/fnox/config.toml`). When it exits with an error, tell the user, and
until it works send every review to the oracle, keep every pane, hold every
release in `Backlog`, and send every driver question to the user.

## gate: who reviews this step?

```bash
jev.py gate --issue <ID> --phase plan --brief <brief-file>
jev.py gate --issue <ID> --phase diff --brief <brief-file> --report <report-file> \
  [--previous-report <earlier-failed-report>] --files "<changed paths>"
```

Returns `send_to`: `oracle` or `self`, with `why`, `stakes` (0–2) and per-risk
`flags` (0–1): security, data, concurrency, money, contract, architecture, and
at diff review `stuck`. A high flag or high stakes sends the step to the oracle;
everything else you review yourself.

The gate reads only the brief, the changed paths and the reports. When the diff
touches something risky the brief never mentioned, say so in the report file you
pass, or send it to the oracle yourself.

## fresh: does this pane need a new session?

```bash
jev.py fresh --issue <ID> --role builder|oracle|driver|steward --pane <pane> [--next <next-brief-file>]
```

It reads the pane's Claude transcript for its context size and recent prompts,
and the pane's recent output. Returns `fresh: true|false` with `why`: a session
restarts when its context passes its role's hard limit, or when its recent
output looks stuck (repeating a failed fix, contradicting its instructions). A
builder or oracle also restarts when the next step is unrelated to its recent
work and it already carries a fair amount of context; the driver and steward
carry the whole project, so only their hard limit and the stuck check apply. A
session that has barely been used (under `FRESH_FLOOR` tokens) is kept without
asking Jev.

Run it at step boundaries, and mid-step only for a builder that has failed the
same way twice: reviewers keep their findings until the step commits.

A fresh builder or oracle: `panes.py restart <role>`. Mid-step, send the new
builder the brief, the open findings, and a note that the uncommitted changes
are its predecessor's work. A fresh driver: end the chunk. A fresh steward,
checked after each pass with `--issue -`: it replaces itself (steward.md).

## steward: release, escalate, duplicate

```bash
jev.py ready --issue <ID> --text <issue-file>
jev.py escalate --issue <ID> --text <issue-file> --question <question-file>
jev.py duplicate --issue <A> --other <B> --text <a-file> --other-text <b-file>
```

- `ready` returns `action`: `rewrite` when the issue is too unclear to build
  (`clear` under `CLEAR_AT`), else `ask` when it is high-stakes, else `release`.
- `escalate` returns `to`: `user` when the decision asked is high-stakes, else
  `steward`.
- `duplicate` returns `duplicate: true|false` with its probability `p`.

High-stakes means the gate's risk questions, asked about the issue or the
decision, scoring at `ASK_FLAG_AT` or `ASK_STAKES_AT`. Those start below the
gate's own cutoffs, so the user sees more at first; loosen them as the log shows
releases that went well.

## Spot checks

About one in ten steps the gate marks `self` go to the oracle anyway, with
`audit: true` and a `why` starting `spot check`. Treat them as ordinary oracle
reviews. They are the only way the log learns what the gate misses; the user can
turn them off with `CREW_AUDIT_RATE=0` or change the share.

## Tuning

Jev itself is not retrained; tuning changes what it is asked and where code
draws the lines. Work from `crewlog.py report`, with the user:

1. **Misses** (a spot check or a later bug found a P1/P2 on a step sent to
   `self`): read the logged brief. If no risk question fits it, add one to
   `RISKS` in `jev.py`; if one fits but scored low, sharpen its wording. If the
   brief never named the risk, fix the brief template instead.
2. **Waste** (oracle reviews that found nothing serious): look at which flag
   sent them. A flag that keeps firing on clean steps needs narrower wording or
   a higher cutoff.
3. **Cutoffs:** `crewlog.py replay --flag-at <F> --stakes-at <S>` shows which
   past decisions would change and whether any dropped review had real findings.
   Change `FLAG_AT` and `STAKES_AT` in `jev.py` only when replay shows no lost
   findings.
4. **Fresh sessions:** compare restarts with later `stuck` flags and the user's
   feedback; adjust the `CONTEXT` table in `jev.py`. For the driver, read the
   report's Chunks section: when a replaced driver's handoff overhead is large
   next to its steps' cost, or chunks run only a step or two, raise its hard
   limit.

5. **Releases and escalations:** the user's verdicts ("that needed me", "why was
   I asked this?") arrive as `crewlog.py feedback`; an escape on a step the
   steward released counts too. Raise `ASK_FLAG_AT` and `ASK_STAKES_AT` while
   the user is asked things they did not need to decide; lower them after a
   release that needed them.

Pin the model version (`MODEL` in `jev.py`) while tuning: a new Jev version
needs a fresh look at the cutoffs.

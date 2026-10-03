# Jev decisions

`scripts/jev.py` asks TypeSafe's Jev model a few typed questions and applies
cutoffs in code; the cutoffs and questions live at the top of `jev.py`, the one
place to read or change them. A call costs a fraction of a cent and under a
second. The key comes from `TYPESAFE_API_KEY`, else fnox (project config, then
`~/.config/fnox/config.toml`). When it exits with an error, tell the user, and
until it works send every review to the oracle and keep every pane.

## gate: who reviews this step?

```bash
jev.py gate --issue <ID> --phase plan --brief <brief-file>
jev.py gate --issue <ID> --phase diff --brief <brief-file> --report <report-file> \
  [--previous-report <earlier-failed-report>] --files "<changed paths>"
```

Returns `send_to`: `oracle` or `self`, with `why`, `stakes` (0–2) and per-risk
`flags` (0–1): security, data, concurrency, money, contract, architecture, and at
diff review `stuck`. A high flag or high stakes sends the step to the oracle;
everything else you review yourself.

The gate reads only the brief, the changed paths and the reports. When the diff
touches something risky the brief never mentioned, say so in the report file you
pass, or send it to the oracle yourself.

## fresh: does this pane need a new session?

```bash
jev.py fresh --issue <ID> --role builder|oracle|driver --pane <pane> [--next <next-brief-file>]
```

It reads the pane's Claude transcript for its context size and recent prompts,
and the pane's recent output. Returns `fresh: true|false` with `why`: a session
restarts when its context passes its role's limit, when its recent output looks
stuck (repeating a failed fix, contradicting its instructions), or when the next
step is unrelated to its recent work and it already carries a fair amount of
context.

Run it at step boundaries, and mid-step only for a builder that has failed the
same way twice: reviewers keep their findings until the step commits.

A fresh builder or oracle: `panes.py restart <role>`. Mid-step, send the new
builder the brief, the open findings, and a note that the uncommitted changes
are its predecessor's work. A fresh driver: end the chunk.

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
3. **Cutoffs:** `crewlog.py replay --flag-at <F> --stakes-at <S>` shows which past
   decisions would change and whether any dropped review had real findings.
   Change `FLAG_AT` and `STAKES_AT` in `jev.py` only when replay shows no lost
   findings.
4. **Fresh sessions:** compare restarts with later `stuck` flags and the user's
   feedback; adjust the `CONTEXT` table in `jev.py`.

Pin the model version (`MODEL` in `jev.py`) while tuning: a new Jev version
needs a fresh look at the cutoffs.


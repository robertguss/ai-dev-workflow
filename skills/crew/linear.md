# Linear

The project's instructions (`CLAUDE.md` or `AGENTS.md`) name the Linear team and
project; reach them through the Linear MCP tools. The steward and the drivers
write to Linear; the oracle and builder work from the repository and their
prompts.

## Ownership

The user wants to be involved as little as possible:

- **The user** gives intent (rough issues, or messages to the steward), answers
  `Needs Input` questions, and merges the release PR.
- **The steward** shapes issues, sets priority, scope and acceptance, finds
  dependencies and duplicates, releases issues to `Ready`, and answers drivers'
  questions that Jev does not send to the user.
- **A driver** owns the issue it claimed: its statuses from `Planning` to
  `Done`, its comments and its sub-issues.

## Statuses

| Status        | Meaning                                  | Set by                                              |
| ------------- | ---------------------------------------- | --------------------------------------------------- |
| `Backlog`     | Intent and discovered work, being shaped | user, steward; driver for discovered work           |
| `Ready`       | Released for building                    | steward; driver for sub-issues of a released parent |
| `Planning`    | Brief in plan review                     | driver                                              |
| `Building`    | Builder building or fixing               | driver                                              |
| `In Review`   | Diff in review (oracle or driver)        | driver                                              |
| `Needs Input` | Waiting on the user                      | steward                                             |
| `Done`        | Landed on the land branch                | driver                                              |

A split parent moves to `Building` when its first sub-issue starts and to `Done`
when its last sub-issue is done.

The label `oracle` on an issue forces an oracle review whatever Jev says. The
label `crew-N` marks the crew holding an issue.

If any of these statuses is missing from the team, tell the user which ones to
add and stop. Linear categories: `Ready` is Unstarted; `Planning`, `Building`,
`In Review` and `Needs Input` are Started.

## Pulling the queue

At each step boundary:

1. **Candidates.** `Ready` issues in the project, including sub-issues, that no
   crew holds.
2. **Order.** Priority: Urgent, High, Medium, Low, then none. Ties go to an
   issue you already started (a split parent's next sub-issue), then to the
   oldest. The latest priorities win over finishing started work: every
   committed step stands on its own.
3. **Fit.** Write the input for `scripts/parallel.py`: every issue a crew holds
   (a `crew-N` label, not `Done`, in any status, `Needs Input` included) as
   `active`, leaving out split parents, whose sub-issues stand for them; the
   candidates in order as `ready`; each with the paths under its `Footprint:`
   and its unfinished blockers. Run
   `parallel.py --input <file> --shared "<Shared globs>"` and take the first
   `compatible` issue.
4. **Claim** it: set `Planning` and add your crew's label (creating the label if
   missing). Re-read the issue and run `parallel.py` again, with it as the only
   `ready` entry and every other active issue as `active`. Another crew's label
   on it too: the lower crew number keeps it. A conflict with another crew's
   claim made meanwhile: the lower crew number keeps its issue, and the higher
   releases its own back to `Ready` without its label. Either way, if you let it
   go, pull again.
5. **Re-read** the claimed issue's description and comments; they may have
   changed since you last saw them.

Done when you hold one claimed issue to plan, or no candidate is compatible.

Without Linear there is one crew: take the next item from the user's
instructions or `HANDOFF.md`.

## Splitting

Once plan review agrees a split, create one sub-issue per step under the parent,
in `Ready`, with the parent's priority and a `Footprint:` for its step (the
issue template is in [steward.md](steward.md#the-issue-template)). Number the
titles in build order (`1/3 …`) and, where the tools allow, make each sub-issue
blocked by the one before it. The current step continues as the first sub-issue.

## Comments

Post on the step's issue (the sub-issue, or the issue itself when it has one
step). Write each so the user can read it without the chat.

Linear shows every agent comment under the user's own account, so each starts
with its author: `[steward]` or `[driver crew-N]`. A comment without a bracketed
author is the user's.

- **At `Building`:** the approved brief, headed `Brief (oracle-approved)` or
  `Brief (driver-reviewed; Jev: <why>)`.
- **At `Done`:** the landed commit SHA and branch, who reviewed (oracle or
  driver) with Jev's reason, the verdict and number of review rounds, each
  finding with its disposition (fixed, withdrawn on dispute, or filed as
  discovered work), and the verify results.

## Discovered work

Work found mid-step that lies outside the step's scope becomes a new issue in
`Backlog`: what you found, where (`file:line`), and why it matters, related to
the current issue. The steward shapes and releases it on its next pass.

## Escalation

Only high-stakes decisions reach the user; Jev decides which (jev.md).

- **A disputed oracle finding** is settled with the oracle (driver.md, triage).
- **A fix outside the step's scope** becomes discovered work.
- **An unclear acceptance criterion or a scope question** goes to the steward
  (driver.md, talking to the steward). It answers, or posts the question for the
  user and sets `Needs Input`. Then act by stage:
  - **Planning** (nothing built yet): remove your crew's label, leave the issue
    to the steward, and pull the next one.
  - **Building or review** (uncommitted work in the tree): keep your label and
    end your turn. The steward sends you the user's answer once they give it;
    restore the earlier status and continue.

Without Linear, ask the user in your pane and wait, at either stage.

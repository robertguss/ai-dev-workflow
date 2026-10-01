# Linear

The project's `AGENTS.md` names the Linear team and project; reach them through
the Linear MCP tools. You are the only agent that writes to Linear. The oracle
and worker work from the repository and your prompts.

## Ownership

The user owns priority, order, what is released to `Ready`, scope and acceptance
criteria. You own every status change after `Ready`, the comments, and
sub-issues. To suggest a priority or scope change, comment and tell the user;
the change itself is theirs.

## Statuses

| Status      | Meaning                                  | Set by                                                                          |
| ----------- | ---------------------------------------- | ------------------------------------------------------------------------------- |
| `Backlog`   | Ideas and discovered work; not buildable | user; driver for discovered work                                                |
| `Ready`     | Released for building                    | user; driver for sub-issues of a released parent and for answered parked issues |
| `Planning`  | Brief in plan review                     | driver                                                                          |
| `Building`  | Worker building or fixing                | driver                                                                          |
| `In Review` | Diff in oracle review                    | driver                                                                          |
| `Needs Input` | Waiting on the user                      | driver                                                                          |
| `Done`      | Committed                                | driver                                                                          |

A split parent moves to `Building` when its first sub-issue starts and to `Done`
when its last sub-issue is done.

If any of these statuses is missing from the team, tell the user which ones to
add and stop. Linear categories: `Ready` is Unstarted; `Planning`, `Building`,
`In Review` and `Needs Input` are Started.

## Pulling the queue

At each step boundary:

1. **Parked issues.** For each issue in `Needs Input`, look for a comment without
   the `[driver]` prefix newer than your question. Answered: move it to
   `Ready`; the answer is now part of its spec.
2. **Candidates.** `Ready` issues in the project, including sub-issues. Skip any
   blocked by an unfinished issue.
3. **Order.** Priority: Urgent, High, Medium, Low, then none. Ties go to an
   issue you already started (a split parent's next sub-issue), then to the
   oldest. The user's latest priorities win over finishing started work: every
   committed step stands on its own.
4. **Re-read** the chosen issue's description and comments; they may have
   changed since you last saw them.

Done when you hold one issue to plan, or the queue is empty.

## Splitting

Once plan review agrees a split, create one sub-issue per step under the parent,
in `Ready`, with the parent's priority. Number the titles in build order
(`1/3 …`) and, where the tools allow, make each sub-issue blocked by the one
before it. The current step continues as the first sub-issue.

## Comments

Post on the step's issue (the sub-issue, or the issue itself when it has one
step). Write each so the user can read it without the chat.

Linear shows your comments under the user's own account, so start every comment
you post with `[driver]`. A comment without that prefix is the user's.

- **At `Building`:** the approved brief, headed `Brief (oracle-approved)`.
- **At `Done`:** the commit SHA, the oracle's verdict and number of review
  rounds, each finding with its disposition (fixed, or escalated and the
  outcome), and the verify results.
- **At `Needs Input`:** the question, below.

## Discovered work

Work found mid-step that lies outside the step's scope becomes a new issue in
`Backlog`: what you found, where (`file:line`), and why it matters, related to
the current issue. It waits for the user to release it. Mention it to the user
in a line.

## Escalation

When only the user can decide (a disputed finding, an unclear acceptance
criterion, a scope question):

1. Comment on the issue: the question, the options with your recommendation, and
   what it blocks. Set `Needs Input`, and tell the user in your pane in a line or
   two.
2. Then act by stage:
   - **Planning** (nothing built yet): park it. Return to the queue and take the
     next issue; pulling picks up the answer.
   - **Building or review** (uncommitted work in the tree): wait. The user
     answers in Linear or in your pane. If your harness can wake you, check the
     issue for a reply every five minutes; otherwise end your turn, saying where
     to answer. Once answered, restore the earlier status and continue.

Without Linear, ask in your pane and wait, at either stage.

---
name: linear-migration
description:
  "Migrate a repository's planning (a ROADMAP, PLAN, HANDOFF queue or audit doc)
  into a Linear project for the crew loop: issues quoting their sources,
  statuses per the crew skill, an oracle review, then the message that switches
  the driver over. Use when the user asks to migrate, move or import a repo or
  project to Linear."
---

# Linear migration

You move one repository's open work into a new Linear project so its **driver**
(the `crew` skill's driver) can pull from it. Nothing in the repository changes:
the migration ends with a **switch-over issue** that the driver itself builds
through its reviewed loop.

Read the crew skill's `linear.md` first: its statuses, ownership rules and the
`[driver]` comment prefix are the contract every migrated issue must satisfy.

## Your workspace: local.md

The facts that differ per user live in `local.md` beside this file (keep it out
of version control; `local.example.md` is the template). Read it before anything
else. If it is missing, create it from the template: look up the team and status
IDs with read-only GraphQL queries, and ask the user for the rest. It holds:

- the Linear team (name, key, ID) and the ID of each crew status;
- where the Linear API key is read from;
- the user's name, for the switch-over's prose;
- the migrations log to append to, and a folder of past migration scripts to
  copy from, if the user keeps them;
- shell quirks and per-repository privacy tools.

## Fixed facts

- One Linear team; one project per repository.
- Write through the GraphQL API (`https://api.linear.app/graphql`, header
  `Authorization: <key>`, no "Bearer"). Read the key fresh from where `local.md`
  says on every run (a shell's environment can hold a stale, revoked key). Never
  print it. The Linear MCP tools are fine for spot-check reads.
- Every comment you post starts with `[driver]`: Linear shows it under the
  user's account, and the driver treats any unprefixed comment as the user's
  reply.
- [template.py](template.py) is a starting point for the migration script:
  quoting helpers, a dry run, creation that saves the id map after every issue,
  and a verifier. Adapt it; past migrations in the user's examples folder (from
  `local.md`) are better starting points when one is close.

## Steps

1. **Locate and wait.** Find the repository and its Herdr tab
   (`herdr agent list`, match `cwd`). Read the driver's pane
   (`herdr agent read <pane> --source recent-unwrapped --lines 400`). Migrate
   only while the driver and oracle are both idle; if either is working, wait
   (poll until both have stayed idle across two checks a minute apart). Done
   when both are idle and `git status` is clean.
2. **Find where the plan lives.** It differs per repository: a ROADMAP, a PLAN,
   the HANDOFF's remaining-work and open-questions sections, an audit doc, the
   driver's pane and its scratch files (signed-off briefs can exist only in a
   session scratch folder or an ignored evidence folder). Inventory every open
   task or step, every open question, every rule that still binds future work
   (with its later amendments), and every owner answer given in chat but not yet
   in git. Done when each inventory item has a source location (`file:line` at
   HEAD, or the pane capture).
3. **Settle what only the user can decide**, one question per message, with a
   recommendation: how far to move (usually a **full move**: the old plan frozen
   as history, binding rules kept), and, when a chunk is in flight, whether to
   migrate now or after it. Derive everything else from the sources and the crew
   skill.
4. **Write the script** (`--dry` prints the plan; the real run refuses if the
   project exists and writes the id map). Then dry-run and check: every cited
   range printed and read against its source, with no quote starting or ending
   mid-sentence; unique issue keys; and the private-data scan (below). Done when
   the dry run shows the intended issues and every range is correct.
5. **Run, then verify against Linear**: each issue's title, status, parent,
   milestone, priority and relations, and its full description (compare letters
   and digits only, after the auto-link normalisation below). Done at zero
   mismatches.
6. **Oracle review.** Send a self-contained prompt to an oracle (the crew's
   oracle pane, or any reviewing agent told
   `Use the crew skill. Your role: oracle.`; ask the user which pane if unsure):
   phase `diff`, read-only access rules, the script, id map and sources, the
   choices to judge, and anything you got wrong and fixed. Triage as the crew's
   driver does; fix, re-verify, `re-review` until sign-off; apply P3s without
   another round. Anything you change after sign-off (the hand-over message, the
   log) goes back for review too. Done at sign-off.
7. **Hand over.** Add a row to the migrations log, if the user keeps one. Give
   the user the message for the running driver's pane (re-read `linear.md`, take
   the switch-over issue first, plus anything in flight), or, with no crew
   running, the message that starts the steward before `CLAUDE.md` names Linear:
   `/crew Your role: steward. Linear: team <KEY>, project <name>.` The
   switch-over issue then adds the `## Crew` section for good. Add anything they
   must do in Linear, under a "What I need from you" heading.

## Statuses and relations

- **Backlog** is the default: the crew's steward shapes migrated work and
  releases it to Ready on its next pass.
- **The switch-over issue** ("Move planning from <source> to Linear") is Ready
  at High priority, or Needs Input with a `[driver]` "resume" question when the
  user has told the driver to hold. Its acceptance: a `## Crew` section in the
  root `CLAUDE.md` (`Linear: team <KEY>, project <name>`); the old plan frozen
  with a banner; binding rules kept, with every pointer to them (including code
  comments) moved if they move; every statement naming the old plan as the queue
  or authority reconciled (grep for it, inside the handoff too); the handoff's
  chunk contract (stopping point, required checks) preserved; the user's
  chat-only answers recorded. Out of scope: changing any rule's meaning, app
  code.
- **Work in flight** mirrors reality: the chunk's parent Building once a step
  has started, finished steps Done (with the commit), a step waiting on the user
  in Needs Input. A signed-off but unbuilt step is Ready, with its brief on the
  issue. The switch-over blocks the next in-flight step whenever that step's
  plan edits the old planning file.
- **Ready only what the user already released**, such as signed-off steps;
  everything else waits for the steward. Agreeing an order is not a release
  while they have said hold. Enforce an agreed order with sequential `blocks`
  relations, not creation order.
- **Every Needs Input issue gets a dated `[driver]` question comment**: the
  question, options, a recommendation, what it blocks. The driver detects the
  answer as a newer unprefixed comment.
- **Relations only where a source states them.** Check every
  "Dependencies:"-style line in the sources against the relations you create,
  both ways: a missing one and an invented one are both errors. A source's "or"
  is not a blocker: when either of two paths closes an item, say so in the issue
  instead of making one path block it.

## Descriptions

- Quote sources verbatim as blockquotes, headed by a link to the exact lines at
  the commit (`<repo>/blob/<sha>/<path>#L<a>-L<b>`). Prefer a pushed commit
  where the file is identical. Quote the owner's answers from the pane with
  their time.
- Put each binding constraint, correction or decision on **every issue it
  governs**: a driver reads only the issue it picks and its comments. That
  includes closing and release rules, authorizations, tool boundaries (what a
  browser check may request), and definitions a later step depends on (split a
  brief and the later step still needs the earlier step's definitions).
- Split a list of separate ideas into one issue each, each quoting the whole
  list item. Never use a parent with sub-issues for undecided ideas: releasing a
  parent authorizes all its children.
- Linear mangles tables inside lists and quotes: render table rows as labelled
  list items (`- **Column:** value`), one per line.
- Nothing private leaves the repository: no personal names or record IDs from
  registers or scratch notes (replace them and say so in the quote's header),
  and no secret values. Run the repository's privacy scanner if it has one, and
  check every value in its secrets files (`.env`, `fnox.toml` and the like)
  against all outgoing text.

## Pitfalls already hit

- Pane captures carry UI glyphs (`⏺`, `⎿`, `❯` input echoes, odd spacing): strip
  them with a regex and re-check the output.
- Parsing numbered points out of a message: stop before the next numbered list
  (a "suggested order" list once replaced corrections 1–4). Verify by each
  point's expected opening words, never against the text you just wrote.
- Two issues sharing a script key: the id map keeps the second, and relations
  land on the wrong issue. Keep keys unique; assert it.
- A milestone `sortOrder` of 0 is ignored: number them 1..n.
- Linear auto-links bare domains when it saves a description (`example.com`
  becomes `[example.com](<http://example.com>)`). Collapse such a link before
  comparing only when its target equals its label.
- Linear can fail mid-run with a non-JSON 5xx, and a failed create may still
  have landed. Save the id map after every issue. Retry reads freely, but never
  retry a create or relation blindly: on an ambiguous write, stop, list the
  project's issues (and relations) on the server, and create only what is
  missing.
- Markdown formatters reflow fenced blocks tagged `markdown`: a two-line
  `## Crew` example became one line. Tag such examples `text`.
- Disclose your own mistakes in the re-review prompt; the oracle checks the fix
  more carefully when told.

---
name: linear-migration
description:
  "Migrate a repository's planning, open questions and binding rules into Linear
  with source-backed issues, preserved workflow semantics and verified relations.
  Use when the user asks to migrate, move or import a repo or project to Linear."
---

# Linear migration

Move the requested repository's open work into Linear. Preserve its current
scope, approval gates, workflow states and source evidence. A migration does not
authorize implementation or delivery of the imported work. It runs in the current
session and does not depend on a separate development skill or terminal app.

## Workspace facts

Read `local.md` beside this file when present; keep it out of version control.
[local.example.md](local.example.md) describes optional workspace facts. Discover
missing team, project and state IDs through available Linear tools. Do not invent
a workflow or rename states to fit a generic process. Use stable UUIDs for writes
and verification; human issue identifiers are display labels.

Prefer connected Linear tools. [template.py](template.py) supports larger scripted
imports, a dry run, saved creation IDs and verification. Use a direct API only
when needed and authorized; obtain credentials from the configured source without
printing them. On an ambiguous write, read the server before retrying a create.

## Migration

1. Read the repository instructions, current handoff, Git state and live Linear
   project. Preserve peer work and avoid a migration that competes with an active
   edit of the planning source. Resolve any actual conflict with the owner.
2. Inventory open tasks, questions, binding rules and later amendments. Record
   each source location at a specific commit, or attributable owner message.
   Include signed-off briefs and retained evidence where available. Distinguish
   approved work from proposals, deferred work and owner holds.
3. Resolve only missing owner choices that materially affect the migration;
   honor existing authorization. Prepare the issues, full source quotations,
   source-to-target state mapping, parent links, dependencies and milestones.
4. Dry-run the import. Read every cited range against its source, retain complete
   sentences, check unique script keys and scan all outgoing text for private data.
5. Import and verify the full descriptions, status UUIDs, labels, parents,
   milestones, priorities and relations against Linear. Audit status history when
   reconciling or moving existing issues. List ordering does not establish a dependency.
6. Follow any independent review requirements in the project's current instructions.
   Fix discrepancies and verify the final saved state. Report review and empirical
   verification separately; do not claim independent review when none occurred.
7. Record the migration and give the user the project and next eligible issue.
   Where repository reconciliation is needed, track a switch-over issue for the
   existing queue pointers, historical-plan banner and preserved binding rules.
   Do not prescribe a role configuration or send another session a message without
   the user's authorization.

## Statuses and relations

- Preserve source workflow semantics. Read the actual team's state names, UUIDs
  and types, including distinctions such as Todo versus Ready. Map source work
  according to its approved meaning; do not silently convert all unstarted work
  to an implementation-ready state.
- Work in flight mirrors reality: implementation started, candidate awaiting
  delivery, decision blocked, or confirmed completion. Record completion evidence
  and the applicable integration meaning; code existing is not sufficient.
- A signed-off but unbuilt proposal remains subject to its owner release/hold.
  Importing it, agreeing an order or creating a parent does not authorize children.
- Keep actual unanswered questions explicit, with what each blocks and the
  available recommendation. Preserve identifiable author provenance for agent
  comments; an unprefixed comment is not automatically an owner's answer.
- Create relations only where supported by a source. Check both missing and
  invented blockers. An alternative path ("A or B") is described as an alternative,
  not encoded as two mandatory blockers.

## Descriptions and privacy

- Quote sources verbatim with links to exact lines at the source commit. Prefer
  a pushed commit where the file is identical. Attribute owner answers with time
  and scope; do not turn an agent's recommendation into an owner's decision.
- Put each governing constraint on every issue it affects: release rules, scope,
  authorizations, tool boundaries and definitions. A later step must be readable
  without the preceding agent's conversation.
- Split separate ideas into separate issues. Preserve a whole source list item
  when quoting it. Avoid a parent that accidentally implies approval of undecided work.
- Linear may mangle tables in lists/quotes, and literal pipes inside cells can
  truncate columns. Use labeled list items and verify every original field.
- Keep private names, student/record identifiers and secret values out of outgoing
  text. Redact private source quotations transparently. Use the repository's
  privacy checks and inspect provenance; automated scans alone are insufficient.

## Verification pitfalls

- Keep creation keys unique and save IDs after every successful create. A failed
  request may still have landed; never retry creation or relations blindly.
- A milestone sortOrder of 0 may be ignored; use an explicit supported order.
- Linear auto-links bare domains. Normalize only when the target equals the label
  before comparing full saved descriptions with the source.
- Source captures can contain UI glyphs and echoed input. Remove display artifacts
  and recheck each quotation rather than accepting a regex extraction unchecked.
- A numbered list extraction must stop before the next unrelated numbered list.
  Verify expected source openings, not only the text generated by the script.
- Use `text` for literal configuration examples; Markdown formatters may reflow
  a fenced block tagged `markdown`.

# AI development skills

Reusable skills for source-backed project coordination.

## Available skill

| Skill | Purpose |
| --- | --- |
| [linear-migration](skills/linear-migration/SKILL.md) | Move repository planning into Linear while preserving source evidence, workflow semantics and approval gates. |

## Install

Link the remaining skill into the skill directory used by your coding app. For
Codex, for example:

```sh
mkdir -p ~/.codex/skills
ln -s "$PWD/skills/linear-migration" ~/.codex/skills/linear-migration
```

The optional [local facts template](skills/linear-migration/local.example.md)
records workspace-specific team/state IDs and credential locations. Keep a filled
`local.md` out of Git. Use available connected Linear tools where possible.

## Retirement

Robert retired the Crew skill and its workflow on 2026-10-06. Its role documents,
Herdr operations and scripts have been removed. Project work follows the current
session's authorization and each project's independent engineering, review,
delivery and owner gates. Git history retains the prior workflow as evidence;
those historical instructions do not govern new work.

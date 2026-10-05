---
name: crew
description:
  "Herdr build crews on Claude Code or Codex: a steward keeps the Linear board
  and starts crews, each a driver, builder and oracle, with Jev gating reviews,
  releases and fresh sessions. Use when the user runs /crew, asks for the crew
  skill, or a prompt names your crew role."
---

# Crew

With Linear, one **steward** runs in the user's checkout and starts up to
`Crews:` crews, each in its own git worktree and Herdr workspace. Without
Linear, a single crew runs in the user's checkout. Each role runs on Claude Code
or Codex, as the project's `Runtime:` line says (`scripts/runtimes.py`). Every
crew has this layout:

```
+-----------------+-----------------+
|                 |     oracle      |
|     driver      +-----------------+
|                 |     builder     |
+-----------------+-----------------+
```

Your prompt names your role. Read that role's file and follow only it:

- `Your role: steward` → [steward.md](steward.md)
- `Your role: driver` → [driver.md](driver.md)
- `Your role: builder` → [builder.md](builder.md)
- `Your role: oracle` → [oracle.md](oracle.md)
- anything else, including `/crew`: when the `## Crew` section of the project's
  `CLAUDE.md` or `AGENTS.md` has a `Linear:` line, [steward.md](steward.md);
  otherwise [driver.md](driver.md).

The role lasts the whole session.

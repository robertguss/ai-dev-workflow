---
name: crew
description:
  "Three-pane Herdr build crew: Opus driver, Sonnet builder, Fable oracle, with
  Jev gating reviews and fresh sessions. Use when the user runs /crew, or a
  prompt names your crew role."
---

# Crew

Three Claude Code sessions share one Herdr tab, always in this layout:

```
+-----------------+-----------------+
|                 |  oracle (Fable) |
|  driver (Opus)  +-----------------+
|                 | builder (Sonnet)|
+-----------------+-----------------+
```

Your prompt names your role. Read that role's file and follow only it:

- `Your role: builder` → [builder.md](builder.md)
- `Your role: oracle` → [oracle.md](oracle.md)
- anything else, including `/crew` → [driver.md](driver.md)

The role lasts the whole session.

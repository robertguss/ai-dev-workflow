# linear-migration: local facts

Copy this file to `local.md` beside `SKILL.md` and fill it in. Keep `local.md`
out of version control. The skill reads it before anything else.

## Linear

- Team: **<team name>**, key `<KEY>`, id `<team uuid>`.
- State mapping: list the actual team's state names, types and stable UUIDs.
  Preserve source meanings, including any distinct Todo/Ready states; do not
  create or rename states to fit a development workflow.
- API key: read it from
  `<where, e.g. "~/.zshrc, the line starting export LINEAR_API_KEY=">`.

Find the ids with a read-only query:

```text
query { teams { nodes { id key name states { nodes { id name type } } } } }
```

## You

- Name, for the switch-over's prose: `<name>`.
- Migrations log to append a row to: `<path, or "none">`.
- Past migration scripts to copy from: `<folder, or "none">`.

## Shell and tools

- Shell quirks scripts must avoid: `<e.g. "ls is aliased; use /bin/ls">`.
- Privacy scanners per repository: `<repo: command, or "none">`.
- Secrets files whose values must never appear in Linear:
  `<e.g. .env, fnox.toml>`.

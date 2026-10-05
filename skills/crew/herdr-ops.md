# Herdr operations

`scripts/panes.py` owns each crew's layout: every change to the crew's panes
goes through it, and a fresh session restarts in place, so the layout holds.
`scripts/crews.py` owns the crews themselves: the steward starts each in its own
worktree and Herdr workspace, and stops it. Agents are named from their tab ID,
lowercased with `:` turned to `-`: tab `wF:t1` gives `driver-wf-t1`,
`oracle-wf-t1`, `builder-wf-t1`, and the steward's tab gives `steward-<tab>`.
Address the steward by that name, since a replacement steward takes it over;
target every other command by pane ID.

- `panes.py setup`: creates whatever is missing and prints the three pane IDs.
- `panes.py check`: `layout_ok`, or the problems. Run it after anything odd.
- `panes.py restart oracle|builder`: stops the pane's agent session and starts a
  fresh one in the same pane, on the role's runtime, model and effort
  (`scripts/runtimes.py`), plus your own permission settings when you run the
  same runtime.
- `panes.py args driver|steward`: the Herdr agent kind and arguments for a
  replacement session.

## Sending a prompt

Write the prompt to a file in your scratch directory, then send it:

```bash
herdr agent prompt <pane> "$(cat "$PROMPT_FILE")" --wait --timeout 580000
```

Always go through a file: shell quoting and backticks inside a double-quoted
string break or execute. Keep your tool's own timeout above the `--timeout`
value.

A build often outlasts one wait. If `--wait` times out while the agent is
`working`, keep waiting with `herdr agent wait <pane> --timeout 580000`. If it
times out in any other state, the prompt may still have been delivered: check
`herdr agent get <pane>` before sending anything again.

If an agent is `blocked`, read its pane and ask the user; its approval dialogs
are the user's to answer.

## Reading the reply

```bash
herdr agent read <pane> --source recent-unwrapped --lines 200
```

The reply follows the echoed first line of your prompt. The oracle's starts with
`Verdict:`; the builder's report starts with `Status:`. If the read is cut off,
re-read with more lines; if the reply still is not recoverable, ask the agent to
write it to a file and reply with the path, then read that file.

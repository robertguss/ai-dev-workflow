# Herdr operations

Target every command by pane ID. Name agents from your tab ID with `:` turned to
`-`: tab `w7:t1` gives `worker-w7-t1`, `oracle-w7-t1`, `driver-w7-t1`.

## Sending a prompt

Write the prompt to a file in your scratch directory, then send it to the oracle
or the worker:

```bash
herdr agent prompt <pane> "$(cat "$PROMPT_FILE")" --wait --timeout 580000
```

Always go through a file: shell quoting and backticks inside a double-quoted
string break or execute. Keep your tool's own timeout above the `--timeout`
value.

A worker's build often outlasts one wait. If `--wait` times out while the agent
is `working`, keep waiting with `herdr agent wait <pane> --timeout 580000`. If
it times out in any other state, the prompt may still have been delivered: check
`herdr agent get <pane>` before sending anything again.

If an agent is `blocked`, read its pane and ask the user; its approval dialogs
are the user's to answer.

## Reading the reply

```bash
herdr agent read <pane> --source recent-unwrapped --lines 200
```

The reply follows the echoed first line of your prompt. The oracle's starts with
`Verdict:`; the worker's report starts with `Status:`. If the read is cut off,
re-read with more lines; if the reply still is not recoverable, ask the agent to
write it to a file and reply with the path, then read that file.

## Starting the worker

At the start of each step's build:

```bash
herdr pane split <oracle-pane> --direction down --cwd "$PWD" --no-focus
herdr agent start worker-<tab> --kind <kind> --pane <new-pane> -- <worker args>
```

Take the new pane ID from `.result.pane.pane_id`, and the kind and arguments
from the worker configuration. Then send `Use the worker skill.` followed by the
approved brief.

Done when the worker has the brief and is `working`.

## Closing the worker

After the step's commit, close its pane: `herdr pane close <worker-pane>`.

A worker that loses the thread mid-step (repeating a failed fix, contradicting
its brief) can be replaced: close it, start a fresh one, and send the brief, the
open findings, and a note that the uncommitted changes are its predecessor's
work.

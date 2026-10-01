# End of chunk

Run these in order once the chunk's last step is committed and its worker
closed. Each step's completion criterion must hold before the next begins.

## 1. Write HANDOFF.md

Create or entirely replace `HANDOFF.md` at the repository root. Write it for a
fresh driver and a fresh oracle who have only the repository, Linear and this
file. Linear holds the backlog, priorities, briefs, review outcomes and the
user's answers, so the handoff points at it rather than restating it. Everything
essential still held only in this chat goes in. Carry forward from the old
handoff every item still unresolved.

Use these sections, writing "none" where one is empty:

1. **State**: a dated observation of the repository, branch, "reviewed through
   `<SHA>`" and "pushed through `<SHA>`" (a committed handoff cannot name its
   own commit). The fresh agents re-check HEAD, the working tree and the remote.
2. **Queue**: the Linear team and project, then a dated snapshot of what a fresh
   driver resumes: split issues with sub-issues left, and parked issues with
   their questions.
3. **Read these first**: the sources of truth, pointed at rather than restated.
4. **Context**: why the work is shaped this way; only what links alone would
   lose.
5. **This chunk**: each commit with its issue identifier. Mark which results the
   oracle checked independently and which are only driver-reported; the detail
   stays in each issue's completion comment.
6. **Decisions and authorizations in force**: those not recorded on a Linear
   issue, and the scope each covers.
7. **Operational state**: the worker configuration when `AGENTS.md` lacks it,
   running jobs or processes, retained evidence directories, cleanup obligations
   and their owner, anything unsafe to repeat.
8. **Conventions and gotchas**: hard-won facts the repository does not confess.
   Name roles (driver, oracle, worker), never pane IDs.
9. **Skills**: required first (`driver` for the driver, `oracle` for the
   oracle), then optional.

Without Linear, the handoff carries the queue itself: add **Remaining work**
(the backlog, in order), **Next chunk** (`proposed` or `approved`, its
acceptance condition and first action) and **Open questions for the user** (each
naming what it blocks).

Done when every section is filled or says "none".

## 2. Handoff review

Send the uncommitted `HANDOFF.md` for a `handoff` review. Triage and re-review
as in the step loop until no P1/P2 finding remains. You make these edits
yourself: `HANDOFF.md` is yours, not the worker's.

Done when the oracle signs off on the final text.

## 3. Commit

Commit `HANDOFF.md` with a message that records the oracle's sign-off, and push
per the project's conventions. Confirm the working tree is clean.

## Launch commands

Steps 4 and 5 relaunch an agent from the command Herdr reports for its pane:
`herdr pane process-info --pane <pane>`, taking the foreground process whose
argv starts with the agent's executable. Always pass `--pane` explicitly;
without it Herdr reports the focused pane, which may belong to another project.

Keep the configuration arguments (permission mode, model, profile) and drop
everything that selects or restarts old work: subcommands like `resume` or
`fork`, flags such as `--continue`, `--resume`, `--fork-session` or
`--session-id`, and any positional prompt. Pass the kept arguments after `--`,
one argv element each. Name the restarted agents as in
[herdr-ops.md](herdr-ops.md).

## 4. Restart the oracle

1. Record the oracle's pane ID, kind (from `herdr agent list`) and cleaned
   launch command.
2. Send `herdr agent send-keys <oracle-pane> ctrl+c`, then check
   `herdr pane process-info --pane <oracle-pane>`. Repeat the keypress and check
   at most four times, switching to `ctrl+d` after two, and stop as soon as the
   shell is in the foreground. If it still is not, tell the user and stop.
3. Start it again in the same pane:
   ```bash
   herdr agent start oracle-<tab> --kind <kind> --pane <oracle-pane> -- <kept arguments>
   ```

Done when `herdr agent get <oracle-pane>` reports `idle` or `done`.

## 5. Start the new driver

1. Record your own kind and cleaned launch command the same way
   (`--pane "$HERDR_PANE_ID"`).
2. Split below yourself, free your name, and start the replacement:
   ```bash
   herdr pane split --current --direction down --cwd "$PWD" --no-focus
   herdr agent rename "$HERDR_PANE_ID" --clear
   herdr agent start driver-<tab> --kind <kind> --pane <new-pane> -- <kept arguments>
   ```
3. **Bootstrap.** Send through a prompt file, with `--wait`:
   `Use the driver skill. You are the replacement driver for pane <your pane ID>. The oracle is pane <oracle pane ID>. Read HANDOFF.md and verify the checkout, then reply READY or list each discrepancy. Do not close anything or start work yet.`
   Read its reply. If it is not `READY`, tell the user and stop, leaving both
   drivers in place.
4. **Takeover.** Tell the user the replacement is ready and is taking over. Then
   send, without `--wait`, as your last action:
   `Takeover: close pane <your pane ID>, tell the user you have taken over, then continue with the queue.`
   The replacement closes this pane and reports the takeover itself.

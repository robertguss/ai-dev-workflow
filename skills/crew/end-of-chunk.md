# End of chunk

Run these in order once the chunk's last step is committed. Each step's
completion criterion must hold before the next begins.

## 1. Write HANDOFF.md

Create or entirely replace `HANDOFF.md` at the repository root. Write it for a
fresh driver, oracle and builder who have only the repository, Linear and this
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
5. **This chunk**: each commit with its issue identifier and who reviewed it
   (oracle, or driver on Jev's call). Mark which results were checked
   independently and which are only driver-reported; the detail stays in each
   issue's completion comment.
6. **Decisions and authorizations in force**: those not recorded on a Linear
   issue, and the scope each covers.
7. **Operational state**: running jobs or processes, retained evidence
   directories, cleanup obligations and their owner, anything unsafe to repeat.
8. **Conventions and gotchas**: hard-won facts the repository does not confess.
   Name roles (driver, oracle, builder), never pane IDs.
9. **Skills**: `crew` for every role, then optional ones.

Without Linear, the handoff carries the queue itself: add **Remaining work**
(the backlog, in order), **Next chunk** (`proposed` or `approved`, its
acceptance condition and first action) and **Open questions for the user** (each
naming what it blocks).

Done when every section is filled or says "none".

## 2. Handoff review

If any step this chunk went to the oracle, send the uncommitted `HANDOFF.md` for
a `handoff` review, and triage and re-review until no P1/P2 finding remains.
Otherwise check it yourself against oracle.md's `handoff` checklist. You make
these edits yourself: `HANDOFF.md` is yours, not the builder's.

Done when the reviewer signs off on the final text.

## 3. Commit

Commit `HANDOFF.md` with a message that records the sign-off and who gave it,
and push per the project's conventions. Confirm the working tree is clean.

## 4. Restart the oracle and builder

Run `panes.py restart oracle` and `panes.py restart builder`, so the next driver
starts with fresh sessions in the same panes. Done when both report `layout_ok`.

## 5. Start the new driver

1. Read your own launch command:
   `herdr pane process-info --pane "$HERDR_PANE_ID"`, taking the foreground
   process whose argv starts with `claude`. Keep the configuration arguments
   (permission mode) and drop everything that selects or restarts old work
   (`resume`, `--continue`, `--resume`, `--fork-session`, `--session-id`, any
   positional prompt). Make sure `--model opus --effort high` is in the kept
   list.
2. Split below yourself, free your name, and start the replacement:
   ```bash
   herdr pane split --current --direction down --cwd "$PWD" --no-focus
   herdr agent rename "$HERDR_PANE_ID" --clear
   herdr agent start driver-<tab> --kind claude --pane <new-pane> -- <kept arguments>
   ```
   The split is temporary: once you close, the new driver fills the left half.
3. **Bootstrap.** Send through a prompt file, with `--wait`:
   `Use the crew skill. You are the replacement driver for pane <your pane ID>. The oracle is pane <oracle pane ID> and the builder is pane <builder pane ID>. Read HANDOFF.md and verify the checkout, then reply READY or list each discrepancy, and wait for the takeover message.`
   Read its reply. If it is not `READY`, tell the user and stop, leaving both
   drivers in place.
4. **Takeover.** Tell the user the replacement is ready and is taking over. Then
   send, without `--wait`, as your last action:
   `Takeover: close pane <your pane ID>, run panes.py check, tell the user you have taken over, then continue with the queue.`
   The replacement closes this pane and reports the takeover itself.

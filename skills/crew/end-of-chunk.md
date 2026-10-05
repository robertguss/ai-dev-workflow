# End of chunk

A chunk ends one of three ways:

- **Retire**, with Linear, when no issue remains that this crew can take: the
  crew closes, and the steward starts crews again when work allows.
- **Replace**, when Jev says a fresh driver is due or the user asks: a new
  driver continues this crew.
- **Stop**, without Linear, when the queue is empty: Replace steps 1 to 3 and 5,
  logged with `--ending retire`; then tell the user the queue is done, and start
  no new driver.

Run the matching steps in order once the chunk's last step has landed. Each
step's completion criterion must hold before the next begins.

## Retire

1. **Leave nothing behind.** The working tree is clean and
   `git log origin/<land>..HEAD` is empty. Whatever this chat still holds that a
   later crew needs (a decision, a gotcha, a half-understood failure) goes on
   the relevant Linear issue as a `[driver crew-N]` comment, or into `Backlog`
   as discovered work. Done when the repository and Linear hold everything.
2. **Log** the chunk:
   `crewlog.py chunk --crew <crew> --steps <steps landed this chunk> --ending retire`.
3. **Hand back.** As your last action, send the steward `retiring <crew>`,
   without `--wait`. The steward closes this crew's workspace, which ends this
   session.

## Replace

### 1. Write the handoff

Create or entirely replace the handoff: `.crew/handoff.md` in your worktree with
Linear (untracked: `.crew/` is excluded from git), `HANDOFF.md` at the
repository root without. Write it for a fresh driver, oracle and builder who
have only the repository, Linear and this file. Linear holds the backlog,
priorities, briefs, review outcomes and the user's answers, so the handoff
points at it rather than restating it. Everything essential still held only in
this chat goes in. Carry forward from the old handoff every item still
unresolved.

Use these sections, writing "none" where one is empty:

1. **State**: a dated observation of the repository, branch, "reviewed through
   `<SHA>`" and "landed through `<SHA>`" (a committed handoff cannot name its
   own commit). The fresh agents re-check HEAD, the working tree and the remote.
2. **Queue**: the Linear team and project, then a dated snapshot of what a fresh
   driver resumes: the issue this crew holds, if any, and a split issue's
   sub-issues left.
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
   Name roles (steward, driver, oracle, builder), never pane IDs.
9. **Skills**: `crew` for every role, then optional ones.

Without Linear, the handoff carries the queue itself: add **Remaining work**
(the backlog, in order), **Next chunk** (`proposed` or `approved`, its
acceptance condition and first action) and **Open questions for the user** (each
naming what it blocks).

Done when every section is filled or says "none".

### 2. Handoff review

If any step this chunk went to the oracle, send the handoff for a `handoff`
review, and triage and re-review until no P1/P2 finding remains. Otherwise check
it yourself against oracle.md's `handoff` checklist. You make these edits
yourself: the handoff is yours, not the builder's.

Done when the reviewer signs off on the final text.

### 3. Commit (without Linear only)

Commit `HANDOFF.md` with a message that records the sign-off and who gave it,
and push per the project's conventions. Confirm the working tree is clean. With
Linear the handoff stays untracked, so nothing lands for it.

### 4. Restart the oracle and builder

Run `panes.py restart oracle` and `panes.py restart builder`, so the next driver
starts with fresh sessions in the same panes. Done when both report `layout_ok`.

### 5. Log the chunk

`crewlog.py chunk --crew <crew, or solo> --steps <steps landed this chunk> --ending replace`.
With Linear, send the steward `chunk <crew>`, without `--wait`.

### 6. Start the new driver

1. `panes.py args driver` gives the new session's arguments: your own permission
   mode, with the driver's model and effort.
2. Split below yourself, free your name, and start the replacement:
   ```bash
   herdr pane split --current --direction down --cwd "$PWD" --no-focus
   herdr agent rename "$HERDR_PANE_ID" --clear
   herdr agent start driver-<tab> --kind claude --pane <new-pane> -- <args>
   ```
   The split is temporary: once you close, the new driver fills the left half.
3. **Bootstrap.** Send through a prompt file, with `--wait`:
   `Use the crew skill. Your role: driver. You are the replacement driver for pane <your pane ID>. The oracle is pane <oracle pane ID> and the builder is pane <builder pane ID>.`
   followed, with Linear, by your own prompt's crew, worktree, land branch and
   steward, then:
   `Read the handoff and verify the checkout, then reply READY or list each discrepancy, and wait for the takeover message.`
   Read its reply. If it is not `READY`, tell the user and stop, leaving both
   drivers in place.
4. **Takeover.** Tell the user the replacement is ready and is taking over. Then
   send, without `--wait`, as your last action:
   `Takeover: close pane <your pane ID>, run panes.py check, tell the user you have taken over, then continue with the queue.`
   The replacement closes this pane and reports the takeover itself.

# Modes

A project runs one mode, for every task, until someone edits it.

| Mode | Adds |
|---|---|
| `standard` | Nothing. The workflow in `WORKFLOW.md`, as written. |
| `tracker` | One tracking record per non-trivial task, committed under `.lean/tracker/`. |
| `full` | The tracking record, and a claimed queue item before work starts. |

Modes only add steps. Contracts, tests, review depth, and the Quality Gate are the same in all
three: no mode lowers a floor, and `full` is not a licence to skip `standard`.

## Choosing it once

The value lives in the mode block of `.lean/PROJECT.md`, which upgrades never touch.
`.lean/bin/mode.sh get` reads it; `.lean/bin/mode.sh set <mode>` records it.

- Unset, and the first task of the session is about to change a file: ask the user which mode, in
  one question, offering the three above with what each adds. Record the answer, then continue the
  task in that mode.
- Recorded: follow it. Do not ask again, do not offer to switch, and do not change the value because
  a task would be tidier in another mode.
- The user changes modes by editing that block. Do it for them only when they ask for the change.
- Unreadable or not one of the three: ask rather than guess. A wrong guess silently drops the
  records or the queue the project asked for.

## tracker

One record per Task Contract, in `.lean/tracker/`, named `<YYYY-MM-DD>-<slug>.md`. Trivial tasks
(see `WORKFLOW.md`) need none. `.lean/bin/tracker.sh` owns the header, you write the sections:

```sh
.lean/bin/tracker.sh new "<title>" --contract "<contract line>"   # prints the record path
.lean/bin/tracker.sh set <record> queue <item id>                 # in full mode
.lean/bin/tracker.sh current                                      # the record still IN_PROGRESS
.lean/bin/tracker.sh state <record> <DONE|BLOCKED|FAILED>         # at the Quality Gate
```

- Open it when you write the contract line, with the contract and `state: IN_PROGRESS`.
- Close it at the Quality Gate with the Result Contract from `CONTRACTS.md`, and commit it with the
  change it describes. The state you set is the status you report; they cannot disagree.
- It is the Result Contract on disk. Record what the diff cannot say -- why, what was ruled out,
  what is unverified -- not a second copy of the diff.
- A record is found by path, file name, or slug, so a later session can close what an earlier one
  opened.

```
# <title>
state: IN_PROGRESS | DONE | BLOCKED | FAILED
contract: risk=<...> quality=<...> acceptance=<...>
started: <YYYY-MM-DD>
queue: <item id, or - outside full mode>

## Changes
## Evidence
## Not verified
## Follow-ups
```

A `BLOCKED` or `FAILED` record stays as it is. Closing it as `DONE` without the gate's evidence is
the same violation as claiming DONE in chat.

## full

Everything `tracker` does, and work is claimed before it starts. `.lean/bin/queue.sh`:

```sh
.lean/bin/queue.sh list             # open items first, then claimed, then done
.lean/bin/queue.sh add <title>      # prints the new item id
.lean/bin/queue.sh claim <id>       # exit 3: someone else holds it
.lean/bin/queue.sh done <id>        # at the Quality Gate
.lean/bin/queue.sh release <id>     # stopping without finishing
```

- Claim before the first change, and name the item id in the tracking record's `queue:` field
  (`tracker.sh new --queue <id>`, or `tracker.sh set <record> queue <id>`).
- Exit 3 is the item's own answer -- held by someone else, not claimed, already done: take another
  item, and never edit the item file to take it anyway. Exit 4 is not an answer about the item: the
  queue branch kept moving under the write, nothing was decided, and the same command can be run
  again. Exit 1 is a usage or argument error.
- The queue never writes to a branch that is checked out, and it refuses rather than commit onto your
  work. Item ids are lowercase slugs; `add` derives one from the title.
- A task the user hands you directly is still work: `add` it, then claim it, so a second session
  does not start the same thing.
- Release what you will not finish. An abandoned claim blocks the item for everyone.

Items live on their own branch, one file per item, and a claim is a push to that branch: the first
push wins and the loser is told who holds the item. So the protocol holds across sessions, machines,
and CI, and never touches the working tree. Without an `origin` remote it degrades to local-only
claims, which coordinate nothing outside the checkout.

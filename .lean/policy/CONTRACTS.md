# Contracts

## Task Contract

Default form is one line, written first, before any file change:

```
Contract: risk=MEDIUM quality=STANDARD acceptance=go test ./... passes and printf 'a' | tally prints 1 1 1
```

Trivial tasks: `Contract: trivial (<reason>)`.

The same contract may be written as a block: `Contract:` alone, then one `field: value` per line in this order, ending at a blank line. `risk`, `quality` and `acceptance` are required; `topic` (a short slug), `budget` and `skill` (such as `lean-grill:high`) are optional. The block's canonical form is the one-line contract above, which receipts and `--contract` use. Model and effort are not typed: hooks record what the runtime reports.

```
Contract:
topic: tally-unicode
risk: MEDIUM
quality: STANDARD
budget: BALANCED
acceptance: go test ./... passes and printf 'a' | tally prints 1 1 1
```

Write the contract first in the reply. In Claude, the PreToolUse guard binds it from that first text of the reply to the latest person prompt (read from the transcript), so no extra command is needed. A contract written later in the reply, in an earlier turn or by a subagent does not count. When the guard cannot read it (Codex, or no readable transcript) it denies with this hint; then declare the same contract as a command of its own. The declaration does not replace the written contract:

```sh
python3 .lean/scripts/contract_guard.py declare <<'EOF'
Contract:
risk: MEDIUM
quality: STANDARD
acceptance: go test ./... passes
EOF
python3 .lean/scripts/contract_guard.py declare --contract 'Contract: trivial (typo in README)'
```

The Claude and Codex PreToolUse hooks bind the contract to the session (subagents share it) and deny edit tools and shell commands that write until one exists: a redirection to anything but `/dev/null`, `/dev/stdout`, `/dev/stderr` or `/dev/tty`; `cp`, `mv`, `rm`, `mkdir`, `tee`, `chmod` and the other file writers; `sed`/`perl` in place; `find -delete`/`-exec`; `sort -o`; Git subcommands that change state and `git -c`; interpreter code that opens a file for writing; Lean scripts that change records or settings; a shell reading commands from stdin (`bash <<EOF`, `... | sh`, `bash -s`), `sudo`, `npx`, `make`, the install subcommands of `npm`, `pnpm`, `yarn`, `pip`, `uv`, `cargo`, `go`, `brew` and `python -m pip`, `docker` commands other than listing ones, downloads to a file (`curl -o`, `wget`) and archive extraction or creation (`tar x`, `tar c`, `unzip`); unparseable text, a backtick, or a command named by an expansion (`eval "$cmd"`, `$tool x`). Runners (`eval`, `sh -c`, `exec`, `xargs`, `env`, `nice`, `time`) are judged by the command they run. Every other tool and shell command, including reads, `cd`, `echo`, loops, `$(...)` reads, `workflow.py show|check|context`, test runs and the gate runner, runs without a contract. The check is a best-effort pattern over the parsed command, not a security boundary: an unlisted tool, interpreter or script, a write hidden in a heredoc body fed to anything but a shell, or a path hidden behind `cd` is not caught, a quoted `>` reads as a redirection, and the Stop gate still refuses changed work that has no contract. A new user prompt clears it. Run outside a hook, `declare` only validates. Use a quoted heredoc or single-quoted `--contract`: the guard accepts no shell expansion or chained command in a declaration.

The line is the whole contract at every risk and quality level. The fields below define what it means; write them out only if the user asks:

- **Goal** — what must be true when finished.
- **Scope** — files/areas in and out.
- **Quality** — `STANDARD | HIGH | VERY_HIGH`.
- **Budget** — `CHEAP | BALANCED | EXPENSIVE`.
- **Risk** — `LOW | MEDIUM | HIGH`.
- **Acceptance** — observable checks that prove completion.

Quality and budget are independent. Budget never lowers quality.

## Defaults

Do not ask the user for these values. Use the defaults, infer risk, and state the result in one line. The user may override any value at any time.

- **Quality** — `STANDARD`, unless the user asks for more or risk is `HIGH` (then at least `HIGH`).
- **Budget** — `BALANCED`.
- **Risk** — inferred:
  - `HIGH` — auth, permissions, payments, secrets, data deletion or migration, security boundaries, public API contracts, anything hard to reverse. Also any area listed under High-risk areas in `.lean/PROJECT.md`; the gate requires a HIGH review receipt when a change touches a backticked path or glob (no spaces) listed there.
  - `MEDIUM` — behavior changes in shared code, multi-file refactors, dependency changes, configuration that affects runtime.
  - `LOW` — docs, comments, tests only, isolated local changes.
- When unsure between two levels, choose the higher one.

## Result Contract

Scale the report to the task. A trivial task needs one line.

- **Status** — `DONE | BLOCKED | FAILED`.
- **Changes** — what changed and where.
- **Evidence** — commands run and their outcomes, tests added/run, which review round the change is on, and the range that review covered against the range that ships.
- **Not verified** — anything skipped, with reason.
- **Follow-ups** — remaining work, if any.

## Review Contract

- **Verdict** — `PASS | REWORK`.
- **Findings** — location, problem, severity, suggested fix.
- **Scope** — what was and was not reviewed.

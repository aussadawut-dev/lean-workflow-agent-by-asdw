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

The Claude and Codex PreToolUse hooks bind the contract to the session (subagents share it) and deny shell, edit and unknown tools until one exists; read-only tools and plain shell reads (`grep`, `cat`, `head`, `tail`, `wc`, `ls` and read-only `git` subcommands, alone or piped, with no redirection, chaining or expansion) stay available. A new user prompt clears it. Run outside a hook, `declare` only validates. Use a quoted heredoc or single-quoted `--contract`: the guard accepts no shell expansion or chained command in a declaration.

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

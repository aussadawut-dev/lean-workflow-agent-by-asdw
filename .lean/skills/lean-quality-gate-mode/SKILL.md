---
name: lean-quality-gate-mode
description: Inspect or set shared Claude/Codex gate automation (auto|manual). Does not waive validation or authorize a gate run.
user-invocable: true
argument-hint: "[auto|manual]"
---

Apply `.lean/policy/SKILL-EFFORT.md`. Run `python3 .lean/scripts/gate_mode.py` from the workflow root for read-only inspection. For an explicit user request to set `auto` or `manual`, pass that single literal argument to the script; never execute arbitrary invocation text as shell code. Reuse an already approved setting request rather than asking again. Report mode and whether a saved preference exists.

The optional project-owned `.codex/quality-gate.json` controls both providers at workspace level, including the selected application target. It is not a native runtime setting. Missing settings mean auto; invalid settings report NOT_RUN rather than silently changing policy. Do not import another project's preference or write global/runtime trust settings.

In manual mode, automatic Stops skip the full gate and report NOT_RUN. Obtain applicable user authorization before an explicit full run, reusing matching workset/batch approval. Deferred checks never count as a pass; keep VALIDATING/BLOCKED until current acceptance, gate and required review are satisfied. Direct shared runner calls and `python3 .codex/hooks/quality_gate.py run` remain explicit validation entry points; `CLAUDE_GATE_FORCE=1 .claude/hooks/quality-gate.sh` forces the Claude adapter.

Mode changes are protected gate-control changes. Inspect control drift and record only matching already-given approval through the existing `gate_evidence.py accept-controls` procedure, or let an independent HIGH-depth PASS review cover the change; do not use a toggle to approve unrelated hook or gate edits. Use exact contract/review flags for HIGH work. See [runtime guidance](../../policy/QUALITY.md). This command changes automation policy, not acceptance, review, publication or permissions.

$ARGUMENTS

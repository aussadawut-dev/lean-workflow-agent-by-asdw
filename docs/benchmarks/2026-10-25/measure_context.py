#!/usr/bin/env python3
"""Compare fixed Lean context profiles offline; never call a model or run an app.

Requires the optional local measurement tool tiktoken (not a Lean dependency).
Run from any directory with --baseline <commit>; JSON is written to stdout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import tiktoken


ROOT = Path(__file__).resolve().parents[3]
PRIOR = ROOT / "docs/benchmarks/2026-10-23"
MAINTENANCE = (
    ".codex/hooks/quality_gate.py",
    ".lean/scripts/contract_guard.py",
    ".lean/scripts/gate_evidence.py",
    ".lean/scripts/quality-gate.sh",
    ".lean/scripts/submodule.py",
)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="commit before this change")
    args = parser.parse_args()
    revision = git("rev-parse", "--verify", args.baseline + "^{commit}").strip()
    historical = json.loads((PRIOR / "context-tokens.json").read_text())
    worker = json.loads((PRIOR / "worker-context-tokens.json").read_text())
    output = {
        "measurement": "Offline sum of per-file text tokens, not actual model usage or billing.",
        "baseline_revision": revision,
        "tiktoken_version": tiktoken.__version__,
        "historical_source": "docs/benchmarks/2026-10-23/context-tokens.json",
        "worker_source": "docs/benchmarks/2026-10-23/worker-context-tokens.json",
        "worker_application_revision": worker["application_revision"],
        "limits": [
            "Excludes system/runtime prompts, wrappers, tool traffic, retries, output and cache billing.",
            "Fixed profiles are comparable input inventories, not required reads for every task.",
            "Worker application/brief tokens reuse the pinned prior artifact; no app or model was run.",
            "Historical deployment count 0 means the feature was absent in v4.7.0, not free deployment.",
            "Maintenance source profile counts full files; focused range reads can cost less.",
            "No causal claim about actual token savings, agent correctness or application speed.",
        ],
        "encodings": {},
        "current_file_sha256": {},
    }
    for encoding in ("o200k_base", "cl100k_base"):
        encoder = tiktoken.get_encoding(encoding)

        def count(text):
            return len(encoder.encode(text, disallowed_special=()))

        def profile(names, current):
            rows = []
            for name in names:
                text = (ROOT / name).read_text() if current else git("show", revision + ":" + name)
                rows.append({"path": name, "tokens": count(text)})
                if current:
                    output["current_file_sha256"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            return {"tokens": sum(row["tokens"] for row in rows), "files": rows}

        prior_profiles = historical["encodings"][encoding]["current-dirty"]
        result = {}
        for label in ("startup-required", "task-fixed-read-set", "deployment-optional"):
            names = [row["path"] for row in prior_profiles[label]["files"]]
            before, after = profile(names, False), profile(names, True)
            result[label] = {
                "historical_4_7_0_tokens": historical["encodings"][encoding]["v4.7.0"][label]["tokens"],
                "historical_2026_10_23_tokens": prior_profiles[label]["tokens"],
                "before_tokens": before["tokens"],
                "after_tokens": after["tokens"],
                "delta_tokens": after["tokens"] - before["tokens"],
                "files": [{"path": old["path"], "before_tokens": old["tokens"], "after_tokens": new["tokens"]}
                          for old, new in zip(before["files"], after["files"])],
            }
        before, after = profile(MAINTENANCE, False), profile(MAINTENANCE, True)
        result["gate-maintenance-source-inventory"] = {
            "before_tokens": before["tokens"],
            "after_tokens": after["tokens"],
            "files": [{"path": old["path"], "before_tokens": old["tokens"], "after_tokens": new["tokens"]}
                      for old, new in zip(before["files"], after["files"])],
        }
        # Recount the complete skill. Keep the prior bounded excerpt historical:
        # its exact whitespace selection was not retained in that artifact.
        skill = ".lean/skills/lean-agents/SKILL.md"
        old_skill, new_skill = git("show", revision + ":" + skill), (ROOT / skill).read_text()
        old_worker = worker["encodings"][encoding]["current-dirty"]
        source_tokens = old_worker["handoff-and-app-source-only"]
        old_start = result["startup-required"]["before_tokens"]
        new_start = result["startup-required"]["after_tokens"]
        result["worker-pinned-scenario"] = {
            "source_tokens_reused": source_tokens,
            "historical_bounded": old_worker["fresh-worker-bounded-instructions"]["tokens"],
            "historical_full_skill": old_worker["fresh-worker-full-delegation-skill"]["tokens"],
            "full_skill_before": source_tokens + old_start + count(old_skill),
            "full_skill_after": source_tokens + new_start + count(new_skill),
            "delegation_skill_unchanged": old_skill == new_skill,
            "bounded_method": "Historical count only; prior excerpt whitespace not retained for recounting.",
        }
        output["encodings"][encoding] = result
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

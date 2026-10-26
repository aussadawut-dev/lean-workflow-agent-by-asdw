#!/usr/bin/env python3
"""Compare static context inventories of Lean 4.17.0 and 5.0.0 offline.

Uses the 2026-10-25 method: sum of per-file text tokens for fixed file lists.
Requires the local measurement tool tiktoken (not a Lean dependency).
v4 files come from git tag v4.17.0; v5 files from the working tree (tracked files).
JSON goes to stdout.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[3]
ENCODINGS = ("o200k_base", "cl100k_base")

# Same file lists as the retained 4.17 method (docs/benchmarks/2026-10-25).
STARTUP = [("AGENTS.md", "AGENTS.md"), (".lean/README.md", ".lean/README.md")]
TASK = STARTUP + [
    (f".lean/skills/{s}/SKILL.md", f".lean/skills/{s}/SKILL.md")
    for s in ("lean-task", "lean-scope", "lean-review", "lean-gate")
] + [(f".lean/policy/{p}.md", f".lean/policy/{p}.md")
     for p in ("CONTEXT", "CONTRACTS", "TESTING", "REVIEW", "QUALITY")]
# (v4.17 path, v5 path, note). Mapping is by role; modules are not 1:1 ports.
GATE = [
    (".codex/hooks/quality_gate.py", ".lean/lean/hooks.py", "Codex/Claude lifecycle adapter -> unified hook dispatcher"),
    (".lean/scripts/contract_guard.py", ".lean/lean/guard.py", "contract guard"),
    (".lean/scripts/gate_evidence.py", ".lean/lean/evidence.py", "gate evidence"),
    (".lean/scripts/quality-gate.sh", ".lean/lean/gate.py", "quality gate runner (shell -> Python)"),
    (".lean/scripts/submodule.py", ".lean/lean/target.py", "submodule/target context"),
]
PROJECT_OWNED = {".lean/PROJECT.md", ".lean/config.json", ".lean/skill-effort.json"}
WORKFLOW_ROOTS = (".lean/", ".claude/", ".codex/", ".agents/")
WORKFLOW_FILES = {"AGENTS.md", "CLAUDE.md"}


def git(*args, raw=False):
    out = subprocess.check_output(["git", "-C", str(ROOT), *args])
    return out if raw else out.decode()


class Side:
    def __init__(self, label, ref):
        self.label, self.ref = label, ref  # ref None -> working tree

    def text(self, path):
        if self.ref:
            return git("show", f"{self.ref}:{path}")
        return (ROOT / path).read_text()

    def files(self):
        """Tracked non-symlink workflow-owned files."""
        if self.ref:
            rows = git("ls-tree", "-r", self.ref).splitlines()
        else:
            rows = git("ls-files", "-s").splitlines()
        out = []
        for row in rows:
            meta, path = row.split("\t", 1)
            if meta.split()[0] == "120000" or "__pycache__" in path:
                continue
            if (path in WORKFLOW_FILES or path.startswith(WORKFLOW_ROOTS)) and path not in PROJECT_OWNED:
                if not self.ref and not (ROOT / path).is_file():
                    continue
                out.append(path)
        return sorted(out)


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return m.group(0) if m else ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v4", default="v4.17.0", help="4.x ref to compare (default: the retained v4.17.0 run)")
    args = parser.parse_args()
    v4 = Side(args.v4.lstrip("v"), args.v4)
    v5 = Side("5.0.0", None)
    head = git("rev-parse", "HEAD").strip()
    dirty = git("status", "--porcelain", "--untracked-files=no").strip() != ""
    out = {
        "measurement": "Offline sum of per-file text tokens, not actual model usage or billing.",
        "tiktoken_version": tiktoken.__version__,
        "versions": {
            v4.label: {"ref": args.v4, "commit": git("rev-parse", f"{args.v4}^{{commit}}").strip()},
            "5.0.0": {"ref": "working tree on feat/refactor-v4", "head_commit": head,
                      "tracked_files_modified_vs_head": dirty},
        },
        "file_mapping": {
            "startup": [{"v4": a, "v5": b} for a, b in STARTUP],
            "task-fixed-read-set": [{"v4": a, "v5": b} for a, b in TASK],
            "gate-source": [{"v4": a, "v5": b, "note": n} for a, b, n in GATE],
            "no_v5_equivalent": [".lean/skills/lean-playbook/SKILL.md (4.17 deployment-optional; not in either fixed set)"],
            "v5_only_gate_modules": "other .lean/lean/*.py modules are listed under gate-all-v5-modules",
        },
        "limits": [
            "Static inventories only: exclude system/runtime prompts, tool traffic, retries, model output and cache billing.",
            "Fixed sets are comparable input inventories, not required reads for every task.",
            "Gate source counts full files; focused range reads can cost less.",
            "No causal claim about actual token, cost or speed savings, or agent correctness.",
        ],
        "encodings": {},
        "workflow_owned_files": {},
    }
    for name, side in ((v4.label, v4), ("5.0.0", v5)):
        paths = side.files()
        lines = sum(len(side.text(p).splitlines()) for p in paths)
        notest = [p for p in paths if not p.startswith(".lean/tests/")]
        out["workflow_owned_files"][name] = {
            "files": len(paths), "lines": lines,
            "files_excluding_tests": len(notest),
            "lines_excluding_tests": sum(len(side.text(p).splitlines()) for p in notest),
            "definition": "tracked non-symlink files under .lean/ .claude/ .codex/ .agents/ plus AGENTS.md, CLAUDE.md; excludes project-owned PROJECT.md, config.json, skill-effort.json",
        }
    for enc in ENCODINGS:
        e = tiktoken.get_encoding(enc)

        def count(t):
            return len(e.encode(t, disallowed_special=()))

        def inv(pairs):
            rows = [{"v4_path": a, "v5_path": b,
                     "v4_tokens": count(v4.text(a)), "v5_tokens": count(v5.text(b))} for a, b in pairs]
            return rows

        def summ(rows, extra=None):
            a, b = sum(r["v4_tokens"] for r in rows), sum(r["v5_tokens"] for r in rows)
            d = {"v4_tokens": a, "v5_tokens": b, "delta_tokens": b - a,
                 "delta_percent": round((b - a) / a * 100, 1) if a else None, "files": rows}
            d.update(extra or {})
            return d

        r = {}
        r["startup-required"] = summ(inv(STARTUP))
        r["task-fixed-read-set"] = summ(inv(TASK))
        r["gate-source-inventory"] = summ(inv([(a, b) for a, b, _ in GATE]))
        # v5 gate: every module of the lean package (v4 equivalent is the 17 scripts + 2 hooks).
        v5mods = sorted(p for p in v5.files() if re.fullmatch(r"\.lean/lean/[^/]+\.py", p))
        v4scripts = sorted(p for p in v4.files() if re.fullmatch(r"\.lean/scripts/[^/]+", p)
                           or p in (".codex/hooks/quality_gate.py",) or p.startswith(".claude/hooks/"))
        a = sum(count(v4.text(p)) for p in v4scripts)
        b = sum(count(v5.text(p)) for p in v5mods)
        r["all-executable-source"] = {
            "v4_files": len(v4scripts), "v5_files": len(v5mods), "v4_tokens": a, "v5_tokens": b,
            "delta_tokens": b - a, "delta_percent": round((b - a) / a * 100, 1),
            "v4_paths": v4scripts, "v5_paths": v5mods,
            "note": "supplementary: all v4 scripts/hooks vs all v5 lean package modules",
        }
        # Supplementary: skill discovery metadata (YAML frontmatter of every skill).
        sk4 = sorted(p for p in v4.files() if re.fullmatch(r"\.lean/skills/[^/]+/SKILL\.md", p))
        sk5 = sorted(p for p in v5.files() if re.fullmatch(r"\.lean/skills/[^/]+/SKILL\.md", p))
        a = sum(count(frontmatter(v4.text(p))) for p in sk4)
        b = sum(count(frontmatter(v5.text(p))) for p in sk5)
        r["skill-metadata-supplementary"] = {
            "v4_skills": len(sk4), "v5_skills": len(sk5), "v4_tokens": a, "v5_tokens": b,
            "delta_tokens": b - a, "delta_percent": round((b - a) / a * 100, 1),
            "note": "frontmatter of all skills; the 4.17 retained method did not count it; v4 default discovery exposes 9 core skills, 18 with optional pack",
        }
        out["encodings"][enc] = r
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

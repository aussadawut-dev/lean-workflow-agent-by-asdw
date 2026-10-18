#!/usr/bin/env python3
"""Aggregate retained, sanitized Lean eval run artifacts into a reproducible report.

Offline and free: this script never starts claude or codex and never reads prices. Cost appears
only where the runtime reported it. Two subcommands:

  extract  turn one harness result (report.json from run_evals.py, plus optionally the raw
           <case>#<n>.jsonl session saved next to it) into sanitized per-run artifacts
  report   aggregate a directory of artifacts into a table or JSON, one row per arm

Artifact schema: evals/measurements/README.md. Standard library only (Python 3.9+).
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "lean-measure/1"
ARM_KINDS = ("template", "local-settings")
OUTCOMES = ("correct", "false_success", "incorrect", "blocked")
META_FIELDS = ("provider", "model", "runtime", "revision")
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,79}$")
CLAIM = re.compile(r"\bDONE\b|all tests pass|\b(?:completed?|fixed|finished)\b", re.I)
TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


class MeasureError(Exception):
    pass


# --- artifact validation -------------------------------------------------------------------------

def _num(value, name, integer=False, allow_none=True):
    if value is None and allow_none:
        return None
    ok = isinstance(value, int) if integer else isinstance(value, (int, float))
    if isinstance(value, bool) or not ok or value < 0:
        raise MeasureError(f"{name} must be a non-negative {'integer' if integer else 'number'}, got {value!r}")
    return value


def _safe(value, name):
    if not isinstance(value, str) or not SAFE.match(value):
        raise MeasureError(f"{name} must match {SAFE.pattern}, got {value!r}")
    return value


def validate(artifact):
    """Return a normalized artifact containing only whitelisted, safe fields, or raise."""
    if not isinstance(artifact, dict) or artifact.get("schema") != SCHEMA:
        raise MeasureError(f"not a {SCHEMA} artifact")
    arm, meta = artifact.get("arm"), artifact.get("meta")
    if not isinstance(arm, dict) or arm.get("kind") not in ARM_KINDS:
        raise MeasureError(f"arm.kind must be one of {ARM_KINDS}")
    if not isinstance(meta, dict):
        raise MeasureError("meta must be an object")
    if artifact.get("outcome") not in OUTCOMES:
        raise MeasureError(f"outcome must be one of {OUTCOMES}")
    return {
        "schema": SCHEMA,
        "synthetic": bool(artifact.get("synthetic", False)),
        "case": _safe(artifact.get("case"), "case"),
        "run": _num(artifact.get("run"), "run", integer=True, allow_none=False),
        "arm": {"name": _safe(arm.get("name"), "arm.name"), "kind": arm["kind"]},
        "meta": {field: _safe(meta.get(field), f"meta.{field}") for field in META_FIELDS},
        "outcome": artifact["outcome"],
        "tokens": _num(artifact.get("tokens"), "tokens", integer=True),
        "cost_usd": _num(artifact.get("cost_usd"), "cost_usd"),
        "seconds": _num(artifact.get("seconds"), "seconds"),
        "tool_turns": _num(artifact.get("tool_turns"), "tool_turns", integer=True),
        "user_exchanges": _num(artifact.get("user_exchanges"), "user_exchanges", integer=True),
    }


def load_artifacts(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise MeasureError(f"not a directory: {directory}")
    artifacts = []
    for path in sorted(directory.rglob("*.json")):
        try:
            data = json.loads(path.read_text())
        except ValueError as error:
            raise MeasureError(f"{path}: invalid JSON ({error})")
        if isinstance(data, dict) and data.get("schema") != SCHEMA:
            continue  # e.g. a raw run_evals report.json kept alongside; not an artifact
        try:
            artifacts.append(validate(data))
        except MeasureError as error:
            raise MeasureError(f"{path}: {error}")
    return artifacts


# --- report --------------------------------------------------------------------------------------

def group_key(artifact, group_by):
    key = [artifact["arm"]["kind"], artifact["arm"]["name"]]
    key += [artifact["meta"][field] for field in group_by]
    return tuple(key)


def aggregate(artifacts, group_by=()):
    """One summary per arm (plus any --group-by metadata). Refuses to merge differing metadata."""
    unknown = [field for field in group_by if field not in META_FIELDS]
    if unknown:
        raise MeasureError(f"--group-by accepts {', '.join(META_FIELDS)}; got {', '.join(unknown)}")
    groups = {}
    for artifact in artifacts:
        groups.setdefault(group_key(artifact, group_by), []).append(artifact)
    rows = []
    for key in sorted(groups):
        runs = groups[key]
        meta = {}
        for field in META_FIELDS:
            values = sorted({run["meta"][field] for run in runs})
            if len(values) > 1:
                raise MeasureError(
                    f"arm {key[1]!r} ({key[0]}) mixes {field} values {values}; "
                    f"separate them with --group-by {field} or remove the odd runs")
            meta[field] = values[0]
        count = len(runs)
        counts = {outcome: sum(1 for run in runs if run["outcome"] == outcome) for outcome in OUTCOMES}

        def stat(field):
            values = [run[field] for run in runs if run[field] is not None]
            return {"runs_reporting": len(values), "total": sum(values) if values else None,
                    "mean": round(sum(values) / len(values), 4) if values else None}
        rows.append({
            "arm": key[1], "arm_kind": key[0], **meta, "runs": count,
            "synthetic": any(run["synthetic"] for run in runs),
            "correct": counts["correct"], "false_success": counts["false_success"],
            "incorrect": counts["incorrect"], "blocked": counts["blocked"],
            "correct_rate": round(counts["correct"] / count, 4),
            "tokens": stat("tokens"), "cost_usd": stat("cost_usd"), "seconds": stat("seconds"),
            "tool_turns": stat("tool_turns"), "user_exchanges": stat("user_exchanges"),
        })
    return rows


def _fmt(value, digits=1):
    return "n/a" if value is None else (f"{value:.{digits}f}" if isinstance(value, float) else str(value))


def render_table(rows):
    header = ["arm", "kind", "provider", "model", "runtime", "revision", "runs", "correct", "false_ok",
              "incorrect", "blocked", "tok_total", "tok_mean", "cost_total", "secs_mean", "tools_mean", "user_mean"]
    table = [header]
    for row in rows:
        cost = row["cost_usd"]
        cost_text = "n/a" if cost["total"] is None else (
            f"{cost['total']:.4f}" + ("" if cost["runs_reporting"] == row["runs"]
                                       else f" ({cost['runs_reporting']}/{row['runs']} runs)"))
        table.append([row["arm"] + (" [SYNTHETIC]" if row["synthetic"] else ""), row["arm_kind"], row["provider"],
                      row["model"], row["runtime"], row["revision"], str(row["runs"]), str(row["correct"]),
                      str(row["false_success"]), str(row["incorrect"]), str(row["blocked"]),
                      _fmt(row["tokens"]["total"]), _fmt(row["tokens"]["mean"]), cost_text,
                      _fmt(row["seconds"]["mean"]), _fmt(row["tool_turns"]["mean"]),
                      _fmt(row["user_exchanges"]["mean"])])
    widths = [max(len(line[i]) for line in table) for i in range(len(header))]
    return "\n".join("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip() for line in table)


# --- extract -------------------------------------------------------------------------------------

def _usage_tokens(usage):
    if not isinstance(usage, dict):
        return None
    values = [usage.get(key) for key in TOKEN_KEYS if isinstance(usage.get(key), int)]
    return sum(values) if values else None


def classify(record, final_text):
    """blocked: the harness or runtime failed; correct: graders passed; false_success: graders
    failed although the agent claimed completion; incorrect: failed, claim unknown or absent."""
    failures = record.get("failures") or []
    if record.get("passed"):
        return "correct"
    if record.get("exit_code") is None or any(str(f).startswith(("HARNESS", "no session events"))
                                              for f in failures):
        return "blocked"
    if final_text is not None and CLAIM.search(final_text):
        return "false_success"
    return "incorrect"


def build_artifact(record, report, args, session_lines=None):
    """Whitelist projection of one harness record. Nothing from prompts, paths, failure text,
    changed_files, fixtures or agent text is copied; those are only counted or pattern-tested."""
    tokens, cost = record.get("tokens"), record.get("cost_usd")
    tool_turns = user_exchanges = final_text = None
    if session_lines is not None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from harness import read_transcript  # lazy: needs the repository checkout
        transcript = read_transcript(report.get("provider", "claude"), session_lines)
        tool_turns = len(transcript.tools())
        user_exchanges = 1 + len(transcript.tools("AskUserQuestion"))  # the task prompt + clarifying questions
        final_text = transcript.final_text
        if tokens is None:
            tokens = transcript.tokens if transcript.tokens is not None else _usage_tokens(transcript.result.get("usage"))
        if cost is None:
            cost = transcript.cost
    return validate({
        "schema": SCHEMA, "synthetic": False, "case": record.get("case"), "run": record.get("run"),
        "arm": {"name": args.arm, "kind": args.arm_kind},
        "meta": {"provider": report.get("provider"), "model": report.get("model"),
                 "runtime": args.runtime, "revision": args.revision},
        "outcome": classify(record, final_text), "tokens": tokens, "cost_usd": cost,
        "seconds": record.get("seconds"), "tool_turns": tool_turns, "user_exchanges": user_exchanges})


def cmd_extract(args):
    source = Path(args.report)
    report = json.loads(source.read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for record in report.get("runs", []):
        session = source.parent / f"{record.get('case')}#{record.get('run')}.jsonl"
        lines = session.read_text().splitlines() if session.is_file() else None
        artifact = build_artifact(record, report, args, lines)
        path = out / f"{args.arm}--{artifact['case']}--{artifact['run']}.json"
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
        written.append(path)
    print(f"wrote {len(written)} sanitized artifact(s) to {out}")
    return 0


def cmd_report(args):
    rows = aggregate(load_artifacts(args.dir), tuple(filter(None, args.group_by.split(","))))
    if not rows:
        raise MeasureError(f"no {SCHEMA} artifacts under {args.dir}")
    print(json.dumps(rows, indent=2, sort_keys=True) if args.json else render_table(rows))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract", help="sanitize a run_evals report into artifacts")
    extract.add_argument("report", help="report.json written by run_evals.py (raw <case>#<n>.jsonl beside it is used if present)")
    extract.add_argument("--out", required=True, help="directory for the artifacts")
    extract.add_argument("--arm", required=True, help="arm label, e.g. template-4.4.0 or local-settings-x")
    extract.add_argument("--arm-kind", required=True, choices=ARM_KINDS,
                         help="template: the distributed template changed; local-settings: project-local settings changed")
    extract.add_argument("--runtime", required=True, help="runtime version label, e.g. claude-2.1.0")
    extract.add_argument("--revision", required=True, help="Lean revision measured, e.g. a short commit or tag")
    report = sub.add_parser("report", help="aggregate artifacts per arm")
    report.add_argument("dir", help="directory of artifacts")
    report.add_argument("--json", action="store_true")
    report.add_argument("--group-by", default="", help="comma list of provider,model,runtime,revision to split arms")
    args = parser.parse_args(argv)
    try:
        return cmd_extract(args) if args.command == "extract" else cmd_report(args)
    except MeasureError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

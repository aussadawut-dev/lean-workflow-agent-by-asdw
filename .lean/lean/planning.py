"""Read-only validation previews, never gate execution or permission to reuse checks."""
from pathlib import Path
import subprocess

from . import evidence, gate, guard, target, testsel
from .util import LeanError, safe_path


def _commands(project, tier, cwd, application=False):
    commands = target.gate_commands(project) if application else gate.gate_commands(project, tier)
    return {"project_file": str(project), "cwd": str(cwd), "tier": tier,
            "commands": commands or [], "runnable": bool(commands),
            "reason": ("configured checks" if commands else
                       "Stop tier is undefined; automatic Stop uses the full tier" if commands is None else
                       "Gate has no configured checks"),
            "automatic_stop_tier": ("full" if commands is None else "stop") if tier == "stop" else None}


def _review(root, contract, session, paths, active, target_paths):
    reasons = []
    depth = "UNKNOWN"
    if contract is not None:
        match = evidence.CONTRACT.fullmatch(contract) if isinstance(contract, str) else None
        if not match or "\n" in contract or "\r" in contract:
            raise LeanError("plan needs a real single-line Task Contract")
        if match.group(1):
            risk, quality = match.group(1, 2)
            floor = {"STANDARD": "LOW", "HIGH": "MEDIUM", "VERY_HIGH": "HIGH"}[quality]
            depth = max((risk, floor), key=("LOW", "MEDIUM", "HIGH").index)
            reasons.append(f"contract risk {risk}; quality {quality} sets minimum {floor}")
        else:
            depth = "NONE"
            reasons.append("trivial contract")
    else:
        reasons.append("no explicit or bound session contract; contract review depth is unknown")
    # Use the gate's session/target risk reader as well as the test-selection delta. An
    # explicit test base may include additional changes; it must never lower the gate floor.
    risky = set(evidence.high_risk_changes(root, session))
    risky.update(evidence.matching_risk(paths, evidence.high_risk_areas(root)))
    if active["target"] is not None:
        prefix = Path(active["project_root"]).relative_to(root).as_posix() + "/"
        risky.update(prefix + path for path in evidence.matching_risk(
            target_paths, evidence.high_risk_areas(Path(active["record_root"]))))
    if risky:
        depth = "HIGH"
        reasons.append("changed PROJECT High-risk areas require independent HIGH review")
    return {"depth": depth, "independent": depth == "HIGH", "reasons": reasons,
            "high_risk_paths": sorted(risky)}


def _evidence(root, contract, review, tier):
    name = gate.STOP_RESULT_FILE if tier == "stop" else gate.RESULT_FILE
    try:
        recorded = gate.load_result(root, name)
        recorded_status = recorded["status"] if recorded else "NOT_RUN"
        state_status = (gate.stop_status(root) or "NOT_RUN") if tier == "stop" else gate.status(root)
        gate_evidence = {"recorded_status": recorded_status, "state_status": state_status,
                         "reason": "Recorded evidence only; no validation was run"}
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        gate_evidence = {"recorded_status": "UNKNOWN", "state_status": "UNKNOWN", "reason": str(error)}
    receipt = {"status": "not_assessed", "reason": "No usable contract to assess exact-contract coverage"}
    require_receipt = bool(gate.HIGH_REVIEW.match(contract or ""))
    if contract is not None and not require_receipt and not review["high_risk_paths"]:
        receipt = {"status": "not_required", "reason": "Gate does not require an independent receipt; semantic review follows the stated review depth"}
    elif require_receipt or review["high_risk_paths"]:
        try:
            gate.check_receipt(root, contract or "", require_receipt, review["high_risk_paths"])
            receipt = {"status": "covered", "reason": "Existing receipt readers found the required coverage"}
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            receipt = {"status": "not_covered", "reason": str(error)}
    return {"gate": gate_evidence, "review": receipt,
            "reuse": {"status": "not_assessed", "eligible": None,
                      "reason": "Only the gate runner evaluates all reuse predicates; a recorded PASS is insufficient"}}


def plan(root, *, base=None, tier="full", contract=None, session=""):
    """Return a JSON-safe preview for an explicit workflow root, without writing state.

    ``base`` applies only to the workspace Git repository. Selected application checks
    are shown separately, with their own cwd and full gate; Lean's impact map cannot
    describe application tests. No execution, locking, control acceptance or cache writes.
    """
    root = Path(root).resolve()
    if tier not in gate.MARKERS:
        raise LeanError("plan tier must be full or stop")
    if not isinstance(session, str) or "\n" in session or "\r" in session:
        raise LeanError("plan session must be a single-line string")
    active = target.context(root)  # Invalid selections fail; never silently plan the workspace alone.
    project = safe_path(root, ".lean/PROJECT.md")
    paths = testsel.changed(root, base)
    files, reason = testsel.select(root, paths)
    selected = {"scope": "workflow", "root": str(root), "files": files,
                "reason": reason, "status": "selected"}
    application, target_paths = None, []
    if active["target"] is not None:
        application_root = Path(active["project_root"])
        target_paths = testsel.changed(application_root)
        application = {"name": active["target"], "changed_paths": target_paths,
                       "base": None, "base_reason": "--base applies only to the workspace repository",
                       "gate": _commands(Path(active["project_file"]), "full", application_root, application=True),
                       "tests": {"scope": "application", "files": [], "status": "not_assessed",
                                 "reason": "Application tests are defined by its gate commands; Lean impact selection applies only to workflow tests"}}
    if contract is None and session:
        contract = guard.current(root, session)
    review = _review(root, contract, session, paths, active, target_paths)
    return {"schema": 1, "preview": True, "validation": "NOT_RUN",
            "notice": "Read-only preview; state can change before execution. The actual gate remains authoritative.",
            "roots": active, "base": base, "contract": contract,
            "changed_paths": paths, "tests": selected, "gate": _commands(project, tier, root),
            "target": application, "review": review, "evidence": _evidence(root, contract, review, tier)}


def explain(value):
    """Render the preview without implying that the listed checks have passed."""
    lines = [value["notice"], "Validation: NOT_RUN", "Workflow root: " + value["roots"]["workflow_root"],
             f"Changed paths ({len(value['changed_paths'])}):"]
    lines += ["  " + path for path in value["changed_paths"]] or ["  (none)"]
    tests = value["tests"]
    lines.append(f"Workflow tests ({len(tests['files'])}): {tests['reason']}")
    lines += ["  " + name for name in tests["files"]]
    for label, block in [("Workspace", value["gate"])] + (
            [("Target " + value["target"]["name"], value["target"]["gate"])] if value["target"] else []):
        lines.append(f"{label} gate ({block['tier']}, cwd={block['cwd']}): {block['reason']}")
        lines += ["  " + command for command in block["commands"]]
    if value["target"]:
        lines.append("Target tests: " + value["target"]["tests"]["reason"])
        lines.append("Target base: " + value["target"]["base_reason"])
        lines += ["  target changed: " + path for path in value["target"]["changed_paths"]]
    review = value["review"]
    lines.append(f"Required review: {review['depth']}" + (" (independent)" if review["independent"] else ""))
    lines += ["  " + reason for reason in review["reasons"]]
    lines += ["  high-risk: " + path for path in review["high_risk_paths"]]
    current = value["evidence"]
    lines.append(f"Recorded gate: {current['gate']['recorded_status']}; state status: {current['gate']['state_status']}")
    lines.append(f"Review evidence: {current['review']['status']}; {current['review']['reason']}")
    lines.append("Check reuse: not assessed; " + current["reuse"]["reason"])
    return "\n".join(lines)

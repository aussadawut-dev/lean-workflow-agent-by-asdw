"""`lean` command dispatch. Each group lives in its own module; this file only wires arguments."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from . import __version__
from .util import LeanError, WORKFLOW_ROOT, recorded_gate


class Parser(argparse.ArgumentParser):
    """No option abbreviations: the contract guard reads exact option names, so `--exp` must not mean `--export`.
    Subcommand parsers inherit this class."""

    def __init__(self, *args, **kwargs):
        kwargs["allow_abbrev"] = False
        super().__init__(*args, **kwargs)


def build_parser(argv=()):
    from . import models, progress, records, spawn
    gate_modes = ()
    if "gate" in argv:  # Only the gate group needs the gate's constants; importing it costs every other call.
        from . import gate
        gate_modes = gate.MODES
    parser = Parser(prog="lean", description="Lean Workflow command line.")
    parser.add_argument("--root", type=Path, default=None,
                        help="explicit root (default: this checkout; records follow the selected target)")
    parser.add_argument("--workflow-root", type=Path, default=None,
                        help="workflow templates when --root names a target's record root")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    commands.add_parser("version", help="print the workflow version")
    status = commands.add_parser("status", help="mode, tracker, gate and progress at a glance")
    status.add_argument("--line", action="store_true", help="one line for a status bar (Claude statusLine)")
    status.add_argument("--json", action="store_true")
    watch = commands.add_parser("watch", help="live progress view for a second terminal pane")
    watch.add_argument("--interval", type=float, default=1.0)
    watch.add_argument("--once", action="store_true", help="draw one frame and exit")

    prog = commands.add_parser("progress", help="report task progress (drives every progress bar)")
    prog_actions = prog.add_subparsers(dest="action", required=True)
    prog_set = prog_actions.add_parser("set", help="enter a phase: " + ", ".join(progress.PHASES + (progress.DONE,)))
    prog_set.add_argument("phase", choices=progress.PHASES + (progress.DONE,))
    prog_set.add_argument("--done", type=int)
    prog_set.add_argument("--total", type=int)
    prog_set.add_argument("--task")
    prog_set.add_argument("--note")
    prog_actions.add_parser("show")
    prog_actions.add_parser("clear")

    contract = commands.add_parser("contract", help="declare or show the session's Task Contract")
    contract_actions = contract.add_subparsers(dest="action", required=True)
    declare = contract_actions.add_parser("declare", help="validate a contract (the hook binds it to the session)")
    declare.add_argument("--contract", help="one-line contract; omit to read a block from stdin")
    current = contract_actions.add_parser("current", help="print the session's declared contract")
    current.add_argument("--session", required=True)

    hook = commands.add_parser("hook", help="provider lifecycle hook entry (reads the hook JSON on stdin)")
    hook.add_argument("provider", choices=("claude", "codex"))
    hook.add_argument("event", choices=("pre-tool", "prompt", "session-start", "stop"))
    hook.add_argument("--cache-tree", action="store_true")

    gate_parser = commands.add_parser("gate", help="Quality Gate")
    gate_actions = gate_parser.add_subparsers(dest="action", required=True)
    gate_run = gate_actions.add_parser("run", help="run PROJECT.md checks with contract and review evidence")
    gate_run.add_argument("--cache-tree", action="store_true")
    gate_run.add_argument("--require-review", action="store_true")
    gate_run.add_argument("--quiet", action="store_true")
    gate_run.add_argument("--contract", default="")
    gate_run.add_argument("--session", default="")
    gate_run.add_argument("--hook", action="store_true", help=argparse.SUPPRESS)  # Raw hook mode, payload on stdin.
    gate_run.add_argument("--seed", action="store_true", help=argparse.SUPPRESS)
    gate_actions.add_parser("status", help="last recorded gate result (never a fresh run)")
    gate_mode = gate_actions.add_parser("mode", help="show or set automation: " + ", ".join(gate_modes))
    gate_mode.add_argument("mode", nargs="?", choices=gate_modes)
    gate_mode.add_argument("--policy", action="store_true", help="print the policy text")
    accept = gate_actions.add_parser("accept-controls", help="record an already user-approved control change")
    accept.add_argument("--reason", required=True)
    pending = gate_actions.add_parser("review-pending",
                                      help="quiet Stops while an independent review of this exact state runs")
    pending.add_argument("--contract", required=True)
    pending.add_argument("--session", required=True)
    gate_scope = gate_actions.add_parser(
        "scope", help="run one gate check unless the change touches only work records (LEAN_GATE_SCOPE=full runs it)")
    gate_scope.add_argument("--only", action="append", default=[], metavar="GLOB",
                            help="another path that alone does not need this check (repeatable)")
    gate_scope.add_argument("--always", action="append", default=[], metavar="GLOB",
                            help="a path that always needs this check, even if it is a record (repeatable)")
    gate_scope.add_argument("check", nargs=argparse.REMAINDER, help="-- <command> [args...]")

    evidence_parser = commands.add_parser("evidence", help="review receipts and shipping state", add_help=False)
    evidence_parser.add_argument("rest", nargs=argparse.REMAINDER)

    records.parser_for(commands)

    test = commands.add_parser("test", help="run categorised tests; --changed selects by impact")
    scope = test.add_mutually_exclusive_group()
    scope.add_argument("--changed", action="store_true", help="only tests the current change can affect")
    scope.add_argument("--all", action="store_true")
    scope.add_argument("--tier", action="append", choices=("unit", "hooks", "e2e"))
    test.add_argument("--base", help="also count changes since this commit")
    test.add_argument("--list", action="store_true", help="show the selection without running it")
    test.add_argument("-j", "--jobs", type=int)
    test.add_argument("files", nargs="*", help="tiers (unit, hooks, e2e) or <tier>/test_<name>.py files")

    lint = commands.add_parser("lint", help="static workflow checks")
    lint.add_argument("--write-registry", action="store_true",
                      help="maintainers: regenerate .lean/assets.json from the workflow files first")
    commands.add_parser("attribution", help="refuse unpushed commits that carry AI attribution")

    models_parser = commands.add_parser("models", help="per-provider model list (sizes 3S-3XL)")
    models_actions = models_parser.add_subparsers(dest="action")
    models_actions.add_parser("list")
    models_check = models_actions.add_parser("check", help="validate the list; --live asks the provider CLIs")
    models_check.add_argument("--live", action="store_true")
    models_eval = models_actions.add_parser("eval", help="run candidates on the graded task bank within a token budget")
    models_eval.add_argument("--plan", type=Path, required=True, help='{"candidates": [{provider, model, effort}], "tasks": [sizes]}')
    models_eval.add_argument("--budget", type=int, required=True, help="token cap: no run starts once it is spent")
    models_eval.add_argument("--out", type=Path, help="results folder (default docs/benchmarks/<date>-model-eval)")
    models_eval.add_argument("-j", "--jobs", type=int, default=4)
    models_eval.add_argument("--timeout", type=int, default=900, help="seconds per run")
    models_eval.add_argument("--estimate", type=int, help="tokens reserved per run until a real count is known "
                             "(default 250000)")
    models_apply = models_actions.add_parser("apply", help="write an approved eval proposal into models.json")
    models_apply.add_argument("--proposal", type=Path, required=True)
    models_apply.add_argument("--sha256", required=True, help="the digest `lean models eval` printed for it")
    models_actions.add_parser("bank", help="check the task bank: references score full marks, stubs do not")

    spawn_parser = commands.add_parser("spawn", help="plan or run agents for independent tasks")
    spawn_actions = spawn_parser.add_subparsers(dest="action", required=True)
    for name in ("plan", "run"):
        sub = spawn_actions.add_parser(name)
        sub.add_argument("--tasks", type=Path, help="task list JSON: {\"tasks\": [{id, files, size, deps, prompt}]}")
        sub.add_argument("--level", choices=("default", "max"), default="default",
                         help="default: max_agents at once; max: every parallel task (/lean-agents)")
        sub.add_argument("--provider", choices=models.PROVIDERS)
        sub.add_argument("--model", help="explicit model for every agent (needs -n)")
        sub.add_argument("-n", "--count", type=int, help="explicit agent count (/lean-agents <model> xN)")
        sub.add_argument("--effort")
        if name == "run":
            sub.add_argument("--plan", type=Path, help="a plan JSON from `lean spawn plan`")
            sub.add_argument("--timeout", type=int, default=spawn.DEFAULT_TIMEOUT)
            sub.add_argument("--allow-api-keys", action="store_true",
                             help="keep metered API credentials in agent environments")
            sub.add_argument("--allow-dirty", action="store_true")
            sub.add_argument("--trust-agents", action="store_true",
                             help="let agents run any command without asking (see docs/agents-and-models.md)")
    spawn_clean = spawn_actions.add_parser("clean", help="remove a run's worktrees and branches")
    spawn_clean.add_argument("run")

    log = commands.add_parser("log", help="development activity: timeline, phase durations, export")
    log.add_argument("--task", help="only this task's phases")
    log.add_argument("--since", help="ISO time, e.g. 2026-10-26T08:00:00Z")
    log.add_argument("--summary", action="store_true", help="durations and counts instead of the timeline")
    log.add_argument("--json", action="store_true")
    log.add_argument("--export", type=Path, help="write the log to a project file (.md or .jsonl)")

    target = commands.add_parser("target", help="application repositories as submodules (lean-target)")
    target_actions = target.add_subparsers(dest="action", required=True)
    use = target_actions.add_parser("use", help="add or reuse a remote as targets/<name> and select it")
    use.add_argument("remote")
    use_choice = use.add_mutually_exclusive_group()
    use_choice.add_argument("--apply", action="store_true")
    use_choice.add_argument("--dry-run", action="store_true")
    target_actions.add_parser("context", help="workflow, project and record roots of the selection")
    target_actions.add_parser("clear", help="deselect the target, keeping its checkout and records")
    target_gate = target_actions.add_parser("gate", help="run the selected application's checks")
    target_gate.add_argument("--optional", action="store_true")
    target_gate.add_argument("--quiet", action="store_true")
    target_gate.add_argument("--session", default="")

    effort = commands.add_parser("effort", help="procedure intensity (not model effort)")
    effort.add_argument("level", nargs="?", choices=("standard", "high", "ultra", "reset"))
    effort.add_argument("skill", nargs="?")

    update = commands.add_parser("update", help="update Lean from a pinned upstream release")
    update_actions = update.add_subparsers(dest="action", required=True)
    preview = update_actions.add_parser("preview", help="fetch a release and plan the update (no target writes)")
    preview.add_argument("--target", type=Path, help="installation to update (default: this checkout)")
    preview.add_argument("--source", help="upstream Git URL or path")
    preview.add_argument("--ref", help="tag, branch or commit (default: highest stable tag)")
    preview.add_argument("--workspace", type=Path, help="external directory for the release and plan")
    apply = update_actions.add_parser("apply", help="apply a previewed plan with snapshots")
    apply.add_argument("--workspace", type=Path, required=True)
    apply.add_argument("--take", action="append", default=[], help="take the incoming version of a conflict path")
    rollback = update_actions.add_parser("rollback", help="restore the snapshot of an applied plan")
    rollback.add_argument("--workspace", type=Path, required=True)
    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser(argv)
    args = parser.parse_args(argv)
    try:
        root = (args.root or WORKFLOW_ROOT).resolve()
        if args.root is None and args.command in RECORD_COMMANDS:
            # Workflow records follow the selected target; an invalid selection fails, never falls back.
            from . import target
            root = target.record_root(WORKFLOW_ROOT)
        if args.command in RECORD_COMMANDS:
            from . import records
            if args.workflow_root is not None:
                records.TEMPLATE_ROOT = args.workflow_root.resolve() / ".lean/templates"
            elif root != WORKFLOW_ROOT:
                records.TEMPLATE_ROOT = WORKFLOW_ROOT / ".lean/templates"
        return dispatch(root, args, parser)
    except LeanError as error:
        print(f"lean: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"lean {args.command}: {error}", file=sys.stderr)
        return 2


# Commands whose state belongs to the selected target's record root.
RECORD_COMMANDS = ("mode", "tracker", "queue", "effort", "models")


def emit(code, out, err):
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


def dispatch(root, args, parser):
    command = args.command
    if command == "version":
        print(__version__)
        return 0
    if command == "hook":
        from . import hooks
        stdin = sys.stdin.read() if not sys.stdin.isatty() else ""
        return emit(*hooks.run_hook(root, args.provider, args.event, stdin, args.cache_tree))
    if command == "contract":
        from . import guard
        if args.action == "declare":
            text, meta = guard.parse(args.contract if args.contract is not None else sys.stdin.read())
            if not guard.declaration_bound(root, text):
                print("lean: this contract was validated but NOT bound: no session in this checkout holds it. "
                      "The guard binds only a declare that is its own command with a literal single-quoted "
                      "--contract or a quoted heredoc (no shell variable, pipe or preceding command); it binds in "
                      "the session's project, not in a checkout reached with `cd`; and it runs only if Lean's "
                      "hooks were loaded when this Claude session started (restart after /lean-init).\n"
                      + guard.HELP, file=sys.stderr)
                return 2
            print(text + "".join(f"\n{name}: {value}" for name, value in meta.items()))
            return 0
        found = guard.current(root, args.session)
        if not found:
            print("No Task Contract declared for this session", file=sys.stderr)
            return 1
        print(found)
        return 0
    if command == "progress":
        from . import progress
        if args.action == "set":
            state = progress.update(root, args.phase, args.done, args.total, args.task, args.note)
            print(progress.line(state))
        elif args.action == "show":
            print(progress.shown(root) or "no task tracked")
        else:
            progress.clear(root)
        return 0
    if command == "status":
        return status(root, args)
    if command == "watch":
        return watch(root, args)
    if command == "gate":
        return gate_command(root, args)
    if command == "evidence":
        from . import evidence
        return evidence.main(args.rest, root=root)
    if command in ("mode", "tracker", "queue"):
        from . import records
        return records.run(root, args)
    if command == "test":
        return test_command(root, args)
    if command == "lint":
        from . import structure
        if args.write_registry:
            print(f"registry: {structure.write_registry(root)} files")
        failures = structure.check(root)
        for failure in failures:
            print(f"FAIL {failure}")
        print("lint ok" if not failures else f"lint: {len(failures)} problem(s)")
        return 1 if failures else 0
    if command == "attribution":
        from . import attribution
        message = attribution.check(root)
        if message:
            print(message, file=sys.stderr)
        return 1 if message else 0
    if command == "models":
        from . import models
        if args.action == "check":
            ok, lines = models.check(root, live=args.live)
            print("\n".join(lines))
            return 0 if ok else 1
        if args.action in ("eval", "apply", "bank"):
            return models_eval_command(root, args)
        print(models.table(models.load(root)))
        return 0
    if command == "spawn":
        return spawn_command(root, args)
    if command == "effort":
        from . import effort
        print(effort.run(root, args.level, args.skill))
        return 0
    if command == "update":
        from . import update
        return update.command(root, args)
    if command == "target":
        from . import target
        return target.command(root, args)
    if command == "log":
        from . import activity
        events = activity.load(root, args.since, args.task)
        if args.export:
            print(f"exported {len(events)} events to {activity.export(root, args.export, events)}")
        elif args.json:
            print(json.dumps(events, indent=2, ensure_ascii=False))
        else:
            print("\n".join(activity.summary(events) if args.summary else activity.timeline(events) or
                            ["no activity recorded"]))
        return 0
    parser.error(f"unknown command {command}")
    return 2


def status_line_session():
    """The session a Claude status line is drawn for (its stdin JSON), else this process's session."""
    from . import progress
    import select
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return None
        fd, chunks = sys.stdin.fileno(), []
        # Bounded: an inherited pipe that never closes must not hang a status bar.
        while sum(map(len, chunks)) < 1 << 20 and select.select([fd], [], [], 0.2)[0]:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        data = json.loads(b"".join(chunks) or b"{}")
        found = progress.valid_session(data.get("session_id")) if isinstance(data, dict) else ""
        return found or None
    except (OSError, ValueError, AttributeError):
        return None


def status(root, args):
    from . import progress
    if args.line:  # Refreshed often: no tree hashing, and none of the gate's imports.
        text = progress.shown(root, status_line_session()) or "Lean: no task tracked"
        try:
            gate_state = recorded_gate(root)
        except (OSError, ValueError):
            gate_state = "UNKNOWN"
        print(f"{text} · gate {gate_state}")
        return 0
    state = progress.load(root)
    from . import gate, records
    config = records.config(root)
    report = {"version": __version__, "mode": config["mode"], "execution": config["execution"],
              "gate": gate.status(root), "progress": state}
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"Lean {__version__} · mode {config['mode']}/{config['execution']} · gate {report['gate']}")
    print(progress.watch_frame(root))
    return 0


def watch(root, args):
    from . import progress
    try:
        while True:
            frame = progress.watch_frame(root)
            if args.once:
                print(frame)
                return 0
            sys.stdout.write("\x1b[2J\x1b[H" + time.strftime("%H:%M:%S ") + "lean watch (Ctrl-C to stop)\n"
                             + frame + "\n")
            sys.stdout.flush()
            time.sleep(max(0.2, args.interval))
    except KeyboardInterrupt:
        return 0


def gate_command(root, args):
    if args.action == "scope":
        from . import testsel
        command = args.check[1:] if args.check[:1] == ["--"] else args.check
        return testsel.scoped(Path.cwd(), command, args.only, args.always)
    from . import evidence, gate
    if args.action == "status":
        print(gate.status(root))
        return 0
    if args.action == "mode":
        if args.mode and args.policy:
            raise LeanError("--policy only inspects; it cannot be combined with a mode to set")
        try:
            if args.mode:
                gate.write_mode(root, args.mode)
            mode, _, _, configured = gate.read_mode(root)
        except (OSError, ValueError) as error:
            print(f"Gate policy invalid/unavailable: {error}; validation NOT_RUN.", file=sys.stderr)
            return 2
        print(gate.policy(mode) if args.policy else json.dumps({"mode": mode, "configured": configured}))
        return 0
    if args.action == "accept-controls":
        return evidence.main(["accept-controls", "--reason", args.reason], root=root)
    if args.action == "review-pending":
        try:
            marker = gate.mark_review_pending(root, args.contract, args.session)
        except ValueError as error:
            print(f"review-pending refused: {error}", file=sys.stderr)
            return 2
        print(f"Review pending for this contract and shipping state; Stops are released UNVERIFIED for up to "
              f"{gate.PENDING_LIMIT // 3600}h or until the state, contract or receipt changes ({marker['state'][:12]}).")
        return 0
    try:
        gate.read_mode(root)
    except (OSError, ValueError) as error:
        print(f"Gate policy invalid/unavailable: {error}; validation NOT_RUN.", file=sys.stderr)
        return 2
    if args.seed and not args.hook:
        raise LeanError("--seed requires --hook")
    payload = None
    if args.hook:
        text = sys.stdin.read() if not sys.stdin.isatty() else ""
        payload = json.loads(text) if text.strip() else {}
        if not isinstance(payload, dict):
            raise LeanError("hook input must be a JSON object")
    code, out, err = gate.run(root, hook=args.hook, seed=args.seed, cache_tree=args.cache_tree,
                              require_review=args.require_review, quiet=args.quiet, contract=args.contract,
                              session=args.session, payload=payload)
    for line in out:
        print(line)
    for line in err:
        print(line, file=sys.stderr)
    if code == 0 and not args.quiet and not args.hook:
        print("Quality Gate: PASS", file=sys.stderr)
    return code


def models_eval_command(root, args):
    import tempfile
    import time
    from . import evals
    if args.action == "bank":
        with tempfile.TemporaryDirectory() as work:
            report = evals.check_bank(Path(work))
        bad = [size for size, (reference, stub, units) in report.items() if reference != units or stub >= units]
        for size, (reference, stub, units) in report.items():
            print(f"{size:<3} reference {reference}/{units}  stub {stub}/{units}")
        print("task bank ok" if not bad else "task bank FAILED: " + ", ".join(bad))
        return 1 if bad else 0
    if args.action == "apply":
        changes = evals.apply(root, args.proposal, args.sha256)
        print("\n".join(changes) if changes else "no change: models.json already matches the proposal")
        return 0
    out = args.out or root / "docs" / "benchmarks" / time.strftime("%Y-%m-%d-model-eval")
    print(f"runs in {evals.work_folder(out)} (for agy's write_file allow rule)")
    rows, skipped = evals.evaluate(root, args.plan, args.budget, out, jobs=args.jobs, timeout=args.timeout,
                                   estimate=evals.ESTIMATE if args.estimate is None else args.estimate)
    sha = evals.write_outputs(out, rows, skipped, args.budget)
    print(f"results: {out}/results.jsonl, {out}/summary.md")
    print(f"proposal: {out}/proposal.json (sha256 {sha}); apply only after review and the user's approval:")
    print(f"python3 .lean/bin/lean models apply --proposal {out}/proposal.json --sha256 {sha}")
    if skipped:
        print(f"{len(skipped)} run(s) skipped at the budget")
    return 0


def test_command(root, args):
    from . import structure, testsel
    if args.files:
        files, reason = testsel.named(root, args.files), "named files"
    elif args.tier:
        files, reason = testsel.all_files(root, tuple(args.tier)), "tier " + ", ".join(args.tier)
    elif args.changed:
        files, reason = testsel.select(root, testsel.changed(root, args.base))
    else:
        files, reason = testsel.all_files(root), "all tests"
    if reason == "lint":
        print("Documentation-only change: lint only.")
        if args.list:
            return 0
        failures = structure.check(root)
        for failure in failures:
            print(f"FAIL {failure}")
        return 1 if failures else 0
    print(f"Selected {len(files)} test file(s): {reason}")
    if args.list:
        print("\n".join(files))
        return 0
    if not files:
        return 0
    return 1 if testsel.run_files(root, files, args.jobs, reason=reason) else 0


def spawn_command(root, args):
    from . import progress, spawn
    if args.action == "clean":
        print(spawn.clean(root, args.run))
        return 0
    if args.action == "run" and args.plan:
        from .util import read_json
        planned = read_json(args.plan)
    else:
        if not args.tasks:
            raise LeanError("--tasks is required (or --plan for run)")
        tasks = spawn.load_tasks(args.tasks)
        level = "explicit" if args.count else args.level
        planned = spawn.plan(root, tasks, level, args.provider, args.model, args.count, args.effort)
    if args.action == "plan":
        print(spawn.to_json(planned))
        for note in planned["notes"]:
            print(f"note: {note}", file=sys.stderr)
        return 0
    from . import target
    if target.context(root)["target"] is not None:
        raise LeanError("spawn run builds worktrees of the Lean workspace, which do not contain the selected "
                        "target's application; for target work spawn in-session subagents from `lean spawn plan`, "
                        "or clear the target first")
    document = spawn.run(root, planned, args.timeout, args.allow_api_keys, args.allow_dirty,
                         trusted=args.trust_agents)
    print(spawn.summary(document))
    return 0 if all(row["status"] == "done" for row in document["agents"]) else 1

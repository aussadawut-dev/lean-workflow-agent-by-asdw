#!/usr/bin/env python3
"""Task Contract declarations shared by the Claude and Codex hooks.

A session declares its contract with a `declare` shell command. The PreToolUse
hook binds the declared text to the session and denies write-capable tools
until a declaration exists; a person's prompt clears it. These records catch
mistakes; they are not a security boundary.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time

sys.dont_write_bytecode = True
LINE = re.compile(r"Contract: (?:risk=(LOW|MEDIUM|HIGH) quality=(STANDARD|HIGH|VERY_HIGH) acceptance=([^<\s].*)"
                  r"|trivial \(([^<].*)\))\Z")
FIELDS = ("topic", "risk", "quality", "budget", "skill", "acceptance")
REQUIRED = ("risk", "quality", "acceptance")
VALUES = {"risk": ("LOW", "MEDIUM", "HIGH"), "quality": ("STANDARD", "HIGH", "VERY_HIGH"),
          "budget": ("CHEAP", "BALANCED", "EXPENSIVE")}
# Tools that cannot change files by themselves. Everything else, including shell
# and MCP tools, waits for a declaration; an unknown tool is guarded, not trusted.
READ_ONLY = {"Read", "Glob", "Grep", "LS", "NotebookRead", "WebFetch", "WebSearch", "ToolSearch", "Skill",
             "AskUserQuestion", "TodoWrite", "Agent", "Task", "SendMessage", "ListAgents", "EnterPlanMode",
             "ExitPlanMode", "update_plan", "view_image", "web_search", "request_user_input"}
READ_ONLY_PREFIXES = ("collaboration",)  # Codex subagent spawn, wait and messaging tools.
# A declaration is a whole command: optional `cd <dir> &&`, then the declare call with a
# single-quoted --contract or a quoted heredoc, so no shell expansion or chained command runs.
DECLARE = re.compile(r"\s*(?:cd\s+(?:\"[^\"$`\\]*\"|'[^']*'|[\w./~-]+)\s*&&\s*)?python3\s+"
                     r"(?:\"(?:[^\"$`\\]*/)?\.lean/scripts/contract_guard\.py\"|'(?:[^']*/)?\.lean/scripts/contract_guard\.py'"
                     r"|(?:\"\$CLAUDE_PROJECT_DIR\"/|\$CLAUDE_PROJECT_DIR/|[\w./~-]*?)\.lean/scripts/contract_guard\.py)"
                     r"\s+declare(?P<rest>.*)\Z")
SINGLE = re.compile(r"\s+--contract\s+'(?P<text>[^'\n]*)'\s*\Z")
HEREDOC = re.compile(r"\s*<<-?\s*(?P<quote>['\"])(?P<word>\w+)(?P=quote)\s*\Z")
RUNTIME_PROMPTS = ("<task-notification>", "<agent-message", "<cross-session-message")
MAX_SESSIONS = 64
HELP = ("Declare the Task Contract first, in its own command:\n"
        "python3 .lean/scripts/contract_guard.py declare <<'EOF'\nContract:\nrisk: LOW\nquality: STANDARD\n"
        "acceptance: <observable check>\nEOF\n"
        "or: python3 .lean/scripts/contract_guard.py declare --contract 'Contract: trivial (<reason>)'.\n"
        "Write the same contract at the top of your reply. A new user prompt clears the declaration.")


def parse(text):
    """Return (canonical one-line contract, metadata) or raise ValueError.

    Accepts the one-line form, or a block: `Contract:` then one `field: value` per line in
    the order topic, risk, quality, budget, skill, acceptance, ending at a blank line.
    """
    lines = text.strip("\n").splitlines()
    if not lines:
        raise ValueError("empty contract")
    first = lines[0].strip()
    if first != "Contract:":
        if LINE.fullmatch(first):
            return first, {}
        raise ValueError("a contract starts with `Contract:` and is either one line or a field block")
    values, order = {}, []
    for line in lines[1:]:
        if not line.strip():
            break
        name, colon, value = line.partition(":")
        name, value = name.strip().lower(), value.strip()
        if not colon or name not in FIELDS:
            raise ValueError(f"unknown contract field line: {line.strip()[:80]!r}")
        if name in values:
            raise ValueError(f"duplicate contract field: {name}")
        if not value or value.startswith("<"):
            raise ValueError(f"contract field {name} needs a real value")
        if name in VALUES and value not in VALUES[name]:
            raise ValueError(f"{name} must be one of {', '.join(VALUES[name])}")
        values[name] = value
        order.append(FIELDS.index(name))
    if order != sorted(order):
        raise ValueError("contract fields must follow the order: " + ", ".join(FIELDS))
    missing = [name for name in REQUIRED if name not in values]
    if missing:
        raise ValueError("contract is missing: " + ", ".join(missing))
    canonical = f"Contract: risk={values['risk']} quality={values['quality']} acceptance={values['acceptance']}"
    if not LINE.fullmatch(canonical):
        raise ValueError("contract acceptance must be a single real line")
    return canonical, {name: values[name] for name in ("topic", "budget", "skill") if name in values}


def declared_text(command):
    """The contract text of a pure declare command, None for any other command."""
    head, _, body = command.partition("\n")
    match = DECLARE.fullmatch(head)
    if not match:
        return None
    rest = match.group("rest")
    single = SINGLE.fullmatch(rest)
    if single and not body.strip():
        return single.group("text")
    heredoc = HEREDOC.fullmatch(rest)
    if not heredoc:
        raise ValueError("declare takes a single-quoted --contract or a quoted heredoc (<<'EOF')")
    lines = body.split("\n")
    word = heredoc.group("word")
    if word not in [line.strip() for line in lines]:
        raise ValueError(f"heredoc terminator {word} not found")
    end = [line.strip() for line in lines].index(word)
    if any(line.strip() for line in lines[end + 1:]):
        raise ValueError("nothing may follow a declare heredoc")
    return "\n".join(lines[:end])


class Store:
    """Per-checkout session records under the ignored runtime directory."""

    def __init__(self, root):
        self.directory = Path(root) / ".agent-runtime"
        self.path = self.directory / "contract-sessions.json"

    def __enter__(self):
        for path in (self.directory, self.path, self.directory / "contract-sessions.lock"):
            if path.is_symlink():
                raise ValueError("contract state must not cross a symlink boundary")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = (self.directory / "contract-sessions.lock").open("a")
        fcntl.flock(self.lock, fcntl.LOCK_EX)
        data = json.loads(self.path.read_text()) if self.path.exists() else {"schema": 1, "sessions": {}}
        if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("sessions"), dict):
            raise ValueError("contract state is malformed; delete .agent-runtime/contract-sessions.json to reset")
        self.sessions = data["sessions"]
        return self

    def save(self):
        newest = sorted(self.sessions.items(), key=lambda item: item[1].get("at", 0))[-MAX_SESSIONS:]
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"schema": 1, "sessions": dict(newest)}, indent=2) + "\n")
        temporary.replace(self.path)

    def __exit__(self, *error):
        self.lock.close()


def session_of(payload):
    session = payload.get("session_id")
    if not isinstance(session, str) or not session.strip() or "\n" in session:
        raise ValueError("hook input has no session_id")
    return session


def current(root, session):
    with Store(root) as store:
        record = store.sessions.get(session) or {}
    return record.get("contract")


def baseline(root, session, value=None):
    """Read, or with `value` record, the shipping state a session last left verified or found."""
    with Store(root) as store:
        record = store.sessions.setdefault(session, {})
        if value is None:
            return record.get("baseline")
        record.update({"baseline": value, "at": record.get("at", time.time())})
        store.save()
    return value


def pre_tool(root, payload):
    """Return None to allow, or the reason to deny."""
    session = session_of(payload)
    name = payload.get("tool_name")
    if not isinstance(name, str):
        raise ValueError("hook input has no tool_name")
    command = (payload.get("tool_input") or {}).get("command") if name == "Bash" else None
    if isinstance(command, str):
        try:
            text = declared_text(command)
        except ValueError as error:
            return f"Contract declaration rejected: {error}.\n{HELP}"
        if text is not None:
            try:
                contract, meta = parse(text)
            except ValueError as error:
                return f"Contract declaration rejected: {error}.\n{HELP}"
            with Store(root) as store:
                store.sessions.setdefault(session, {}).update(
                    {"contract": contract, "meta": meta, "at": time.time(),
                     "model": payload.get("model") if isinstance(payload.get("model"), str) else None})
                store.save()
            return None
    if name in READ_ONLY or name.startswith(READ_ONLY_PREFIXES):
        return None
    declared = current(root, session)
    if declared and isinstance(command, str) and not payload.get("agent_id") and records_own_receipt(command, declared):
        # The author's main thread never records the review of its own contract (REVIEW.md);
        # a reviewer subagent carries an agent_id, and a fresh reviewer session declares its own.
        return ("Lean contract guard: only the independent reviewer records the review receipt for this "
                "session's contract. Ask the reviewer to record it; if it cannot, report BLOCKED.")
    if declared:
        return None
    return f"Lean contract guard: no Task Contract is declared for this prompt, so `{name}` is blocked.\n{HELP}"


def records_own_receipt(command, declared):
    """Whether `command` runs `gate_evidence.py record-review` for `declared` (or a contract it cannot see).

    The command is parsed, so a contract that merely mentions the subcommand, or a quoted copy of
    the contract in another command, does not count; shell quoting of the contract does not hide it.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return bool(re.search(r"gate_evidence\.py\b.*\brecord-review\b", command, re.S))
    for index, token in enumerate(tokens):
        if not token.endswith("gate_evidence.py"):
            continue
        call = []
        for word in tokens[index + 1:]:
            if word in ("&&", "||", ";", "|", "&"):
                break
            call.append(word)
        if "record-review" not in call:
            continue
        contract = None
        for position, word in enumerate(call):
            if word == "--contract" and position + 1 < len(call):
                contract = call[position + 1]
            elif word.startswith("--contract="):
                contract = word.split("=", 1)[1]
        # An expanded or missing value cannot be compared; treat it as the session's own contract.
        if contract is None or "$" in contract or "`" in contract or contract == declared:
            return True
    return False


def prompt(root, payload):
    """A person's prompt starts a new task; runtime-injected prompts continue the current one."""
    session = session_of(payload)
    text = payload.get("prompt")
    if isinstance(text, str) and text.lstrip().startswith(RUNTIME_PROMPTS):
        return
    with Store(root) as store:
        record = store.sessions.get(session)
        if record and "contract" in record:
            for name in ("contract", "meta", "model"):
                record.pop(name, None)
            store.save()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pre-tool", help="PreToolUse hook: allow or deny from stdin JSON")
    commands.add_parser("prompt", help="UserPromptSubmit hook: clear the session's declaration")
    show = commands.add_parser("current", help="print the session's declared contract")
    show.add_argument("--session", required=True)
    declare = commands.add_parser("declare", help="validate a contract (the hook binds it to the session)")
    declare.add_argument("--contract", help="one-line contract; omit to read a block from stdin")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "declare":
            contract, meta = parse(args.contract if args.contract is not None else sys.stdin.read())
            print(contract + "".join(f"\n{name}: {value}" for name, value in meta.items()))
            return 0
        if args.command == "current":
            contract = current(root, args.session)
            if not contract:
                print("No Task Contract declared for this session", file=sys.stderr)
                return 1
            print(contract)
            return 0
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be a JSON object")
        if args.command == "prompt":
            prompt(root, payload)
            return 0
        reason = pre_tool(root, payload)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        # Fail closed: a guard that cannot decide blocks the tool (and reports why). A failed
        # prompt reset only warns; blocking would discard the person's prompt.
        print(f"Lean contract guard error: {error}", file=sys.stderr)
        return 1 if args.command == "prompt" else 2
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

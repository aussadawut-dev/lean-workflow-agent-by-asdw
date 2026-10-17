#!/usr/bin/env python3
"""Task Contract declarations shared by the Claude and Codex hooks.

The PreToolUse hook binds a session's contract from the first line of its reply
(read from the Claude transcript) or from a `declare` shell command, and denies
write-capable tools until one exists; a person's prompt clears it. These records catch
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
# Runtime-injected turns (task notices, agent hand-backs, hook feedback), sometimes wrapped in a
# system reminder, continue the current task; only a person's prompt clears the declaration.
RUNTIME_PROMPTS = ("<task-notification>", "<agent-message", "<cross-session-message", "<system-reminder>",
                   "[SYSTEM NOTIFICATION", "Stop hook feedback:")
MAX_SESSIONS = 64
HELP = ("Write the Task Contract as the first line of your reply, before any tool call; the guard reads it\n"
        "from the transcript. Without a readable transcript, declare it in a command of its own:\n"
        "python3 .lean/scripts/contract_guard.py declare --contract 'Contract: risk=LOW quality=STANDARD "
        "acceptance=<observable check>'\n"
        "(or a quoted heredoc with the block form). A new user prompt clears the declaration.")
TRANSCRIPT_WAIT = 1.0  # Seconds to re-read a transcript whose current reply may not be flushed yet.
TRANSCRIPT_TAIL = 4_000_000  # Bytes read from the end of a transcript; the current turn is near the end.


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


def text_of(content):
    """Plain text of a message body, or None when it carries tool results (not a prompt)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    if any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content):
        return None
    return "\n".join(block.get("text", "") for block in content
                     if isinstance(block, dict) and block.get("type") == "text")


def transcript_contract(path):
    """The contract that opens the reply to the latest person prompt in a Claude transcript, or None.

    Only the first non-empty assistant text after that prompt counts, so a contract written
    later in the reply, in an earlier turn or by a subagent (sidechain) never does. Runtime
    turns (hook feedback, notices, compaction summaries) and tool results continue the turn. Unreadable lines are skipped.
    """
    if not isinstance(path, str) or not path:
        return None
    try:
        with open(path, "rb") as source:
            source.seek(0, os.SEEK_END)
            size = source.tell()
            source.seek(max(0, size - TRANSCRIPT_TAIL))
            data = source.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    lines = data.splitlines()
    if size > TRANSCRIPT_TAIL:
        lines = lines[1:]  # The first line may be cut.
    prompt_seen, first = False, None
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if (not isinstance(entry, dict) or entry.get("isSidechain") or entry.get("isMeta")
                or entry.get("isCompactSummary")):
            continue
        message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
        if entry.get("type") == "user":
            text = text_of(message.get("content"))
            if text is not None and text.strip() and not text.lstrip().startswith(RUNTIME_PROMPTS):
                prompt_seen, first = True, None
        elif entry.get("type") == "assistant" and prompt_seen and first is None:
            content = message.get("content")
            blocks = [content] if isinstance(content, str) else content if isinstance(content, list) else []
            for block in blocks:
                text = block if isinstance(block, str) else block.get("text") if (
                    isinstance(block, dict) and block.get("type") == "text") else None
                if isinstance(text, str) and text.strip():
                    first = text
                    break
    if first is None:
        return None
    try:
        return parse(first.strip().split("\n\n", 1)[0])
    except ValueError:
        return None


def bind_transcript(root, session, payload):
    """Bind the contract that opens the reply (Claude transcript) to the session; return it or None."""
    path = payload.get("transcript_path")
    found = transcript_contract(path)
    # Claude can persist the reply's text a moment after PreToolUse starts for a tool in the same
    # response (observed: present on a re-read 0.1s later), so re-read briefly before denying.
    deadline = time.monotonic() + TRANSCRIPT_WAIT
    while not found and isinstance(path, str) and os.path.isfile(path) and time.monotonic() < deadline:
        time.sleep(0.05)
        found = transcript_contract(path)
    if not found:
        return None
    with Store(root) as store:
        store.sessions.setdefault(session, {}).update(
            {"contract": found[0], "meta": found[1], "source": "transcript", "at": time.time(),
             "model": payload.get("model") if isinstance(payload.get("model"), str) else None})
        store.save()
    return found[0]


# Shell reads allowed before a contract: one simple command or a pipeline of them, no redirection,
# chaining, expansion or newline. Git takes only these subcommands, given directly (no `-c` options).
READ_COMMANDS = {"grep", "cat", "head", "tail", "wc", "ls"}
READ_GIT = {"status", "diff", "log", "show", "ls-files", "rev-parse", "blame"}
WRITING_OPTIONS = ("--output", "--ext-diff", "--textconv")


def read_only_shell(command):
    """Whether a shell command only reads, by a conservative allowlist (unknown means no)."""
    if not command.strip() or any(mark in command for mark in ("\n", "\r", "$", "`")):
        return False
    words = shell_words(command)
    if not words:
        return False
    parts, current = [], []
    for word in words:
        if word == "|":
            parts.append(current)
            current = []
        elif any(mark in word for mark in ";&|<>()"):
            # shlex keeps runs such as `>&`, `&>` or `>|` as one token, so refuse any
            # operator character outside a lone pipe (a quoted one only costs a declaration).
            return False
        else:
            current.append(word)
    parts.append(current)
    for part in parts:
        if not part or any(word.startswith(WRITING_OPTIONS) for word in part):
            return False
        if part[0] == "git":
            if len(part) < 2 or part[1] not in READ_GIT:
                return False
        elif part[0] not in READ_COMMANDS:
            return False
    return True


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
    if writes_receipt(name, payload.get("tool_input") or {}):
        # Only gate_evidence.py writes the receipt, so its state and contract checks always apply.
        return ("Lean contract guard: the review receipt is written only by the reviewer through "
                "gate_evidence.py, never edited directly. If the reviewer cannot record it, report BLOCKED.")
    if name in READ_ONLY or name.startswith(READ_ONLY_PREFIXES):
        return None
    if isinstance(command, str) and read_only_shell(command):
        return None  # A plain read changes nothing, so it needs no contract yet.
    # Bind a transcript contract before any check that depends on the session's contract.
    declared = current(root, session) or bind_transcript(root, session, payload)
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else root
    if (declared and isinstance(command, str) and not payload.get("agent_id")
            and records_own_receipt(command, declared, cwd)):
        # The author's main thread never records the review of its own contract (REVIEW.md);
        # a reviewer subagent carries an agent_id, and a fresh reviewer session declares its own.
        return ("Lean contract guard: only the independent reviewer records the review receipt for this "
                "session's contract. Ask the reviewer to record it; if it cannot, report BLOCKED.")
    if declared:
        return None
    return f"Lean contract guard: no Task Contract is declared for this prompt, so `{name}` is blocked.\n{HELP}"


OPERATORS = set(";&|<>()") | {"&&", "||", ";;", "|&", ">>", "<<", "<<<"}


def shell_words(command):
    """Shell words with operators as their own tokens (`'x';echo` gives three), or None if unparseable."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


# Text unique to gate_evidence.py, so a renamed or copied script is still recognised.
GATE_MARKER = '("record-review", ' + '"check-review")'  # Split so this file is not mistaken for one.
RECEIPT = ".agent-runtime/review.json"
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch"}


WRITERS = {"cp", "mv", "ln", "install", "tee", "dd", "rsync", "touch", "truncate"}
COPIERS = {"cp", "mv", "ln", "install", "rsync"}


def simple_commands(words):
    """Split shell words into simple commands at operators."""
    command = []
    for word in words:
        if word in OPERATORS:
            yield command
            command = []
        else:
            command.append(word)
    yield command


def writes_receipt(name, tool_input):
    """Whether a tool call writes the receipt file itself (mentioning or reading it is fine).

    A heuristic: redirect targets and writer arguments are checked, so a write through a path the
    guard cannot see (`cd .agent-runtime && echo > review.json`) is not caught.
    """
    if not isinstance(tool_input, dict):
        return False
    if name in EDIT_TOOLS - {"apply_patch"}:
        return any(str(tool_input.get(key, "")).endswith(RECEIPT) for key in ("file_path", "notebook_path", "path"))
    command = tool_input.get("command")
    if not isinstance(command, str) or RECEIPT not in command:
        return False
    if name == "apply_patch":
        return any(line.startswith("*** ") and "File:" in line and line.rstrip().endswith(RECEIPT)
                   for line in command.splitlines())
    if name != "Bash":
        return False
    words = shell_words(command)
    if words is None:
        return True  # Unparseable and naming the receipt: refuse rather than guess.
    for index, word in enumerate(words[:-1]):
        if word in (">", ">>", ">|") and words[index + 1].endswith(RECEIPT):
            return True
    for command_words in simple_commands(words):
        if not command_words:
            continue
        tool = Path(command_words[0]).name
        targets = any(word.endswith(RECEIPT) for word in command_words[1:])
        if targets and (tool in WRITERS or (tool == "sed" and any(w.startswith("-i") for w in command_words))):
            return True
        if any(RECEIPT in word and re.search(r"open\([^)]*['\"][wax]|write_(text|bytes)\(", word)
               for word in command_words):
            return True
    return False


def gate_tool(word, cwd, previous=""):
    """Whether a word names gate_evidence: by name, through a path the guard cannot read, or a copy.

    A copy is recognised by content when it is a .py file or the script python runs, so a renamed
    or extension-less copy that already exists still counts.
    """
    if "gate_evidence" in word or "$" in word or "`" in word:
        return True
    if cwd is None or not (word.endswith(".py") or Path(previous).name.startswith("python")):
        return False
    path = Path(word) if Path(word).is_absolute() else Path(cwd) / word
    try:
        return path.is_file() and path.stat().st_size < 1_000_000 and GATE_MARKER in path.read_text(errors="ignore")
    except OSError:
        return False


def records_own_receipt(command, declared, cwd=None, depth=0):
    """Whether `command` runs `record-review` for `declared`, or for a contract the guard cannot read.

    A receipt call is a standalone `record-review` word with gate_evidence (by name, a hidden path,
    or a copy) earlier in the same simple command, or in a later `xargs` command of the same
    pipeline (`echo record-review | xargs python3 gate_evidence.py`). A command that also copies
    or links gate_evidence counts, since the copy does not exist yet when the guard runs. Any
    other argument that itself holds a command mentioning it (`sh -c`, `bash -lc`, here-strings,
    `echo ... | sh`, `eval`) is checked the same way; the `--contract` value and the contract text
    itself are data, not commands. A call passes only with a literal `--contract` value that
    differs from the declared contract.
    """
    words = shell_words(command)
    if words is None or depth > 3:
        return "record-review" in command
    values = [words[index + 1] for index, word in enumerate(words[:-1]) if word == "--contract"]
    values += [word.split("=", 1)[1] for word in words if word.startswith("--contract=")]
    for word in words:
        # A word (or a --contract= value) whose only mention of record-review is inside the declared
        # contract text is data, such as a commit message quoting it. Anything else that mentions it
        # may run under a wrapper (`eval "--contract=x; ..."`), so it is parsed as a command.
        candidate = word.split("=", 1)[1] if word.startswith("--contract=") else word
        if "record-review" not in candidate.replace(declared, ""):
            continue
        # Re-parsing a single word yields itself: a path or pattern such as record-review.txt is
        # not a call, and a bare record-review word is left to the standalone check below.
        if candidate == word and not any(c.isspace() for c in word):
            continue
        if records_own_receipt(candidate, declared, cwd, depth + 1):
            return True
    standalone = "record-review" in words
    copies = any(command_words and Path(command_words[0]).name in COPIERS
                 and any("gate_evidence" in word for word in command_words[1:])
                 for command_words in simple_commands(words))
    # `grep -rn record-review gate_evidence.py` only searches: the word comes before the tool in the
    # same simple command. Across a pipe only xargs turns input into the tool's arguments.
    called = standalone and copies
    tool = in_pipeline = in_segment = xargs = False
    previous = ""
    for word in words:
        if word == "|":
            in_pipeline, in_segment, tool, xargs = in_pipeline or in_segment, False, False, False
        elif word in OPERATORS:
            in_pipeline = in_segment = tool = xargs = False
        elif word == "record-review":
            called = called or tool
            in_segment = True
        elif Path(word).name == "xargs":
            xargs = True
        elif gate_tool(word, cwd, previous):
            tool = True
            called = called or (in_pipeline and xargs)
        previous = word
    if not called:
        return False
    if not values or declared in command:
        return True
    return any(value == declared or "$" in value or "`" in value or value in OPERATORS for value in values)


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


GUARD = ".lean/scripts/contract_guard.py"


def repairs_guard(payload):
    """While the guard is broken, allow read-only tools and edits that repair or restore the guard file."""
    name = payload.get("tool_name")
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    if not isinstance(name, str):
        return False
    if name in READ_ONLY or name.startswith(READ_ONLY_PREFIXES):
        return True
    if name in EDIT_TOOLS - {"apply_patch"}:
        return str(tool_input.get("file_path", "")).endswith(GUARD)
    command = tool_input.get("command")
    if not isinstance(command, str):
        return False
    if name == "apply_patch":
        files = [line for line in command.splitlines() if line.startswith("*** ") and "File:" in line]
        return bool(files) and all(line.rstrip().endswith(GUARD) for line in files)
    words = shell_words(command) or []
    restores = name == "Bash" and words[:2] in (["git", "checkout"], ["git", "restore"])
    # The guard path itself (relative or absolute, plain characters only), so no expansion runs.
    plain = re.compile(r"(?:/[\w./-]*/|\./)?" + re.escape(GUARD))
    return restores and all(word in ("git", "checkout", "restore", "--", "--staged") or plain.fullmatch(word)
                            for word in words)


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
        try:
            reason = pre_tool(root, payload)
        except Exception as error:  # A guard bug, not a decision: keep the guard repairable.
            if repairs_guard(payload):
                print(f"Lean contract guard crashed ({error!r}); allowing this read or guard repair.",
                      file=sys.stderr)
                return 0
            print(f"Lean contract guard crashed: {error!r}. Repair {GUARD} (edits to it stay allowed), or "
                  f"restore it with `git checkout -- {GUARD}`.", file=sys.stderr)
            return 2
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

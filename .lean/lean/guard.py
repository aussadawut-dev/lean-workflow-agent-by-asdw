"""Task Contract guard shared by the Claude and Codex hooks.

The PreToolUse hook binds a session's contract from the first line of its reply
(read from the Claude transcript) or from a `lean contract declare` command, and denies
write-capable tools until one exists; a person's prompt clears it, except a Claude prompt typed
while the agent is still working. These records catch mistakes; they are not a security boundary.
"""
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

from .util import RUNTIME

LINE = re.compile(r"Contract: (?:risk=(LOW|MEDIUM|HIGH) quality=(STANDARD|HIGH|VERY_HIGH) acceptance=([^<\s].*)"
                  r"|trivial \(([^<].*)\))\Z")
FIELDS = ("topic", "risk", "quality", "budget", "skill", "acceptance")
REQUIRED = ("risk", "quality", "acceptance")
VALUES = {"risk": ("LOW", "MEDIUM", "HIGH"), "quality": ("STANDARD", "HIGH", "VERY_HIGH"),
          "budget": ("CHEAP", "BALANCED", "EXPENSIVE")}
# Tools that cannot change files by themselves; they never consult the contract. Any other tool
# runs too, unless it is an edit tool or a shell command that writes (see shell_writes).
READ_ONLY = {"Read", "Glob", "Grep", "LS", "NotebookRead", "WebFetch", "WebSearch", "ToolSearch", "Skill",
             "AskUserQuestion", "TodoWrite", "Agent", "Task", "SendMessage", "ListAgents", "EnterPlanMode",
             "ExitPlanMode", "update_plan", "view_image", "web_search", "request_user_input"}
READ_ONLY_PREFIXES = ("collaboration",)  # Codex subagent spawn, wait and messaging tools.
# A declaration is a whole command: optional `cd <dir> &&`, then the declare call with a
# single-quoted --contract or a quoted heredoc, so no shell expansion or chained command runs.
DECLARE = re.compile(r"\s*(?:cd\s+(?:\"[^\"$`\\]*\"|'[^']*'|[\w./~-]+)\s*&&\s*)?(?:python3\s+)?"
                     r"(?:\"(?:[^\"$`\\]*/)?\.lean/bin/lean\"|'(?:[^']*/)?\.lean/bin/lean'"
                     r"|(?:\"\$CLAUDE_PROJECT_DIR\"/|\$CLAUDE_PROJECT_DIR/|[\w./~-]*?)\.lean/bin/lean)"
                     r"\s+contract\s+declare(?P<rest>.*)\Z")
SINGLE = re.compile(r"\s+--contract\s+'(?P<text>[^'\n]*)'\s*\Z")
HEREDOC = re.compile(r"\s*<<-?\s*(?P<quote>['\"])(?P<word>\w+)(?P=quote)\s*\Z")
# Runtime-injected turns (task notices, agent hand-backs, hook feedback), sometimes wrapped in a
# system reminder, continue the current task; only a person's prompt clears the declaration
# (a Claude prompt typed mid-turn continues it too; see still_working).
RUNTIME_PROMPTS = ("<task-notification>", "<agent-message", "<cross-session-message", "<system-reminder>",
                   "[SYSTEM NOTIFICATION", "Stop hook feedback:")
MAX_SESSIONS = 64
HELP = ("Write the Task Contract as the first line of your reply, before any tool call; the guard reads it\n"
        "from the transcript once a tool result has arrived. Reads and inspection run without a contract;\n"
        "only write tools and writing shell commands wait for it. When the turn's first tool call writes\n"
        "(or the guard cannot read a transcript, as in Codex), declare it first in a command of its own:\n"
        "python3 .lean/bin/lean contract declare --contract 'Contract: risk=LOW quality=STANDARD "
        "acceptance=<observable check>'\n"
        "(or a quoted heredoc with the block form). A new user prompt clears the declaration; in Claude,\n"
        "one typed while the agent is still working keeps it.")
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
        self.directory = Path(root) / RUNTIME
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


def declaration_bound(root, contract, environment=None):
    """Whether a `lean contract declare` of `contract` is bound, as far as the calling runtime can show.

    Only Claude's shell (CLAUDECODE=1) runs the guard's hook before every command, which binds a pure
    declare first; there, a contract that no session holds was not bound (a shell variable, a pipe or
    a preceding command). Other runtimes (Codex without trust, agy) only validate. Reads the store
    without creating it; malformed records are skipped."""
    environment = os.environ if environment is None else environment
    if environment.get("CLAUDECODE") != "1":
        return True
    path = Path(root) / RUNTIME / "contract-sessions.json"
    try:
        sessions = json.loads(path.read_text()).get("sessions") if not path.is_symlink() else None
    except (OSError, ValueError, AttributeError):
        sessions = None
    if not isinstance(sessions, dict):
        return False
    return any(isinstance(record, dict) and record.get("contract") == contract for record in sessions.values())


def baseline(root, session, value=None):
    """Read, or with `value` record, the shipping state a session last left verified or found."""
    with Store(root) as store:
        record = store.sessions.setdefault(session, {})
        if value is None:
            return record.get("baseline")
        record.update({"baseline": value, "at": record.get("at", time.time())})
        store.save()
    return value


def start_session(root, session, value):
    """Keep the original commit boundary across resumes and later verified-state updates."""
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", "HEAD"],
                          capture_output=True, text=True)
    with Store(root) as store:
        record = store.sessions.setdefault(session, {})
        record.setdefault("baseline", value)
        record.setdefault("initial_head", head.stdout.strip() if head.returncode == 0 else "")
        record.setdefault("at", time.time())
        store.save()


def initial_head(root, session):
    """The session's immutable original HEAD; empty means it began before the first commit."""
    with Store(root) as store:
        return (store.sessions.get(session) or {}).get("initial_head")


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
    log_contract(root, found[0], "transcript")
    return found[0]


def log_contract(root, contract, source):
    try:
        from . import activity  # Imported here: a broken log module must not decide a tool call.
        activity.record(root, "contract", contract=contract, source=source)
    except Exception:  # noqa: BLE001 - logging never decides a tool call.
        pass


def pre_tool(root, payload):
    """Return None to allow, or the reason to deny."""
    session = session_of(payload)
    name = payload.get("tool_name")
    if not isinstance(name, str):
        raise ValueError("hook input has no tool_name")
    tool_input = payload.get("tool_input") or {}
    # Any shell-like tool carries its text as `command`; edit tools carry a patch or content there.
    command = tool_input.get("command") if name not in EDIT_TOOLS else None
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
            log_contract(root, contract, "declared")
            return None
    if writes_receipt(name, tool_input):
        # Only gate_evidence.py writes the receipt, so its state and contract checks always apply.
        return ("Lean contract guard: the review receipt is written only by the reviewer through "
                "`lean evidence record-review`, never edited directly. If the reviewer cannot record it, "
                "report BLOCKED.")
    if writes_receipt(name, tool_input, PENDING):
        return ("Lean contract guard: the review-pending marker is written only by "
                "`lean gate review-pending --contract ... --session ...`, never edited directly.")
    if name in READ_ONLY or name.startswith(READ_ONLY_PREFIXES):
        return None
    # Only write tools and writing shell commands wait for the contract; the Stop gate still refuses
    # changed work without one, so reads, inspection and tools the guard does not know run first.
    # A command whose parsed words mention record-review is a write and takes the receipt check
    # whatever the heuristic says: a renamed copy of gate_evidence.py looks like any other script.
    words = shell_words(command) if isinstance(command, str) else []
    mentions_receipt = isinstance(command, str) and (words is None or any("record-review" in w for w in words))
    writing = name in EDIT_TOOLS or mentions_receipt or (isinstance(command, str) and shell_writes(command))
    if not writing:
        return None
    # Bind a transcript contract before any check that depends on the session's contract.
    declared = current(root, session) or bind_transcript(root, session, payload)
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else root
    if (declared and mentions_receipt and not payload.get("agent_id")
            and records_own_receipt(command, declared, cwd)):
        # The author's main thread never records the review of its own contract (REVIEW.md);
        # a reviewer subagent carries an agent_id, and a fresh reviewer session declares its own.
        return ("Lean contract guard: only the independent reviewer records the review receipt for this "
                "session's contract. Ask the reviewer to record it; if it cannot, report BLOCKED.")
    if declared:
        return None
    return (f"Lean contract guard: no Task Contract is declared for this prompt, so this writing `{name}` call "
            f"is blocked.\n{HELP}")


OPERATORS = set(";&|<>()") | {"&&", "||", ";;", "|&", ">>", "<<", "<<<"}


def shell_words(command):
    """Shell words with operators as their own tokens (`'x';echo` gives three), or None if unparseable."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""  # Bash reads `a#` as a word, so `#` must not hide what follows.
        return list(lexer)
    except ValueError:
        return None


# Text unique to the evidence command, so a renamed or copied script is still recognised.
GATE_MARKER = '("record-review", ' + '"check-review")'  # Split so this file is not mistaken for one.
RECEIPT = RUNTIME + "/review.json"
PENDING = RUNTIME + "/review-pending.json"  # Written only by `lean gate review-pending`.
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


# Shell commands that write, by a best-effort pattern over the parsed words. Reads and inspection
# run before a contract; the Stop gate still refuses changed work that has no contract, so this
# check only makes the contract come before the first write. Unparseable text, a command named by
# an expansion (`eval "$cmd"`, `$tool x`), a backtick, a shell reading commands from stdin, `sudo`,
# `npx` and `wget` count as writes; runners (`eval`, `sh -c`, `xargs`, `env`) are judged by the
# command they run. An unlisted interpreter, tool or script, a write hidden in a heredoc body fed
# to anything but a shell, or a path hidden behind `cd` is not caught, and a quoted `>` reads as a
# redirection.
READ_GIT = {"status", "diff", "log", "show", "ls-files", "rev-parse", "blame", "describe", "rev-list", "cat-file",
            "ls-tree", "ls-remote", "grep", "shortlog", "for-each-ref", "merge-base", "name-rev",
            "check-ignore", "diff-tree", "diff-index", "count-objects", "var", "version", "help"}
# Read only in some forms. `git reflog`: its first word decides (`expire`, `delete`, `drop`, `write` rewrite the
# log; `show`, `list`, `exists` or a ref name read). `git symbolic-ref`: one name and only the options below read;
# anything else (a second name, `-d` alone, bundled as `-qd` or abbreviated as `--del`) may change a ref.
REFLOG_WRITES = {"expire", "delete", "drop", "write"}
SYMBOLIC_REF_READ_OPTIONS = {"-q", "--quiet", "--short", "--recurse", "--no-recurse"}
GIT_LISTERS = {"branch", "tag", "remote", "stash", "worktree", "config"}  # List or change, by argument.
GIT_LIST_FLAGS = {"-l", "--list", "-a", "-r", "--all", "--remotes", "--contains", "--no-contains", "--merged",
                  "--no-merged", "--points-at", "--show-current", "-v", "-vv", "--verbose", "-n"}
GIT_CHANGERS = {"-d", "-D", "-m", "-M", "-c", "-C", "-u", "-f", "-F", "-s", "-e", "--delete", "--move", "--copy",
                "--force", "--annotate", "--sign", "--set-upstream-to", "--unset-upstream", "--edit-description",
                "--track", "add", "rm", "remove", "rename", "set-url", "set-head", "set-branches", "prune", "update",
                "push", "pop", "drop", "apply", "clear", "create", "unset", "--unset", "--unset-all", "--add",
                "--replace-all", "--edit", "--rename-section", "--remove-section", "lock", "unlock", "move", "repair"}
GIT_OUTPUT_OPTIONS = ("--output", "--ext-diff", "--textconv")
WRITE_COMMANDS = WRITERS | {"rm", "rmdir", "mkdir", "chmod", "chown", "chgrp", "patch", "apply_patch", "make", "sudo",
                            "npx", "wget"}
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "}", "coproc", "function", "()"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
RUNNERS = {"xargs", "env", "nohup", "time", "nice", "command", "builtin"}
INSTALLERS = {"npm", "pnpm", "yarn", "pip", "pip3", "uv", "cargo", "go", "brew"}
INSTALL_WORDS = {"install", "i", "ci", "add", "remove", "rm", "uninstall", "publish", "init", "update", "upgrade", "build"}
PIP_MODULES = {"pip", "pip3", "uv", "pipx"}
MODULE_WRITES = {"venv", "ensurepip", "build", "twine"}
CONTAINER_READS = {"ps", "images", "logs", "inspect", "version", "info", "stats", "top", "port", "diff", "history",
                   "events", "search"}
INTERPRETERS = {"python", "python2", "python3", "node", "ruby", "perl", "php"}
INLINE_WRITE = re.compile(r"open\([^,)]*,\s*['\"][rbt+]*[wax]|mode\s*=\s*['\"][rbt+]*[wax]|\.write_(text|bytes)\("
                          r"|os\.(remove|unlink|rename|replace|makedirs|mkdir|rmdir|chmod|system)\(|subprocess\."
                          r"|shutil\.|\.(unlink|rmdir|mkdir|touch)\(|writeFile(Sync)?\(|fs\.(rm|unlink|rename|mkdir)")
FILE_REDIRECTS = {">", ">>", ">|", ">>|", "&>", "&>>"}
DEV_SINKS = {"/dev/null", "/dev/stderr", "/dev/stdout", "/dev/tty"}
# A `w`/`W` command writes the file that follows it: after the start, an address, `!`, `;` or `{`
# (with or without a space before the name), or as an `s///` flag after other flags (with a space).
SED_WRITE = re.compile(r"(?:^|[;{}!0-9$])\s*[wW](?:\s+\S|/)|[/,][gpiImMe0-9]*[wW]\s+\S")
# Options that take the next word as their value, so it is not the command a runner runs.
RUNNER_VALUES = {"xargs": {"-I", "-J", "-R", "-S", "-n", "-P", "-L", "-s", "-d", "-E", "-a", "--max-args", "--max-lines",
                           "--max-procs", "--max-chars", "--delimiter", "--arg-file", "--eof", "--replace"},
                 "env": {"-u", "-C", "--unset", "--chdir"}, "nice": {"-n", "--adjustment"},
                 "time": {"-f", "-o", "--format", "--output"}}
ENV_COMMAND_LINE = ("-S", "--split-string")  # env runs this value as a command line.
SHELL_VALUED = {"-o", "+o", "-O", "+O"}  # Shell options whose next word is an option name, not a script.
PERL_VALUED = ("-M", "-m", "-I", "-e", "-E", "-x", "-C")  # Their letters are not switches.
# `lean` command groups: True only reads (or writes ignored runtime state such as progress),
# a set names the subcommands that only read, and a group missing here writes.
LEAN_READS = {"status": True, "watch": True, "progress": True, "test": True, "lint": True,
              "models": {"list", "check", "bank"},  # `apply` writes models.json; `eval` writes results.
              "log": True,
              "attribution": True, "hook": True, "version": True,
              "contract": {"declare", "current"}, "mode": {"show", "check", "context"},
              "queue": {"list", "history"}, "evidence": {"state", "gate-state", "check-review", "check-shipped",
                                                         "high-risk"},
              "gate": {"run", "status", "mode"}, "spawn": {"plan"}, "update": {"preview"},
              "target": {"context", "gate", "use"}}
LEAN_DEFAULT_READS = {"models"}  # Groups whose bare call only prints (`lean models` lists the sizes).
LEAN_VALUE_WRITES = {"effort": {"standard", "high", "ultra", "reset"}, "lint": {"--write-registry"},
                     "target": {"--apply", "clear"}, "log": {"--export"},
                     "gate": {"auto", "manual", "auto_fixloop", "manual_fixloop", "accept-controls"}}


def unknown_word(word):
    """Whether a word's value is decided only when the shell runs it: an expansion or a glob."""
    return any(mark in word for mark in "$`*?[")


def git_writes(args):
    """Whether a git command changes state: a subcommand outside the read set, or a lister with changing arguments."""
    index = 0
    while index < len(args) and args[index].startswith("-"):
        if args[index].startswith("-c"):
            return True  # `-c core.pager=...` runs a program.
        index += 2 if args[index] in ("-C", "--git-dir", "--work-tree", "--namespace") else 1
    if index >= len(args):
        return False
    sub, rest = args[index], args[index + 1:]
    if any(word.startswith(GIT_OUTPUT_OPTIONS) for word in rest):
        return True
    if sub in READ_GIT:
        return False
    if sub == "reflog":
        words = [word for word in rest if not word.startswith("-")]
        return bool(words) and (words[0] in REFLOG_WRITES or unknown_word(words[0]))
    if sub == "symbolic-ref":
        names = [word for word in rest if not word.startswith("-")]
        options = [word for word in rest if word.startswith("-")]
        return (len(names) != 1 or unknown_word(names[0])
                or any(word not in SYMBOLIC_REF_READ_OPTIONS for word in options))
    if sub not in GIT_LISTERS or any(word in GIT_CHANGERS for word in rest):
        return True
    positional = [word for word in rest if not word.startswith("-")]
    if sub == "stash":
        return not positional or positional[0] not in ("list", "show")
    if sub == "worktree":
        return not positional or positional[0] != "list"
    if sub == "remote":
        return bool(positional) and positional[0] not in ("show", "get-url")
    if sub == "config":
        return not any(word in ("--get", "--get-all", "--get-regexp", "--list", "-l") for word in rest)
    return bool(positional) and not any(word in GIT_LIST_FLAGS for word in rest)  # branch, tag


def lean_cli(word):
    """Whether a word names the Lean command line (by path or bare name)."""
    return word == "lean" or word.endswith("/bin/lean") or word == ".lean/bin/lean"


def lean_writes(rest):
    """Whether a `lean` call changes records or settings (an unknown group does)."""
    while rest[:1] in (["--root"], ["--workflow-root"]):
        rest = rest[2:]
    if not rest:
        return False  # Usage text.
    group, words = rest[0], rest[1:]
    if group in LEAN_VALUE_WRITES:
        if any(word.split("=", 1)[0] in LEAN_VALUE_WRITES[group] for word in words):
            return True
        if group == "effort":
            return False
    reads = LEAN_READS.get(group)
    if reads is True:
        return False
    if reads is None:
        return True
    positional, skip = [], False
    for word in words:
        if skip:
            skip = False
        elif word == "--root":
            skip = True  # Its value is a path, not a subcommand.
        elif not word.startswith("-"):
            positional.append(word)
    if not positional:
        return group not in LEAN_DEFAULT_READS
    return positional[0] not in reads


def redirect_writes(words):
    """An output redirection to a file; descriptor duplication (`2>&1`, `>&-`) and device sinks are not."""
    for index, word in enumerate(words):
        target = words[index + 1] if index + 1 < len(words) else ""
        if word in FILE_REDIRECTS and target not in DEV_SINKS:
            return True
        if word == ">&" and target and not target.isdigit() and target != "-" and target not in DEV_SINKS:
            return True
    return False


def quoted_substitutions(words):
    """Command substitutions kept inside quoted words: `echo "$(rm x)"` runs rm."""
    for word in words:
        for marker in ("$(", "<(", ">("):
            start = word.find(marker)
            if start != -1:
                end = word.rfind(")")
                yield word[start + 2:end if end > start else len(word)]


def nested_writes(name, args, raw, depth):
    """The command a runner runs, after its options and their values: `xargs -I % rm %` runs rm."""
    if name == "command" and any(word in ("-v", "-V") for word in args):
        return False  # A lookup, not a run.
    takes, index = RUNNER_VALUES.get(name, set()), 0
    while index < len(args) and args[index].startswith("-"):
        word = args[index]
        if word == "--":
            index += 1
            break
        if name == "env" and word.split("=", 1)[0] in ENV_COMMAND_LINE:
            line = word.split("=", 1)[1] if "=" in word else (args[index + 1] if index + 1 < len(args) else "")
            return shell_writes(line, depth + 1)
        index += 2 if word in takes else 1
    return command_writes(args[index:], raw, depth + 1)


def command_writes(words, raw, depth=0):
    """Whether one simple command writes; `raw` is the whole command text, for inline interpreter code."""
    if depth > 3:
        return True
    while words and (words[0] in KEYWORDS or ("=" in words[0] and not words[0].startswith(("-", "=")))):
        # Shell keywords and leading environment assignments; `function NAME` also drops the name.
        words = words[2:] if words[0] == "function" else words[1:]
    while len(words) >= 2 and words[1] == "()":
        words = words[2:]  # A POSIX `NAME() { ... }` definition: the body follows.
        while words and words[0] in KEYWORDS:
            words = words[1:]
    if not words:
        return False
    if words[0].startswith("$"):
        return True  # A command named by an expansion is invisible.
    name, args = (words[0] if words[0] == "." else Path(words[0]).name), words[1:]
    positional = [word for word in args if not word.startswith("-")]
    if lean_cli(words[0]):
        return lean_writes(args)
    if name in WRITE_COMMANDS or (name in INSTALLERS and any(word in INSTALL_WORDS for word in args)):
        return True
    if name == "yarn":
        return not args  # Bare yarn installs.
    if name in ("docker", "podman"):
        return not positional or positional[0] not in CONTAINER_READS
    if name == "unzip":
        return not any(word in ("-l", "-t", "-Z", "-z") for word in args)
    if name == "tar":  # Extract, create, append or update, as a long option or in any short cluster.
        return bool(args) and (any(word.startswith(("--extract", "--create", "--append", "--update", "--delete"))
                                   or re.fullmatch(r"-[a-zA-Z]*[xcru][a-zA-Z]*", word) for word in args)
                               or bool(re.match(r"[a-zA-Z]*[xcru]", args[0])))
    if name == "curl":
        return any(word.startswith(("--output", "--remote-name")) or re.match(r"-[a-zA-Z]*[oO]", word) for word in args)
    if name in SHELLS:
        nested = next((args[i + 1] for i, word in enumerate(args[:-1])
                       if word.startswith("-") and not word.startswith("--") and "c" in word[1:]), None)
        if nested is not None:
            return shell_writes(nested, depth + 1)
        # Without -c or a script, or with -s, the shell runs commands from stdin, which the guard cannot see.
        script, index = None, 0
        while index < len(args):
            word = args[index]
            if word in SHELL_VALUED:
                index += 2
                continue
            if not word.startswith(("-", "+")):
                script = word
                break
            index += 1
        return script is None or any("s" in word[1:] for word in args if word.startswith("-") and not word.startswith("--"))
    if name in ("eval", "exec", "source", "."):
        return shell_writes(" ".join(args), depth + 1)
    if name in RUNNERS:
        return nested_writes(name, args, raw, depth)
    if name == "git":
        return git_writes(args)
    if name == "perl":
        return any(word.startswith("--in-place") or (re.match(r"-[0-9a-zA-Z]*i", word)
                                                     and not word.startswith(PERL_VALUED)) for word in args)
    if name == "sed":
        # The script is the -e values, or else the first positional word; the rest are file names.
        scripts = [args[i + 1] for i, word in enumerate(args[:-1]) if word in ("-e", "--expression")]
        scripts = scripts or positional[:1]
        return (any(word.startswith(("--in-place", "-f", "--file")) or re.match(r"-[a-zA-Z]*i", word) for word in args)
                or any(SED_WRITE.search(script) for script in scripts))
    if name == "find":
        return any(word.startswith(("-delete", "-exec", "-ok", "-fprint", "-fls", "-rm", "-fdelete")) for word in args)
    if name == "sort":
        return any(word.startswith("--output") or re.match(r"-[a-zA-Z]*o", word) for word in args)
    if name in INTERPRETERS:
        if INLINE_WRITE.search(raw):
            return True
        if "-m" in args[:-1]:
            module = args[args.index("-m") + 1]
            if module in MODULE_WRITES or (module in PIP_MODULES and any(word in INSTALL_WORDS for word in args)):
                return True
        script = positional[0] if positional else ""
        if lean_cli(script):
            return lean_writes(args[args.index(script) + 1:])
        if ".lean/lean/" in script:
            return True  # A module run directly bypasses the command map.
    return False


def shell_writes(command, depth=0):
    """Whether a shell command writes, by a best-effort pattern (unparseable or invisible means yes)."""
    if depth > 3 or "`" in command:
        return True
    terminator = None
    for line in command.splitlines():
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue  # A heredoc body is data; inline interpreter code is checked on the whole text.
        words = shell_words(line)
        if words is None or redirect_writes(words):
            return True
        for index, word in enumerate(words[:-1]):
            if word in ("<<", "<<-"):
                terminator = words[index + 1].lstrip("-")
        if any(command_writes(list(part), command, depth) for part in simple_commands(words)):
            return True
        if any(shell_writes(inner, depth + 1) for inner in quoted_substitutions(words)):
            return True
    return False


def writes_receipt(name, tool_input, target=RECEIPT):
    """Whether a tool call writes the receipt file (or another runtime `target`) itself; mentioning or reading it is fine.

    A heuristic: redirect targets and writer arguments are checked, so a write through a path the
    guard cannot see (`cd .agent-runtime && echo > review.json`) is not caught.
    """
    if not isinstance(tool_input, dict):
        return False
    if name in EDIT_TOOLS - {"apply_patch"}:
        return any(str(tool_input.get(key, "")).endswith(target) for key in ("file_path", "notebook_path", "path"))
    command = tool_input.get("command")
    if not isinstance(command, str) or target not in command:
        return False
    if name == "apply_patch":
        return any(line.startswith("*** ") and "File:" in line and line.rstrip().endswith(target)
                   for line in command.splitlines())
    if name != "Bash":
        return False
    words = shell_words(command)
    if words is None:
        return True  # Unparseable and naming the receipt: refuse rather than guess.
    for index, word in enumerate(words[:-1]):
        if word in (">", ">>", ">|") and words[index + 1].endswith(target):
            return True
    for command_words in simple_commands(words):
        if not command_words:
            continue
        tool = Path(command_words[0]).name
        targets = any(word.endswith(target) for word in command_words[1:])
        if targets and (tool in WRITERS or (tool == "sed" and any(w.startswith("-i") for w in command_words))):
            return True
        if any(target in word and re.search(r"open\([^)]*['\"][wax]|write_(text|bytes)\(", word)
               for word in command_words):
            return True
    return False


def gate_tool(word, cwd, previous=""):
    """Whether a word names gate_evidence: by name, through a path the guard cannot read, or a copy.

    A copy is recognised by content when it is a .py file or the script python runs, so a renamed
    or extension-less copy that already exists still counts.
    """
    if "gate_evidence" in word or "evidence.py" in word or lean_cli(word) or "$" in word or "`" in word:
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
                 and any("gate_evidence" in word or "evidence.py" in word or lean_cli(word)
                         for word in command_words[1:])
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


TURN_END = "turn_duration"  # Written once a turn finishes; stop_hook_summary also follows a Stop that blocks.


def moment(entry):
    """A transcript entry's timestamp in epoch seconds, or None when it has none."""
    try:
        return datetime.fromisoformat(str(entry.get("timestamp")).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def still_working(path, since):
    """Whether a Claude transcript shows the turn whose contract was bound at `since` still running.

    Claude runs UserPromptSubmit for a prompt typed while the agent works before recording that
    prompt anywhere, then delivers it mid-turn with no user entry of its own. A prompt that starts a
    turn is recorded as a user entry before its hook runs, an interrupt leaves a user entry and a
    finished turn a turn_duration entry, so any of them after the binding means a new task. Any
    doubt (no transcript, no Claude assistant entry, an entry without a time) counts as a new task.
    """
    if not isinstance(path, str) or not path or not isinstance(since, (int, float)):
        return False
    try:
        with open(path, "rb") as source:
            source.seek(0, os.SEEK_END)
            size = source.tell()
            source.seek(max(0, size - TRANSCRIPT_TAIL))
            data = source.read().decode("utf-8", errors="replace")
    except OSError:
        return False
    lines = data.splitlines()
    if size > TRANSCRIPT_TAIL:
        lines = lines[1:]  # The first line may be cut.
    claude = False  # Codex rollouts have no assistant entries, so a Codex prompt always starts a task.
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("isSidechain"):
            continue
        claude = claude or (entry.get("type") == "assistant" and isinstance(entry.get("message"), dict))
        boundary = entry.get("type") == "system" and entry.get("subtype") == TURN_END
        if entry.get("type") == "user" and not entry.get("isMeta"):
            message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
            words = text_of(message.get("content"))
            boundary = bool(words and words.strip() and not words.lstrip().startswith(RUNTIME_PROMPTS))
        if boundary:
            when = moment(entry)
            if when is None or when >= since:
                return False
    return claude


def prompt(root, payload):
    """A person's prompt starts a new task; runtime-injected prompts continue the current one.

    So does a Claude prompt typed while the agent is still working: the contract bound in that turn
    stands, and the agent declares again only if the prompt changes the task (see still_working).
    """
    session = session_of(payload)
    text = payload.get("prompt")
    if isinstance(text, str) and text.lstrip().startswith(RUNTIME_PROMPTS):
        return
    with Store(root) as store:
        record = store.sessions.get(session)
        if record and "contract" in record:
            if still_working(payload.get("transcript_path"), record.get("at")):
                return
            for name in ("contract", "meta", "model"):
                record.pop(name, None)
            store.save()


GUARD = ".lean/lean/guard.py"


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


def hook(root, event, stdin):
    """Run the PreToolUse (`pre-tool`) or UserPromptSubmit (`prompt`) hook; return (exit code, message)."""
    try:
        payload = json.loads(stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be a JSON object")
        if event == "prompt":
            prompt(root, payload)
            return 0, ""
        try:
            reason = pre_tool(root, payload)
        except Exception as error:  # A guard bug, not a decision: keep the guard repairable.
            if repairs_guard(payload):
                return 0, f"Lean contract guard crashed ({error!r}); allowing this read or guard repair."
            return 2, (f"Lean contract guard crashed: {error!r}. Repair {GUARD} (edits to it stay allowed), or "
                       f"restore it with `git checkout -- {GUARD}`.")
    except (OSError, ValueError, TypeError, AttributeError) as error:
        # Fail closed: a guard that cannot decide blocks the tool (and reports why). A failed
        # prompt reset only warns; blocking would discard the person's prompt.
        return (1 if event == "prompt" else 2), f"Lean contract guard error: {error}"
    return (2, reason) if reason else (0, "")

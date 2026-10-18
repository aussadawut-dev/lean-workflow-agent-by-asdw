"""Task Contract declarations, the shared PreToolUse guard and both providers' Stop checks."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".lean/scripts"))
import contract_guard  # noqa: E402

DECLARE = "python3 .lean/scripts/contract_guard.py declare"
BLOCK = "Contract:\ntopic: guard\nrisk: LOW\nquality: STANDARD\nbudget: CHEAP\nacceptance: tests pass"
LINE = "Contract: risk=LOW quality=STANDARD acceptance=tests pass"
FILES = (".gitignore", ".lean/scripts/contract_guard.py", ".lean/scripts/gate_evidence.py", ".lean/scripts/gate_lock.py",
         ".lean/scripts/gate_mode.py", ".lean/scripts/quality-gate.sh", ".claude/hooks/quality-gate.sh",
         ".claude/settings.json", ".codex/hooks.json", ".codex/hooks/quality_gate.py")


def stop_refusal(result):
    """Claude's Stop adapter refuses with a JSON decision block on exit 0; read it as exit 2 + reason."""
    try:
        data = json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else None
    except ValueError:
        data = None
    if isinstance(data, dict) and data.get("decision") == "block":
        return subprocess.CompletedProcess(result.args, 2, "", result.stderr + data["reason"])
    return result


class ParseTests(unittest.TestCase):
    def test_one_line_trivial_and_block_forms(self):
        self.assertEqual(contract_guard.parse(LINE), (LINE, {}))
        self.assertEqual(contract_guard.parse("Contract: trivial (typo)")[0], "Contract: trivial (typo)")
        self.assertEqual(contract_guard.parse(BLOCK + "\n\nPlan follows: edit x.\nrisk: ignored"),
                         (LINE, {"topic": "guard", "budget": "CHEAP"}))
        self.assertEqual(contract_guard.parse("Contract:\nRisk: HIGH\nquality: HIGH\nacceptance: a b")[0],
                         "Contract: risk=HIGH quality=HIGH acceptance=a b")

    def test_rejects_placeholders_unknown_duplicate_missing_and_misordered_fields(self):
        bad = ["", "Contract: risk=<LOW|MEDIUM|HIGH> quality=<STANDARD> acceptance=<check>", "Plan: x",
               "Contract:\nrisk: LOW\nquality: STANDARD\nacceptance: <observable check>",
               "Contract:\nrisk: LOW\nquality: STANDARD\nmodel: x\nacceptance: ok",
               "Contract:\nrisk: LOW\nrisk: HIGH\nquality: STANDARD\nacceptance: ok",
               "Contract:\nrisk: LOW\nquality: STANDARD",
               "Contract:\nquality: STANDARD\nrisk: LOW\nacceptance: ok",
               "Contract:\nrisk: SEVERE\nquality: STANDARD\nacceptance: ok",
               "Contract:\nrisk LOW\nquality: STANDARD\nacceptance: ok"]
        for text in bad:
            with self.assertRaises(ValueError, msg=text):
                contract_guard.parse(text)


class DeclareCommandTests(unittest.TestCase):
    def test_accepts_single_quoted_and_quoted_heredoc_forms(self):
        self.assertEqual(contract_guard.declared_text(f"{DECLARE} --contract '{LINE}'"), LINE)
        heredoc = f"{DECLARE} <<'EOF'\n{BLOCK}\nEOF\n"
        self.assertEqual(contract_guard.declared_text(heredoc), BLOCK)
        for prefix in ('cd "/tmp/a b" && python3', "python3", 'python3 "$CLAUDE_PROJECT_DIR"/', "python3 /abs/"):
            command = f"{prefix} .lean/scripts/contract_guard.py declare <<\"END\"\n{BLOCK}\nEND"
            command = command.replace("/ .lean", "/.lean")
            self.assertEqual(contract_guard.declared_text(command), BLOCK, command)

    def test_other_commands_are_not_declarations_and_unsafe_forms_are_rejected(self):
        for command in ("ls", "python3 .lean/scripts/gate_evidence.py state", "echo declare"):
            self.assertIsNone(contract_guard.declared_text(command))
        for command in (f"{DECLARE} --contract '{LINE}' && rm -rf build",
                        f"{DECLARE} --contract \"{LINE}\"",
                        f"{DECLARE} <<EOF\n{BLOCK}\nEOF",
                        f"{DECLARE} <<'EOF'\n{BLOCK}\nEOF\ntouch x",
                        f"{DECLARE} <<'EOF'\n{BLOCK}\n",
                        f"{DECLARE} --contract '{LINE}'\ntouch x"):
            with self.assertRaises(ValueError, msg=command):
                contract_guard.declared_text(command)
        self.assertIsNone(contract_guard.declared_text(
            f"python3 $(touch pwned).lean/scripts/contract_guard.py declare --contract '{LINE}'"))


class ShellWriteTests(unittest.TestCase):
    def test_reads_inspection_chains_loops_and_other_tools_are_not_writes(self):
        for command in ("grep -n -i regression .lean/policy/TESTING.md", "cat a.py | head -5", "ls -la src",
                        "git status --short", "git diff", "git log --oneline -3", "git show HEAD:a.py | tail -n 20",
                        "rg -n 'def state' .lean/scripts", "sed -n 26,58p gate.py", "find . -name '*.py' -type f",
                        "sort -u names.txt", "grep -n x a.py && sed -n 3,9p a.py", "ls src; git status --short",
                        'cd /tmp && echo hi; for f in a b; do cat "$f"; done', 'x=$(git rev-parse HEAD); echo "$x"',
                        "python3 .lean/scripts/workflow.py show", "python3 .lean/scripts/workflow.py context",
                        "python3 .lean/scripts/gate_evidence.py --root . state", "python3 .lean/scripts/model_drift.py",
                        "python3 -m unittest discover -s .lean/tests", "python3 .lean/tests/run_tests.py",
                        "python3 .lean/scripts/clean_repo.py", "python3 .lean/scripts/skill_effort.py",
                        "cat a 2>&1 | head", "ls > /dev/null", "cat a 2>/dev/null", "echo x >&2", "git branch -r",
                        "git -C sub status", "git --no-pager log -1", "git tag -l 'v*'", "git remote -v",
                        "git stash list", "git config --get user.name", "git worktree list", "git diff -M",
                        "bash .lean/scripts/quality-gate.sh", "./script.sh --flag", "(cat a)", "cat a &",
                        "grep 'a#b' f", "rg --hostname-bin=./h.sh x f", "find d -name v", "sed 1p f", "sed -n -e 1p f",
                        "sort -T /tmp f", "sort -rn -k2 f", "python3 -c 'print(open(\"f\").read())'",
                        "env | grep PATH", "time grep x f", "X=1 cat f", "xargs grep x", "npm test", "go test ./...",
                        "cargo test", "perl -ne print f", "cat <<'EOF'\nhello\nEOF", "",
                        # Review round 1: quoted substitutions, descriptor duplication, device sinks, keywords,
                        # heredoc bodies, anchored open() modes, listing subcommands of tools that also write.
                        'x="$(git rev-parse HEAD)"', 'echo "$(git status --short)"', "cmd >&2", "cmd 2>&1", "cmd >&-",
                        "ls > /dev/stderr", "if grep -q x f; then echo yes; fi", "for f in a b; do cat $f; done",
                        "python3 -c \"print(open('a.txt').read())\"", "cat <<'EOF'\ndon't\nEOF",
                        "python3 - <<'PY'\n# don't\nprint(1)\nPY", "docker ps", "docker logs x", "curl -s url",
                        "curl -sS -X POST url", "tar tf a.tgz", "unzip -l a.zip", "yarn test", "python3 -m pip list",
                        "python3 -m unittest discover", "bash -c 'echo $HOME'", "sed -n 1p work.txt", "sed 's/x/y/' f",
                        "time grep x f", "xargs -n 1 grep x", "brew list"):
            self.assertFalse(contract_guard.shell_writes(command), command)

    def test_writes_runners_installers_and_invisible_commands_are_writes(self):
        receipt_call = "python3 .lean/scripts/gate_evidence.py " + "record-" + "review --verdict PASS"
        for command in ("cat a > b", "echo x >> f", "cat a >| f", "cat a &> f", "grep x f | tee out", "head f 1> y",
                        "cmd 2> err.log", "sed -i '' s/a/b/ f", "sed -ni 1p f", "sed --in-place s/a/b/ f",
                        "perl -pi -e s/a/b/ f", "perl -i.bak -ne print f", "rm -f x", "rm -rf build", "mkdir d",
                        "touch x", "cp a b", "mv a b", "chmod +x f", "patch -p1", "/bin/rm x", "git commit -m x",
                        "git add .", "git push", "git checkout -- f", "git -c core.pager=cat log", "git branch feature",
                        "git tag v1", "git tag -d v1", "git remote add o url", "git stash", "git stash pop",
                        "git config user.name x", "git worktree add ../w", "git fetch", "git reset --hard",
                        "git diff --output=x", "git log --ext-diff", "python3 -c \"open('x','w').write('y')\"",
                        "python3 - <<'PY'\nfrom pathlib import Path\nPath('x').write_text('y')\nPY",
                        "node -e \"require('fs').writeFileSync('x','y')\"",
                        "python3 .lean/scripts/workflow.py configure tracker",
                        "python3 .lean/scripts/gate_evidence.py accept-controls --reason x", receipt_call,
                        "python3 .lean/scripts/skill_pack.py enable", "python3 .lean/scripts/clean_repo.py --apply",
                        "python3 .lean/scripts/skill_effort.py high", "python3 .lean/scripts/unknown.py",
                        'eval "$cmd"', "bash -c 'cat a > b'", "sh -lc 'touch y'",
                        "exec tee f", "env FOO=1 tee f", "nohup tee f", "xargs rm", "sudo ls", "npm install x",
                        "pip install x", "go build ./...", "make", "cat a; rm b", "cat a && touch b",
                        "cat a || touch b", "cat a\nrm b", "ls $(touch x)", "cat `touch x`", "find . -delete",
                        "find . -exec rm {} +", "find d -name v -rm", "sort -o out f", "sort -uo out f",
                        "sort --output=out f", "cat a#; rm -rf x", "cat 'open",
                        # Review round 1: keywords hiding a writer, quoted substitutions, >& to a file, zsh >>|,
                        # pip modules, brew, bare yarn, npx, docker, downloads, archives, perl digits, runner
                        # option values, sed w, other inline writers, commands named by an expansion.
                        "for f in a b; do cp $f /tmp; done", "if true; then rm x; fi", "{ rm x; }", "! rm x",
                        "while true; do touch x; done", 'echo "$(rm -rf x)"', 'echo "$(git commit -m x)"',
                        "cmd >& out.log", "cmd >&out", "cmd >>| f", "python3 -m pip install x", "python -m pip install x",
                        "python3 -m venv .venv", "brew install jq", "yarn", "npx prettier --write .", "docker run x",
                        "curl -o f url", "curl -sSLO url", "wget url", "tar xf a.tgz", "tar -czf out.tgz dir",
                        "unzip a.zip", "perl -0pi -e s/a/b/ f", "xargs -I % rm %", "env -u X rm f", "nice -n 5 rm x",
                        "sed -n '1w out' f", "sed 's/a/b/w out' f", "sed -f script.sed f",
                        "python3 -c \"import os; os.system('rm x')\"",
                        "python3 -c \"from pathlib import Path; Path('x').unlink()\"", "$cmd arg",
                        '"$HOME/bin/rm" x', "${EDITOR} f"):
            self.assertTrue(contract_guard.shell_writes(command), command)


class HookFixture(unittest.TestCase):
    """Run hooks exactly as each provider's configured command does, in a disposable checkout."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean contract guard ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def hook(self, provider, event, payload):
        if provider == "claude":
            config = json.loads((self.root / ".claude/settings.json").read_text())
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        else:
            config = json.loads((self.root / ".codex/hooks.json").read_text())
            env = dict(os.environ)
        command = config["hooks"][event][0]["hooks"][0]["command"]
        return subprocess.run(["sh", "-c", command], cwd=self.root, env=env, input=json.dumps(payload),
                              text=True, capture_output=True)

    def tool(self, provider, name, session="s1", **tool_input):
        return self.hook(provider, "PreToolUse", {"session_id": session, "tool_name": name, "tool_input": tool_input,
                                                   "hook_event_name": "PreToolUse", "model": "model-x"})

    def prompt(self, provider, text, session="s1"):
        return self.hook(provider, "UserPromptSubmit", {"session_id": session, "prompt": text})



class GuardHookTests(HookFixture):
    def test_both_providers_deny_writes_until_declared_then_reset_on_a_person_prompt(self):
        for provider, write, shell in (("claude", ("Edit", {"file_path": "x.py"}), "Bash"),
                                       ("codex", ("apply_patch", {"command": "*** Begin Patch"}), "Bash")):
            with self.subTest(provider=provider):
                session = f"{provider}-session"
                denied = self.tool(provider, write[0], session, **write[1])
                self.assertEqual(denied.returncode, 2, denied.stderr)
                self.assertIn("declare", denied.stderr)
                self.assertEqual(self.tool(provider, shell, session, command="touch x").returncode, 2)
                self.assertEqual(self.tool(provider, "Read", session, file_path="x.py").returncode, 0)
                declared = self.tool(provider, shell, session, command=f"{DECLARE} <<'EOF'\n{BLOCK}\nEOF")
                self.assertEqual(declared.returncode, 0, declared.stderr)
                self.assertEqual(self.tool(provider, write[0], session, **write[1]).returncode, 0)
                self.assertEqual(self.tool(provider, shell, session, command="touch x").returncode, 0)
                # A subagent shares the session and its declaration.
                self.assertEqual(self.hook(provider, "PreToolUse", {
                    "session_id": session, "agent_id": "a1", "tool_name": shell,
                    "tool_input": {"command": "python3 -m unittest"}}).returncode, 0)
                # Another session is still blocked.
                self.assertEqual(self.tool(provider, write[0], "other", **write[1]).returncode, 2)
                self.assertEqual(self.prompt(provider, "<task-notification>done</task-notification>",
                                             session).returncode, 0)
                # Runtime notices wrapped in a system reminder are not a person's prompt either.
                self.assertEqual(self.prompt(provider, "<system-reminder>\n[SYSTEM NOTIFICATION - NOT USER INPUT]\n"
                                             "<task-notification>done</task-notification>", session).returncode, 0)
                self.assertEqual(self.prompt(provider, "Stop hook feedback:\nGate evidence: refused", session).returncode, 0)
                self.assertEqual(self.tool(provider, write[0], session, **write[1]).returncode, 0)
                self.assertEqual(self.prompt(provider, "Next task please", session).returncode, 0)
                self.assertEqual(self.tool(provider, write[0], session, **write[1]).returncode, 2)

    def test_only_a_subagent_or_another_session_records_the_review_of_a_declared_contract(self):
        record = ("python3 .lean/scripts/gate_evidence.py record-review --contract '{}' --reviewer r "
                  "--evidence e --verdict PASS --state abc")
        for provider in ("claude", "codex"):
            with self.subTest(provider=provider):
                session = f"{provider}-author"
                self.assertEqual(self.tool(provider, "Bash", session,
                                           command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
                author = self.tool(provider, "Bash", session, command=record.format(LINE))
                self.assertEqual(author.returncode, 2, author.stderr)
                self.assertIn("independent reviewer", author.stderr)
                reviewer = self.hook(provider, "PreToolUse", {
                    "session_id": session, "agent_id": "reviewer-1", "tool_name": "Bash",
                    "tool_input": {"command": record.format(LINE)}})
                self.assertEqual(reviewer.returncode, 0, reviewer.stderr)
                # A fresh reviewer session declares its own (review) contract and may record.
                fresh = f"{provider}-reviewer"
                self.assertEqual(self.tool(provider, "Bash", fresh,
                                           command=f"{DECLARE} --contract 'Contract: trivial (review)'").returncode, 0)
                self.assertEqual(self.tool(provider, "Bash", fresh, command=record.format(LINE)).returncode, 0)

    def test_receipt_calls_take_the_receipt_check_whatever_the_write_heuristic_says(self):
        # Review round 1: a quoted word, a cd into the scripts directory and a dotted path all name a receipt
        # call that the write heuristic alone would read as a plain script. (The word is split so that
        # writing this file is not itself mistaken for a receipt call.)
        word = "record-" "review"
        plain = ("python3 .lean/scripts/gate_evidence.py WORD --contract '{}' --reviewer r "
                 "--evidence e --verdict PASS --state abc").replace("WORD", word)
        forms = (plain.replace(word, word.replace("review", '"review"')),
                 plain.replace("python3 .lean/scripts/", "cd .lean/scripts && python3 "),
                 plain.replace(".lean/scripts/", ".lean/tests/../scripts/"))
        for command in forms:  # Without a contract every form is a write and waits for one.
            denied = self.tool("claude", "Bash", "no-contract", command=command.format(LINE))
            self.assertEqual(denied.returncode, 2, command)
            self.assertIn("declare", denied.stderr)
        self.assertEqual(self.tool("claude", "Bash", "author", command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        for command in forms:  # With the author's contract declared, each reaches the own-receipt check.
            denied = self.tool("claude", "Bash", "author", command=command.format(LINE))
            self.assertEqual(denied.returncode, 2, command)
            self.assertIn("independent reviewer", denied.stderr)
        # A read that merely mentions the word runs once a contract exists.
        self.assertEqual(self.tool("claude", "Bash", "author", command="grep -rn " + word + " .lean").returncode, 0)

    def test_receipt_check_parses_the_command_instead_of_matching_text(self):
        mentions = "Contract: risk=HIGH quality=HIGH acceptance=the author cannot record-review its own work"
        session = "parse-session"
        self.assertEqual(self.tool("claude", "Bash", session, command=f"{DECLARE} --contract '{mentions}'").returncode, 0)
        # Commands that only quote the contract are not receipt recordings.
        for command in (f"bash .lean/scripts/quality-gate.sh --require-review --contract '{mentions}'",
                        f"python3 .lean/scripts/gate_evidence.py check-review --contract '{mentions}'",
                        f"echo '{mentions}'"):
            result = self.tool("claude", "Bash", session, command=command)
            self.assertEqual(result.returncode, 0, (command, result.stderr))
        # The contract as data inside a longer word, or as a --contract= value, is not a recording.
        for command in (f"git commit -m 'fix: {mentions}'",
                        f"bash .lean/scripts/quality-gate.sh --contract='{mentions}' --require-review"):
            self.assertFalse(contract_guard.records_own_receipt(command, mentions), command)
        # A single word that only contains the subcommand name is a path or pattern, not a call.
        for command in ("cat record-review.txt", "grep -rn record-review .lean/policy", "ls record-review/x"):
            self.assertFalse(contract_guard.records_own_receipt(command, mentions), command)
        # A nested recording of that contract is still one, including one hidden behind a
        # --contract= or --contract word that a wrapper evaluates (review of 4c609b7).
        nested = f"python3 .lean/scripts/gate_evidence.py record-review --contract '{mentions}' --state s"
        for command in (f"bash -lc {json.dumps(nested)}", f"eval {json.dumps('--contract=x; ' + nested)}",
                        f"bash -c {json.dumps('--contract=x; ' + nested)}",
                        f"eval --contract {json.dumps('x; ' + nested)}"):
            self.assertTrue(contract_guard.records_own_receipt(command, mentions), command)
        # Shell quoting that changes the text still names the same contract.
        apostrophe = "Contract: risk=LOW quality=STANDARD acceptance=the author's tests pass"
        quoted = apostrophe.replace("'", "'\\''")
        self.assertEqual(self.tool("codex", "Bash", "quote-session", command=f"{DECLARE} <<'EOF'\n{apostrophe}\nEOF").returncode, 0)
        for command in (f"python3 .lean/scripts/gate_evidence.py --root . record-review --contract '{quoted}' --state s",
                        f'python3 .lean/scripts/gate_evidence.py record-review --contract "{apostrophe}" --state s',
                        f"python3 .lean/scripts/gate_evidence.py record-review --contract='{quoted}'"):
            result = self.tool("codex", "Bash", "quote-session", command=command)
            self.assertEqual(result.returncode, 2, command)
        # Shell syntax glued to the contract, wrappers and subshells still name it (review round 1).
        base = f"python3 .lean/scripts/gate_evidence.py record-review --contract '{quoted}'"
        for command in (base + ";echo done", base + "&&echo done", base + ">/dev/null", f"({base})",
                        f'bash -c "{base.replace(chr(34), "")}"', f"sh -c {json.dumps(base)}",
                        "python3 .lean/scripts/gate_evidence.py state&&" + base,
                        # Review round 2: option bundles, options before -c, here-strings and pipes.
                        f"bash -lc {json.dumps(base)}", f"bash -ec {json.dumps(base)}",
                        f"bash --norc -c {json.dumps(base)}", f"bash <<< {json.dumps(base)}",
                        f"echo {json.dumps(base)} | sh", f"eval {json.dumps(base)}"):
            self.assertTrue(contract_guard.records_own_receipt(command, apostrophe), command)
        # Another command on the line is not part of the receipt call.
        self.assertFalse(contract_guard.records_own_receipt(
            f"python3 .lean/scripts/gate_evidence.py state; echo '{apostrophe}'", apostrophe))
        # A contract hidden behind expansion cannot be compared, so the author's thread may not record at all.
        hidden = self.tool("codex", "Bash", "quote-session",
                           command='python3 .lean/scripts/gate_evidence.py record-review --contract "$(cat c.txt)"')
        self.assertEqual(hidden.returncode, 2)

    def test_receipt_guard_catches_copies_pipelines_and_direct_receipt_writes(self):
        session = "evasion-session"
        self.assertEqual(self.tool("codex", "Bash", session, command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        copy = self.root / "tools/ge.py"
        copy.parent.mkdir()
        shutil.copy2(self.root / ".lean/scripts/gate_evidence.py", copy)
        for command in (f"python3 tools/ge.py record-review --contract '{LINE}' --state s",
                        f"python3 {shlex.quote(str(copy))} record-review --contract '{LINE}' --state s",
                        f"echo record-review | xargs python3 .lean/scripts/gate_evidence.py --contract '{LINE}'"):
            self.assertTrue(contract_guard.records_own_receipt(command, LINE, self.root), command)
            self.assertEqual(self.tool("codex", "Bash", session, command=command).returncode, 2, command)
        # A copy only counts when it is one; searching the real script stays allowed.
        (self.root / "notes.py").write_text("print('record-review notes')\n")
        for command in (f"python3 notes.py record-review --contract '{LINE}'",
                        "grep -rn record-review .lean/scripts/gate_evidence.py"):
            self.assertFalse(contract_guard.records_own_receipt(command, LINE, self.root), command)
        # The receipt file is written only by record-review, never by an edit tool or a shell write.
        receipt = ".agent-runtime/review.json"
        for provider, name, tool_input in (("claude", "Write", {"file_path": f"{self.root}/{receipt}"}),
                                           ("claude", "Edit", {"file_path": receipt}),
                                           ("codex", "apply_patch", {"command": f"*** Update File: {receipt}"}),
                                           ("codex", "Bash", {"command": f"cp fake.json {receipt}"}),
                                           ("codex", "Bash", {"command": f"echo '{{}}' > {receipt}"})):
            with self.subTest(name=name, tool_input=tool_input):
                result = self.hook(provider, "PreToolUse", {"session_id": session, "tool_name": name,
                                                            "tool_input": tool_input, "agent_id": "a1"})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("review receipt", result.stderr)
        self.assertEqual(self.tool("codex", "Bash", session, command=f"cat {receipt}").returncode, 0)
        # Review round 1: copy-and-run in one command, extension-less copies, reads with redirects
        # and an unrelated pipeline.
        for command in (f"cp .lean/scripts/gate_evidence.py g && python3 g record-review --contract '{LINE}'",
                        f"ln -s .lean/scripts/gate_evidence.py /tmp/g.py; python3 /tmp/g.py record-review --contract '{LINE}'"):
            self.assertTrue(contract_guard.records_own_receipt(command, LINE, self.root), command)
        shutil.copy2(copy, self.root / "tools/ge")
        self.assertTrue(contract_guard.records_own_receipt(
            f"python3 tools/ge record-review --contract '{LINE}'", LINE, self.root))
        self.assertFalse(contract_guard.records_own_receipt(
            "grep record-review notes.txt | python3 .lean/scripts/gate_evidence.py state", LINE, self.root))
        for command in (f"grep x {receipt} 2>&1", f"cat {receipt} 2>/dev/null", f"python3 -m json.tool {receipt} > out.json"):
            self.assertFalse(contract_guard.writes_receipt("Bash", {"command": command}), command)
        for command in (f"tee {receipt} < x", f"sed -i '' s/a/b/ {receipt}", f"printf x >> {receipt}"):
            self.assertTrue(contract_guard.writes_receipt("Bash", {"command": command}), command)
        # Text that only mentions the receipt path is not a write to it.
        for name, tool_input in (("Edit", {"file_path": "CHANGELOG.md", "new_string": f"Never edit `{receipt}`."}),
                                 ("Bash", {"command": f"git commit -m 'refuse writes to {receipt} > now'"}),
                                 ("Bash", {"command": f"python3 -c \"import json; print(json.load(open('{receipt}')))\""}),
                                 ("apply_patch", {"command": f"*** Update File: NOTES.md\n+mentions {receipt}"})):
            with self.subTest(allowed=name):
                result = self.hook("codex", "PreToolUse", {"session_id": session, "tool_name": name,
                                                           "tool_input": tool_input})
                self.assertEqual(result.returncode, 0, result.stderr)
        sneaky = f"python3 -c \"open('{receipt}', 'w').write('{{}}')\""
        self.assertEqual(self.tool("codex", "Bash", session, command=sneaky).returncode, 2)

    def test_a_crashing_guard_still_allows_repairing_itself(self):
        guard = self.root / ".lean/scripts/contract_guard.py"
        guard.write_text(guard.read_text().replace("    session = session_of(payload)\n    name =",
                                                   "    session = session_of(payload)\n    undefined_name\n    name =", 1))
        for provider in ("claude", "codex"):
            with self.subTest(provider=provider):
                blocked = self.tool(provider, "Bash", command="ls")
                self.assertEqual(blocked.returncode, 2, blocked.stderr)
                self.assertIn("contract guard crashed", blocked.stderr)
                for name, tool_input in (("Read", {"file_path": "x.py"}),
                                         ("Edit", {"file_path": str(guard)}),
                                         ("Bash", {"command": "git checkout -- .lean/scripts/contract_guard.py"}),
                                         ("apply_patch", {"command": "*** Update File: .lean/scripts/contract_guard.py"})):
                    result = self.tool(provider, name, **tool_input)
                    self.assertEqual(result.returncode, 0, (name, result.stderr))
                self.assertEqual(self.tool(provider, "Edit", file_path="app.py").returncode, 2)
                # Review round 1: repair mode takes the guard path itself, not a word that ends with it.
                expanded = "git checkout -- $(touch pwned).lean/scripts/contract_guard.py"
                self.assertEqual(self.tool(provider, "Bash", command=expanded).returncode, 2)

    def transcript(self, *entries):
        """A Claude-style JSONL transcript: ("user", text|blocks) or ("assistant", text, sidechain?)."""
        lines = []
        for entry in entries:
            kind, body = entry[0], entry[1]
            sidechain = len(entry) > 2 and entry[2]
            if kind == "assistant":
                content = [{"type": "text", "text": body}] if isinstance(body, str) else body
            else:
                content = body
            lines.append(json.dumps({"type": kind, "isSidechain": sidechain,
                                     "message": {"role": kind, "content": content}}))
        path = self.root / f"transcript-{len(list(self.root.glob('transcript-*')))}.jsonl"
        path.write_text("\n".join(lines) + "\n")
        return str(path)

    def edit_with(self, transcript, session="t1"):
        return self.hook("claude", "PreToolUse", {"session_id": session, "tool_name": "Edit",
                                                  "tool_input": {"file_path": "x.py"}, "transcript_path": transcript})

    def test_reads_inspection_and_other_tools_run_before_a_contract_but_writes_do_not(self):
        for command in ("grep -n x README.md", "cd /tmp && echo hi; for f in a; do cat $f; done",
                        "python3 .lean/scripts/workflow.py show", "x=$(git rev-parse HEAD); echo $x"):
            self.assertEqual(self.tool("claude", "Bash", "ro", command=command).returncode, 0, command)
        self.assertEqual(self.tool("codex", "Bash", "ro", command="git status --short").returncode, 0)
        self.assertEqual(self.tool("claude", "mcp__pencil__execute", "ro", script="x").returncode, 0)
        self.assertEqual(self.tool("claude", "Agent", "ro", prompt="review").returncode, 0)
        for name, tool_input in (("Bash", {"command": "grep -n x README.md > out.txt"}),
                                 ("Bash", {"command": "git commit -m x"}), ("Write", {"file_path": "x.py"}),
                                 ("NotebookEdit", {"notebook_path": "n.ipynb"})):
            denied = self.tool("claude", name, "ro", **tool_input)
            self.assertEqual(denied.returncode, 2, (name, denied.stderr))
            self.assertIn("declare", denied.stderr)
            self.assertNotIn("non-read", denied.stderr)

    def test_contract_written_first_in_the_reply_counts_as_the_declaration(self):
        tool_use = [{"type": "tool_use", "id": "u1", "name": "Read", "input": {}}]
        result = [{"type": "tool_result", "tool_use_id": "u1", "content": "file"}]
        allowed = self.edit_with(self.transcript(("user", "Fix the bug"), ("assistant", f"{LINE}\n\nI'll look."),
                                                 ("assistant", tool_use), ("user", result)))
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        record = json.loads((self.root / ".agent-runtime/contract-sessions.json").read_text())["sessions"]["t1"]
        self.assertEqual((record["contract"], record["source"]), (LINE, "transcript"))
        # The block form and a trivial contract count the same way.
        block = self.edit_with(self.transcript(("user", "Do x"), ("assistant", BLOCK + "\n\nPlan.")), "t2")
        self.assertEqual(block.returncode, 0, block.stderr)
        # Runtime turns (hook feedback, notices) continue the task; they do not start a new one.
        runtime = self.edit_with(self.transcript(
            ("user", "Typo please"), ("assistant", "Contract: trivial (typo)"),
            ("user", "Stop hook feedback:\nGate evidence: refused"),
            ("user", [{"type": "text", "text": "<task-notification>done</task-notification>"}])), "t3")
        self.assertEqual(runtime.returncode, 0, runtime.stderr)

    def test_transcript_bound_contract_still_blocks_the_authors_own_receipt(self):
        # Review round 1: binding from the transcript must happen before the own-receipt check.
        path = self.transcript(("user", "High task"), ("assistant", f"{LINE}\n\nWorking."))
        record = (f"python3 .lean/scripts/gate_evidence.py record-review --contract '{LINE}' --reviewer r "
                  "--evidence e --verdict PASS --state abc")
        base = {"session_id": "r1", "tool_name": "Bash", "tool_input": {"command": record}, "transcript_path": path}
        own = self.hook("claude", "PreToolUse", base)
        self.assertEqual(own.returncode, 2, own.stderr)
        self.assertIn("independent reviewer", own.stderr)
        reviewer = self.hook("claude", "PreToolUse", {**base, "agent_id": "rev"})
        self.assertEqual(reviewer.returncode, 0, reviewer.stderr)

    def test_compaction_summary_and_meta_entries_do_not_start_a_turn(self):
        path = Path(self.transcript(("user", "Fix it"), ("assistant", LINE)))
        extra = [{"type": "user", "isCompactSummary": True, "message": {"role": "user", "content": "Summary of chat"}},
                 {"type": "user", "isMeta": True, "message": {"role": "user", "content": "Caveat: local command"}}]
        path.write_text(path.read_text() + "".join(json.dumps(entry) + "\n" for entry in extra))
        allowed = self.edit_with(str(path), "c1")
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_contract_flushed_just_after_the_hook_starts_still_counts(self):
        # Claude may persist the reply's text a moment after it runs PreToolUse for a tool in the same response.
        path = Path(self.transcript(("user", "Typo please")))
        config = json.loads((self.root / ".claude/settings.json").read_text())
        command = config["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        payload = {"session_id": "late", "tool_name": "Edit", "tool_input": {"file_path": "x.py"},
                   "transcript_path": str(path)}
        process = subprocess.Popen(["sh", "-c", command], cwd=self.root, text=True, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root)))
        process.stdin.write(json.dumps(payload))
        process.stdin.close()
        time.sleep(0.3)
        with path.open("a") as output:
            output.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Contract: trivial (typo)"}]}}) + "\n")
        self.assertEqual(process.wait(timeout=10), 0, process.stderr.read())

    def test_unsaved_reply_denial_says_to_declare_before_a_first_write(self):
        # Claude may not save the reply's text until a tool result arrives, so a turn whose first tool
        # call writes cannot bind the first-line contract from the transcript; declaring first works.
        path = self.transcript(("user", "Fix the typo"))
        denied = self.edit_with(path, "unsaved")
        self.assertEqual(denied.returncode, 2)
        self.assertIn("first tool call", denied.stderr)
        self.assertIn("declare", denied.stderr)

    def test_transcript_contract_must_open_the_reply_to_the_latest_person_prompt(self):
        cases = {
            "late": (("user", "Fix it"), ("assistant", "Bug: max compares strings."), ("assistant", LINE)),
            "old turn": (("user", "First task"), ("assistant", LINE), ("user", "Second task"),
                         ("assistant", "Looking now.")),
            "no reply": (("user", "First task"), ("assistant", LINE), ("user", "Second task")),
            "sidechain": (("user", "Fix it"), ("assistant", LINE, True)),
            "placeholder": (("user", "Fix it"), ("assistant", "Contract: risk=<LOW> quality=<HIGH> acceptance=<x>")),
            "no prompt": (("assistant", LINE),),
        }
        for name, entries in cases.items():
            with self.subTest(name):
                denied = self.edit_with(self.transcript(*entries), f"d-{name}")
                self.assertEqual(denied.returncode, 2, denied.stderr)
                self.assertIn("first line", denied.stderr)
        for path in (str(self.root / "missing.jsonl"), 7):
            self.assertEqual(self.edit_with(path, "d-missing").returncode, 2)
        # A broken line is skipped rather than trusted or fatal.
        broken = self.root / "broken.jsonl"
        broken.write_text("{not json\n" + Path(self.transcript(("user", "Fix it"), ("assistant", LINE))).read_text())
        self.assertEqual(self.edit_with(str(broken), "d-broken").returncode, 0)

    def test_declaration_records_contract_metadata_and_runtime_model(self):
        result = self.tool("codex", "Bash", "s9", command=f"{DECLARE} <<'EOF'\n{BLOCK}\nEOF")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.root / ".agent-runtime/contract-sessions.json").read_text())["sessions"]["s9"]
        self.assertEqual((record["contract"], record["meta"], record["model"]),
                         (LINE, {"topic": "guard", "budget": "CHEAP"}, "model-x"))
        current = subprocess.run(["python3", str(self.root / ".lean/scripts/contract_guard.py"), "--root",
                                  str(self.root), "current", "--session", "s9"], capture_output=True, text=True)
        self.assertEqual(current.stdout.strip(), LINE)

    def test_invalid_declaration_unknown_tools_and_bad_input_fail_closed(self):
        bad = self.tool("claude", "Bash", command=f"{DECLARE} --contract 'Contract: risk=LOW'")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("Contract declaration rejected", bad.stderr)
        # A tool the guard does not know is not gated before a contract; the Stop gate still checks changed work.
        self.assertEqual(self.tool("codex", "mcp__docs__update").returncode, 0)
        self.assertEqual(self.tool("codex", "collaborationspawn_agent", task_name="review").returncode, 0)
        for payload in ({"tool_name": "Edit"}, {"session_id": "s1"}, ["not", "an", "object"]):
            self.assertEqual(self.hook("claude", "PreToolUse", payload).returncode, 2, payload)
        self.assertEqual(subprocess.run(["sh", "-c", "python3 .lean/scripts/contract_guard.py pre-tool || exit 2"],
                                        cwd=self.root, input="{not json", text=True,
                                        capture_output=True).returncode, 2)
        state = self.root / ".agent-runtime/contract-sessions.json"
        state.parent.mkdir(exist_ok=True)
        state.write_text("[]")
        self.assertEqual(self.tool("claude", "Read").returncode, 0)  # Read-only tools never consult state.
        self.assertEqual(self.tool("claude", "Edit", file_path="x.py").returncode, 2)
        # A broken reset warns without discarding the person's prompt.
        self.assertEqual(self.prompt("claude", "hello").returncode, 1)

    def test_declare_cli_validates_without_binding(self):
        script = str(self.root / ".lean/scripts/contract_guard.py")
        ok = subprocess.run(["python3", script, "declare"], input=BLOCK, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout.splitlines()[0], LINE)
        bad = subprocess.run(["python3", script, "declare", "--contract", "Contract:"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse((self.root / ".agent-runtime/contract-sessions.json").exists())


class StopContractTests(HookFixture):
    """Claude's and Codex's Stops use the session's declared contract for changed work."""

    def setUp(self):
        super().setUp()
        (self.root / ".lean/PROJECT.md").write_text("<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        (self.root / "app.py").write_text("x = 1\n")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@e.invalid",
                        "commit", "-qm", "base"], check=True)
        self.transcript = self.root / "transcript.jsonl"
        self.transcript.write_text(json.dumps({"type": "user", "message": {"content": "add y"}}) + "\n")

    def claude_stop(self, session):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        env.pop("CLAUDE_GATE_FORCE", None)
        seed = subprocess.run(["bash", str(self.root / ".claude/hooks/quality-gate.sh"), "--seed"], input="{}",
                              text=True, capture_output=True, env=env)
        self.assertEqual(seed.returncode, 0, seed.stderr)
        (self.root / "app.py").write_text("x = 2\n")
        return stop_refusal(subprocess.run(
            ["bash", str(self.root / ".claude/hooks/quality-gate.sh")], env=env, text=True, capture_output=True,
            input=json.dumps({"session_id": session, "stop_hook_active": False,
                              "transcript_path": str(self.transcript)})))

    def codex_event(self, event, session):
        return subprocess.run(["python3", str(self.root / ".codex/hooks/quality_gate.py"), event], text=True,
                              capture_output=True, input=json.dumps({"session_id": session,
                                                                     "stop_hook_active": False}))

    def test_claude_stop_uses_the_declared_contract_when_the_transcript_lacks_one(self):
        refused = self.claude_stop("c1")
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("No Task Contract", refused.stderr)
        self.assertEqual(self.tool("claude", "Bash", "c1", command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        passed = self.claude_stop("c1")
        self.assertEqual(passed.returncode, 0, passed.stderr)

    def test_codex_session_start_keeps_the_first_baseline_of_a_session(self):
        # A resumed session (or a subagent) fires SessionStart again with the same id; undeclared
        # work made before that must not be folded into the baseline.
        self.assertEqual(self.codex_event("session-start", "r1").returncode, 0)
        (self.root / "app.py").write_text("x = 2\n")
        self.assertEqual(self.codex_event("session-start", "r1").returncode, 0)
        refused = json.loads(self.codex_event("stop", "r1").stdout)
        self.assertEqual(refused.get("decision"), "block", refused)
        self.assertIn("no declared Task Contract", refused["reason"])

    def test_codex_stop_requires_a_declaration_only_for_changed_work(self):
        self.assertEqual(self.codex_event("session-start", "x1").returncode, 0)
        unchanged = self.codex_event("stop", "x1")
        self.assertIn("checks passed", json.loads(unchanged.stdout)["systemMessage"])
        (self.root / "app.py").write_text("x = 2\n")
        refused = json.loads(self.codex_event("stop", "x1").stdout)
        self.assertEqual(refused["decision"], "block")
        self.assertIn("no declared Task Contract", refused["reason"])
        self.assertEqual(self.tool("codex", "Bash", "x1", command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        passed = json.loads(self.codex_event("stop", "x1").stdout)
        self.assertIn("checks passed", passed["systemMessage"])
        high = "Contract: risk=HIGH quality=HIGH acceptance=reviewed"
        (self.root / "app.py").write_text("x = 3\n")
        self.assertEqual(self.prompt("codex", "next", "x1").returncode, 0)
        self.assertEqual(self.tool("codex", "Bash", "x1", command=f"{DECLARE} --contract '{high}'").returncode, 0)
        review = json.loads(self.codex_event("stop", "x1").stdout)
        self.assertEqual(review["decision"], "block")
        self.assertIn("review.json", review["reason"])  # HIGH contract: no receipt, no pass.


if __name__ == "__main__":
    unittest.main()

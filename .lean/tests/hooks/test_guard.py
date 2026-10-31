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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, lean, run_hook, stop_refusal  # noqa: E402
from lean import guard as contract_guard  # noqa: E402

DECLARE = "python3 .lean/bin/lean contract declare"
BLOCK = "Contract:\ntopic: guard\nrisk: LOW\nquality: STANDARD\nbudget: CHEAP\nacceptance: tests pass"
LINE = "Contract: risk=LOW quality=STANDARD acceptance=tests pass"


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
            command = f"{prefix} .lean/bin/lean contract declare <<\"END\"\n{BLOCK}\nEND"
            command = command.replace("/ .lean", "/.lean")
            self.assertEqual(contract_guard.declared_text(command), BLOCK, command)

    def test_other_commands_are_not_declarations_and_unsafe_forms_are_rejected(self):
        for command in ("ls", "python3 .lean/bin/lean evidence state", "echo declare"):
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
            f"python3 $(touch pwned).lean/bin/lean contract declare --contract '{LINE}'"))


class SessionReadTests(unittest.TestCase):
    def test_session_reads_do_not_create_runtime_state(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            self.assertIsNone(contract_guard.current(root, "missing"))
            self.assertIsNone(contract_guard.initial_head(root, "missing"))
            self.assertEqual(list(root.iterdir()), [])

    def test_saving_drops_sessions_idle_longer_than_a_week(self):
        # asdw-harness: one checkout kept every Claude and Codex session's record indefinitely.
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            now = time.time()
            with contract_guard.Store(root) as store:
                store.sessions.update({"old": {"contract": LINE, "at": now - 8 * 86400},
                                       "recent": {"contract": LINE, "at": now - 86400},
                                       "undated": {"initial_head": "abc"}})
                store.save()
            self.assertEqual(sorted(contract_guard.Store(root).read()), ["recent", "undated"])

    def test_session_reads_use_atomic_snapshot_without_creating_lock(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            runtime = root / ".agent-runtime"
            runtime.mkdir()
            path = runtime / "contract-sessions.json"
            path.write_text(json.dumps({"schema": 1, "sessions": {
                "session": {"contract": LINE, "initial_head": "abc"}}}))
            before = path.read_bytes()
            self.assertEqual(contract_guard.current(root, "session"), LINE)
            self.assertEqual(contract_guard.initial_head(root, "session"), "abc")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in runtime.iterdir()], [path.name])

    def test_session_reads_reject_malformed_or_symlinked_state(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            runtime = root / ".agent-runtime"
            runtime.mkdir()
            path = runtime / "contract-sessions.json"
            for content in ('[]', '{"schema": 9, "sessions": {}}', 'invalid JSON'):
                path.write_text(content)
                for read in (contract_guard.current, contract_guard.initial_head):
                    with self.assertRaises(ValueError):
                        read(root, "session")
            path.unlink()
            destination = root / "outside.json"
            destination.write_text('{"schema": 1, "sessions": {}}')
            for boundary in (path, runtime / "contract-sessions.lock"):
                boundary.unlink(missing_ok=True)
                boundary.symlink_to(destination)
                for read in (contract_guard.current, contract_guard.initial_head):
                    with self.assertRaises(ValueError):
                        read(root, "session")
                boundary.unlink()

    def test_session_reads_reject_non_object_session_records(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            runtime = root / ".agent-runtime"
            runtime.mkdir()
            path = runtime / "contract-sessions.json"
            for record in (None, False, [], ["bad"], "bad", 1):
                path.write_text(json.dumps({"schema": 1, "sessions": {"session": record}}))
                for read in (contract_guard.current, contract_guard.initial_head):
                    with self.subTest(record=record, read=read.__name__):
                        with self.assertRaisesRegex(ValueError, "malformed"):
                            read(root, "session")

    def test_session_reads_reject_non_string_contract_and_head(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            runtime = root / ".agent-runtime"
            runtime.mkdir()
            path = runtime / "contract-sessions.json"
            for field, read in (("contract", contract_guard.current), ("initial_head", contract_guard.initial_head)):
                for value in (False, 0, [], ["bad"], {}):
                    path.write_text(json.dumps({"schema": 1, "sessions": {"session": {field: value}}}))
                    with self.subTest(field=field, value=value):
                        with self.assertRaisesRegex(ValueError, "malformed"):
                            read(root, "session")


class ShellWriteTests(unittest.TestCase):
    def test_gate_preflight_reads_evidence_but_redirects_and_chains_still_write(self):
        for command in ("python3 .lean/bin/lean gate preflight",
                        "python3 .lean/bin/lean gate preflight --session review --require-review",
                        "python3 .lean/bin/lean gate preflight --contract '" + LINE + "'"):
            with self.subTest(command=command):
                self.assertFalse(contract_guard.shell_writes(command))
        for command in ("python3 .lean/bin/lean gate preflight > readiness.txt",
                        "python3 .lean/bin/lean gate preflight && touch changed.txt"):
            with self.subTest(command=command):
                self.assertTrue(contract_guard.shell_writes(command))

    def test_reads_inspection_chains_loops_and_other_tools_are_not_writes(self):
        for command in ("grep -n -i regression .lean/policy/TESTING.md", "cat a.py | head -5", "ls -la src",
                        "git status --short", "git diff", "git log --oneline -3", "git show HEAD:a.py | tail -n 20",
                        "rg -n 'def state' .lean/lean", "sed -n 26,58p gate.py", "find . -name '*.py' -type f",
                        "sort -u names.txt", "grep -n x a.py && sed -n 3,9p a.py", "ls src; git status --short",
                        'cd /tmp && echo hi; for f in a b; do cat "$f"; done', 'x=$(git rev-parse HEAD); echo "$x"',
                        "python3 .lean/bin/lean mode show", "python3 .lean/bin/lean mode context",
                        "python3 .lean/bin/lean evidence --root . state", "python3 .lean/bin/lean models check --live",
                        "python3 -m unittest discover -s .lean/tests", "python3 .lean/bin/lean test --changed",
                        "python3 .lean/bin/lean status --line", "python3 .lean/bin/lean effort",
                        "python3 .lean/bin/lean gate mode", "python3 .lean/bin/lean gate mode --policy",
                        "cat a 2>&1 | head", "ls > /dev/null", "cat a 2>/dev/null", "echo x >&2", "git branch -r",
                        "git -C sub status", "git --no-pager log -1", "git tag -l 'v*'", "git remote -v",
                        "git stash list", "git config --get user.name", "git worktree list", "git diff -M",
                        "python3 .lean/bin/lean gate run", "./script.sh --flag", "(cat a)", "cat a &",
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
                        "time grep x f", "xargs -n 1 grep x", "brew list",
                        # Follow-up: sed file names, perl module flags, lookups and runner arguments are data.
                        "sed -n '1,20p' src/w/x.py", "sed -n 1,5p w.txt", "sed -n '/^W/p' f", "sed -e 1p w",
                        "perl -Mstrict -e 'print 1'", "perl -Ilib -ne print f", "command -v rm", "command -V make",
                        "xargs grep -l rm", "env grep make f", "xargs -I % grep x %", "nice -n 5 grep rm f",
                        "python3 .lean/bin/lean gate run --session s", "sh ./script.sh", "tar -C d -tf a.tar",
                        "bash -o pipefail script.sh", "xargs -J % grep x %", "env -S 'grep x f'",
                        "sed -n '/word/p' f", "sed 's/w/x/' f", "python3 .lean/bin/lean progress set test --done 1 --total 3",
                        ".lean/bin/lean watch --once", "lean spawn plan --tasks t.json", "lean lint",
                        "python3 .lean/bin/lean evidence high-risk", "lean update preview --ref v5.0.0",
                        "python3 .lean/bin/lean target context", "lean target use --dry-run -- https://h/app.git",
                        "lean target gate --quiet", "lean --root targets/x --workflow-root . mode show",
                        "python3 .lean/bin/lean log", "lean log --summary --since 2026-10-26", "lean log --json"):
            self.assertFalse(contract_guard.shell_writes(command), command)

    def test_git_reflog_and_symbolic_ref_write_unless_they_only_read(self):
        # Ported from a downstream project's local patch: both were treated as read-only in every form.
        for command in ("git reflog", "git reflog show HEAD", "git reflog exists refs/heads/main", "git reflog -5",
                        "git reflog list", "git reflog main", "git reflog show expire",
                        "git symbolic-ref HEAD", "git symbolic-ref --short HEAD", "git symbolic-ref -q HEAD"):
            with self.subTest(read=command):
                self.assertFalse(contract_guard.shell_writes(command), command)
        for command in ("git reflog expire --expire=now --all", "git reflog delete HEAD@{1}", "git reflog drop",
                        "git symbolic-ref HEAD refs/heads/other", "git symbolic-ref -d HEAD",
                        "git symbolic-ref --delete HEAD", "git symbolic-ref -m why HEAD refs/heads/x",
                        # Review: git accepts bundled short flags and abbreviated long options.
                        "git symbolic-ref -qd HEAD", "git symbolic-ref -dq HEAD", "git symbolic-ref --del HEAD",
                        "git symbolic-ref --delet HEAD", "git reflog write HEAD x y z", "git reflog expire"):
            with self.subTest(write=command):
                self.assertTrue(contract_guard.shell_writes(command), command)

    def test_an_expansion_or_glob_in_the_deciding_git_word_is_a_write(self):
        # Review of 5.2.1: `git reflog $X` read as safe though $X may be `expire`, unlike `git stash $X`.
        for command in ("git reflog $X", 'git reflog "$X"', "git reflog $(echo expire)", "git reflog exp*",
                        "git symbolic-ref $N", "git symbolic-ref HEA?"):
            with self.subTest(command=command):
                self.assertTrue(contract_guard.shell_writes(command), command)

    def test_lean_models_apply_and_eval_are_writes(self):
        for command in ("python3 .lean/bin/lean models", "python3 .lean/bin/lean models list",
                        "python3 .lean/bin/lean models check --live", "python3 .lean/bin/lean models bank"):
            with self.subTest(read=command):
                self.assertFalse(contract_guard.shell_writes(command), command)
        for command in ("python3 .lean/bin/lean models apply --proposal p.json --sha256 x",
                        "python3 .lean/bin/lean models eval --plan p.json --budget 10"):
            with self.subTest(write=command):
                self.assertTrue(contract_guard.shell_writes(command), command)

    def test_lean_help_git_submodule_reads_and_input_redirection_are_not_writes(self):
        for command in ("python3 .lean/bin/lean -h", "python3 .lean/bin/lean --help",
                        "python3 .lean/bin/lean evidence record-review -h",
                        "python3 .lean/bin/lean evidence record-review --help",
                        "python3 .lean/bin/lean mode configure -h", "lean target clear --help",
                        "git submodule", "git submodule -q", "git submodule --cached",
                        "git submodule status", "git submodule status --recursive",
                        "git submodule status --cached targets/app",
                        "git submodule summary", "git submodule summary --cached --files",
                        "git submodule summary -n 5", "git submodule summary --summary-limit=5",
                        "wc -l < $L", 'wc -l < "$L"', 'cat < "$file"', "jq . < data.json", "< $L wc -l"):
            with self.subTest(read=command):
                self.assertFalse(contract_guard.shell_writes(command), command)
        for command in ("git submodule update --init",
                        "git submodule add https://example.com/repo.git targets/app",
                        "git submodule init", "git submodule deinit targets/app",
                        "git submodule sync", "git submodule foreach git status",
                        "git submodule set-branch --branch main targets/app",
                        "git submodule set-url targets/app https://example.com/repo.git",
                        "git submodule absorbgitdirs", "git submodule $X", "git submodule stat*",
                        "bash -s < f", "bash < f", 'bash <<< "rm x"', "wc -l < $L && touch x"):
            with self.subTest(write=command):
                self.assertTrue(contract_guard.shell_writes(command), command)

    def test_writes_runners_installers_and_invisible_commands_are_writes(self):
        receipt_call = "python3 .lean/bin/lean evidence " + "record-" + "review --verdict PASS"
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
                        "python3 .lean/bin/lean mode configure tracker",
                        "python3 .lean/bin/lean gate accept-controls --reason x", receipt_call,
                        "python3 .lean/bin/lean spawn run --tasks t.json", "python3 .lean/bin/lean tracker new --id TCK001 --title x",
                        "python3 .lean/bin/lean effort high", "python3 .lean/bin/lean gate mode auto_fixloop",
                        "python3 .lean/bin/lean gate mode manual_fixloop", "python3 .lean/lean/gate.py",
                        "python3 .lean/bin/lean queue claim --id Q0001 --agent a --request-id 12345678",
                        "lean update apply --workspace w", "lean mode downgrade standard --apply",
                        "python3 .lean/bin/lean unknown-group", "lean effort reset lean-task",
                        "lean target use --apply -- https://h/app.git", "python3 .lean/bin/lean target clear",
                        "lean lint --write-registry", "lean log --export a.md", "lean log --export=a.md",
                        "lean lint --write-registry=x",
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
                        '"$HOME/bin/rm" x', "${EDITOR} f",
                        # Follow-up: shells reading commands from stdin, function bodies, tar options after -C.
                        "bash <<'EOF'\nrm -rf x\nEOF", "echo 'rm x' | sh", "bash -s < f", "cat cmds | bash",
                        "zsh -s", "function f { rm x; }", "function f() { touch y; }", "tar -C d -xf a.tar",
                        "tar -v -czf out.tgz dir", "xargs -n 1 rm", "env -C /tmp rm f", "time -p rm x",
                        "sed -e 's/a/b/' -e 'w out' f", "perl -pi -e s/a/b/ f", "perl -Mstrict -pi -e s/a/b/ f",
                        # Review round 1 of the follow-up: POSIX function bodies, more runner value options,
                        # env -S command lines, sed flags before w and other w addresses, perl -d, bash -o.
                        "f() { rm x; }", "f () { rm x; }", "f(){ rm x;}", "xargs -J % rm %", "xargs -R 1 rm",
                        "xargs -S 1 rm", "xargs --max-args 1 rm", "env --unset X rm f", "nice --adjustment 5 rm x",
                        "time --output t.txt rm x", "env -S 'rm f'", "env --split-string 'rm f'",
                        "sed 's/a/b/gw out' f", "sed 's/a/b/pw out' f", "sed 's/a/b/Iw out' f", "sed -n '1!w out' f",
                        "sed -n 'w/tmp/x' f", "sed -n '\\,x,w out' f", "perl -dpi -e x f", "bash -o pipefail"):
            self.assertTrue(contract_guard.shell_writes(command), command)


class HookFixture(unittest.TestCase):
    """Run hooks exactly as each provider's configured command does, in a disposable checkout."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean contract guard ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        install(self.root)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def hook(self, provider, event, payload):
        return run_hook(self.root, provider, event, payload)

    def tool(self, provider, name, session="s1", **tool_input):
        return self.hook(provider, "PreToolUse", {"session_id": session, "tool_name": name, "tool_input": tool_input,
                                                   "hook_event_name": "PreToolUse", "model": "model-x"})

    def prompt(self, provider, text, session="s1"):
        return self.hook(provider, "UserPromptSubmit", {"session_id": session, "prompt": text})



class MidTurnPromptTests(HookFixture):
    """A Claude prompt typed while the agent still works continues the task; any other prompt starts one."""

    WRITES = {"claude": ("Edit", {"file_path": "x.py"}), "codex": ("apply_patch", {"command": "*** Begin Patch"})}

    def test_plan_preview_is_read_only_before_contract_for_both_providers(self):
        for provider in ("claude", "codex"):
            for flag in ("--explain", "--json"):
                with self.subTest(provider=provider, flag=flag):
                    result = self.tool(provider, "Bash", command="python3 .lean/bin/lean plan " + flag)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIsNone(contract_guard.current(self.root, "s1"))

    def declare(self, provider="claude", session="s1"):
        declared = self.tool(provider, "Bash", session, command=f"{DECLARE} <<'EOF'\n{BLOCK}\nEOF")
        self.assertEqual(declared.returncode, 0, declared.stderr)

    def transcript(self, *entries):
        path = self.root / ".git/transcript.jsonl"
        path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
        return str(path)

    @staticmethod
    def at(offset):
        """An ISO timestamp `offset` seconds from now, as Claude transcripts record it."""
        return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() + offset))

    def submit(self, text, transcript=None, provider="claude", session="s1"):
        payload = {"session_id": session, "prompt": text}
        if transcript:
            payload["transcript_path"] = transcript
        result = self.hook(provider, "UserPromptSubmit", payload)
        self.assertEqual(result.returncode, 0, result.stderr)

    def can_write(self, provider="claude", session="s1"):
        name, tool_input = self.WRITES[provider]
        return self.tool(provider, name, session, **tool_input).returncode == 0

    def assistant(self, offset):
        """A Claude assistant entry that runs a tool, `offset` seconds from now."""
        return {"type": "assistant", "timestamp": self.at(offset),
                "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}

    def test_a_prompt_typed_while_the_agent_works_keeps_the_contract(self):
        # Claude runs the hook before it records such a prompt at all, so nothing in the transcript marks it.
        self.declare()
        self.submit("status?", self.transcript(self.assistant(-2), self.assistant(2)))
        self.assertTrue(self.can_write(), "a status question sent mid-turn dropped the bound contract")

    def test_a_stop_that_blocks_does_not_end_the_turn(self):
        self.declare()
        path = self.transcript(self.assistant(2),
                               {"type": "user", "isMeta": True, "timestamp": self.at(2),
                                "message": {"role": "user", "content": "Stop hook feedback:\nGate refused"}},
                               {"type": "system", "subtype": "stop_hook_summary", "timestamp": self.at(2)})
        self.submit("status?", path)
        self.assertTrue(self.can_write(), "a blocked Stop counted as the end of the turn")

    def test_a_finished_turn_or_an_untimed_turn_end_clears_the_contract(self):
        for offset in (2, None):
            with self.subTest(offset=offset):
                self.declare()
                end = {"type": "system", "subtype": "turn_duration"}
                if offset is not None:
                    end["timestamp"] = self.at(offset)
                self.submit("next", self.transcript(self.assistant(2), end))
                self.assertFalse(self.can_write())

    def test_a_person_prompt_or_interrupt_after_binding_clears_the_contract(self):
        # A prompt that starts a turn is recorded as a user entry before its hook runs.
        for text in ("next task", "[Request interrupted by user]"):
            with self.subTest(text=text):
                self.declare()
                path = self.transcript(self.assistant(2), {"type": "user", "timestamp": self.at(2),
                                                           "message": {"role": "user", "content": text}})
                self.submit("next task", path)
                self.assertFalse(self.can_write())

    def test_a_session_lifetime_keeps_the_contract_across_prompts_and_says_so(self):
        # asdw-harness: 22 contracts in one day, 3 of them the same text redeclared after a new prompt.
        (self.root / ".lean/config.json").write_text(json.dumps(
            {"mode": "standard", "configured": True, "contract_lifetime": "session"}))
        for provider in ("claude", "codex"):
            with self.subTest(provider=provider):
                session = f"keep-{provider}"
                self.declare(provider, session)
                payload = {"session_id": session, "prompt": "next task"}
                if provider == "claude":
                    payload["transcript_path"] = self.transcript(
                        self.assistant(2), {"type": "system", "subtype": "turn_duration", "timestamp": self.at(2)})
                result = self.hook(provider, "UserPromptSubmit", payload)
                self.assertEqual(result.returncode, 0, result.stderr)
                context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
                self.assertIn("kept", context)
                self.assertIn("risk=", context)
                self.assertTrue(self.can_write(provider, session))

    def test_a_write_racing_the_saved_reply_gets_a_short_retry_hint(self):
        path = self.transcript(self.assistant(-1))
        result = self.hook("claude", "PreToolUse", {"session_id": "race", "tool_name": "Edit",
                                                    "tool_input": {"file_path": "x.py"}, "transcript_path": path})
        self.assertEqual(result.returncode, 2)
        self.assertIn("retry this call", result.stderr)
        self.assertLessEqual(len(result.stderr.strip().splitlines()), 3, result.stderr)
        without = self.tool("claude", "Edit", "race", file_path="x.py")
        self.assertIn("contract declare", without.stderr)  # No transcript: the full guidance.

    def test_without_a_readable_transcript_every_prompt_still_clears(self):
        for provider, transcript in (("claude", None), ("claude", "/nonexistent/t.jsonl"), ("codex", None)):
            with self.subTest(provider=provider, transcript=transcript):
                session = f"{provider}-{transcript}"
                self.declare(provider, session)
                self.submit("status?", transcript, provider, session)
                self.assertFalse(self.can_write(provider, session))

    def test_a_codex_prompt_with_its_own_transcript_still_clears(self):
        # Codex rollouts carry no queue records or Claude turn ends, so every Codex prompt starts a task.
        path = self.transcript(
            {"timestamp": self.at(-5), "type": "session_meta", "payload": {"id": "c1"}},
            {"timestamp": self.at(1), "type": "event_msg", "payload": {"type": "task_started"}},
            {"timestamp": self.at(1), "type": "response_item",
             "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "status?"}]}})
        self.declare("codex", "codex-rollout")
        self.submit("status?", path, "codex", "codex-rollout")
        self.assertFalse(self.can_write("codex", "codex-rollout"))


class GuardHookTests(HookFixture):
    def test_shell_writes_only_under_scratch_need_no_contract(self):
        # asdw-harness: `mkdir -p <Claude scratchpad>/x` was blocked although Write there was allowed.
        scratch = "/tmp/lean-guard-scratch-test"
        allowed = (f"mkdir -p {scratch}/x", f"touch {scratch}/a {scratch}/b", f"echo hi > {scratch}/f",
                   f"rm -rf {scratch}/x && mkdir {scratch}/y", f"cat x.py | tee {scratch}/copy")
        denied = (f"cp x.py {scratch}/x", f"mv {scratch}/a x.py", f"touch {scratch}/a && touch x.py",
                  f"mkdir {scratch}/$HOME", f"rm -rf {scratch}/../..{shlex.quote(str(self.root / 'x'))}", f"echo > {shlex.quote(str(self.root / 'f'))}",
                  f"mkdir -m 700 {scratch}/x", f"python3 -c 'open(\"{scratch}/f\", \"w\")'",
                  f"git -C {scratch} init", f"mkdir {scratch}/x\ntouch x.py",
                  # Review 5.7 round 1: the shell rewrites these words, or an option carries the target.
                  f"touch {scratch}/{{a,../../etc/lean-x}}", f"rm -rf {scratch}/*/../x", "rm -rf ~/x",
                  f"rm {scratch}/[ab]/../../x", f"cp -t/etc/lean-x {scratch}/a",
                  f"cp --target-directory=/etc/lean-x {scratch}/a", f"ln -s /etc/lean-x {scratch}/l -T",
                  # Review 5.7 round 2: zsh glob qualifiers and modifiers, extglob and other expansions.
                  f"cp {scratch}/a {scratch}(:s#tmp/lean-guard-scratch-test#etc/lean-x#)", f"touch {scratch}/a(:h)",
                  f"touch {scratch}/@(a|b)", f"touch {scratch}/!(a)", f"touch {scratch}/^a",
                  f"touch {scratch}/a#", f"touch ={scratch}/a")
        for command in allowed:
            with self.subTest(allowed=command):
                result = self.tool("claude", "Bash", "scratch", command=command)
                self.assertEqual(result.returncode, 0, result.stderr)
        for command in denied:
            with self.subTest(denied=command):
                self.assertEqual(self.tool("claude", "Bash", "scratch", command=command).returncode, 2)

    def test_project_listed_commands_run_before_a_contract(self):
        # asdw-harness: `pnpm build` was blocked while `pnpm test`, which also writes, ran.
        self.assertEqual(self.tool("claude", "Bash", "list", command="pnpm build").returncode, 2)
        project = self.root / ".lean/PROJECT.md"
        project.write_text("# Project\n\n## Pre-contract commands\n\n- `pnpm build`\n- `make docs`\n\n## Other\n\n- `make`\n")
        for command in ("pnpm build", "  make docs "):
            with self.subTest(allowed=command):
                self.assertEqual(self.tool("claude", "Bash", "list", command=command).returncode, 0)
        for command in ("pnpm build && rm -rf x", "pnpm build > out", "make", "pnpm install"):
            with self.subTest(denied=command):
                self.assertEqual(self.tool("claude", "Bash", "list", command=command).returncode, 2)

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
        record = ("python3 .lean/bin/lean evidence record-review --contract '{}' --reviewer r "
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
        plain = ("python3 .lean/bin/lean evidence WORD --contract '{}' --reviewer r "
                 "--evidence e --verdict PASS --state abc").replace("WORD", word)
        forms = (plain.replace(word, word.replace("review", '"review"')),
                 plain.replace("python3 .lean/bin/lean", "cd .lean/bin && python3 lean"),
                 plain.replace(".lean/bin/lean", ".lean/tests/../bin/lean"))
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
        for command in (f"python3 .lean/bin/lean gate run --require-review --contract '{mentions}'",
                        f"python3 .lean/bin/lean evidence check-review --contract '{mentions}'",
                        f"echo '{mentions}'"):
            result = self.tool("claude", "Bash", session, command=command)
            self.assertEqual(result.returncode, 0, (command, result.stderr))
        # The contract as data inside a longer word, or as a --contract= value, is not a recording.
        for command in (f"git commit -m 'fix: {mentions}'",
                        f"python3 .lean/bin/lean gate run --contract='{mentions}' --require-review"):
            self.assertFalse(contract_guard.records_own_receipt(command, mentions), command)
        # A single word that only contains the subcommand name is a path or pattern, not a call.
        for command in ("cat record-review.txt", "grep -rn record-review .lean/policy", "ls record-review/x"):
            self.assertFalse(contract_guard.records_own_receipt(command, mentions), command)
        # A nested recording of that contract is still one, including one hidden behind a
        # --contract= or --contract word that a wrapper evaluates (review of 4c609b7).
        nested = f"python3 .lean/bin/lean evidence record-review --contract '{mentions}' --state s"
        for command in (f"bash -lc {json.dumps(nested)}", f"eval {json.dumps('--contract=x; ' + nested)}",
                        f"bash -c {json.dumps('--contract=x; ' + nested)}",
                        f"eval --contract {json.dumps('x; ' + nested)}"):
            self.assertTrue(contract_guard.records_own_receipt(command, mentions), command)
        # Shell quoting that changes the text still names the same contract.
        apostrophe = "Contract: risk=LOW quality=STANDARD acceptance=the author's tests pass"
        quoted = apostrophe.replace("'", "'\\''")
        self.assertEqual(self.tool("codex", "Bash", "quote-session", command=f"{DECLARE} <<'EOF'\n{apostrophe}\nEOF").returncode, 0)
        for command in (f"python3 .lean/bin/lean evidence --root . record-review --contract '{quoted}' --state s",
                        f'python3 .lean/bin/lean evidence record-review --contract "{apostrophe}" --state s',
                        f"python3 .lean/bin/lean evidence record-review --contract='{quoted}'"):
            result = self.tool("codex", "Bash", "quote-session", command=command)
            self.assertEqual(result.returncode, 2, command)
        # Shell syntax glued to the contract, wrappers and subshells still name it (review round 1).
        base = f"python3 .lean/bin/lean evidence record-review --contract '{quoted}'"
        for command in (base + ";echo done", base + "&&echo done", base + ">/dev/null", f"({base})",
                        f'bash -c "{base.replace(chr(34), "")}"', f"sh -c {json.dumps(base)}",
                        "python3 .lean/bin/lean evidence state&&" + base,
                        # Review round 2: option bundles, options before -c, here-strings and pipes.
                        f"bash -lc {json.dumps(base)}", f"bash -ec {json.dumps(base)}",
                        f"bash --norc -c {json.dumps(base)}", f"bash <<< {json.dumps(base)}",
                        f"echo {json.dumps(base)} | sh", f"eval {json.dumps(base)}"):
            self.assertTrue(contract_guard.records_own_receipt(command, apostrophe), command)
        # Another command on the line is not part of the receipt call.
        self.assertFalse(contract_guard.records_own_receipt(
            f"python3 .lean/bin/lean evidence state; echo '{apostrophe}'", apostrophe))
        # A contract hidden behind expansion cannot be compared, so the author's thread may not record at all.
        hidden = self.tool("codex", "Bash", "quote-session",
                           command='python3 .lean/bin/lean evidence record-review --contract "$(cat c.txt)"')
        self.assertEqual(hidden.returncode, 2)

    def test_receipt_guard_catches_copies_pipelines_and_direct_receipt_writes(self):
        session = "evasion-session"
        self.assertEqual(self.tool("codex", "Bash", session, command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        copy = self.root / "tools/ge.py"
        copy.parent.mkdir()
        shutil.copy2(self.root / ".lean/lean/evidence.py", copy)
        for command in (f"python3 tools/ge.py record-review --contract '{LINE}' --state s",
                        f"python3 {shlex.quote(str(copy))} record-review --contract '{LINE}' --state s",
                        f"echo record-review | xargs python3 .lean/bin/lean evidence --contract '{LINE}'"):
            self.assertTrue(contract_guard.records_own_receipt(command, LINE, self.root), command)
            self.assertEqual(self.tool("codex", "Bash", session, command=command).returncode, 2, command)
        # A copy only counts when it is one; searching the real script stays allowed.
        (self.root / "notes.py").write_text("print('record-review notes')\n")
        for command in (f"python3 notes.py record-review --contract '{LINE}'",
                        "grep -rn record-review .lean/lean/evidence.py"):
            self.assertFalse(contract_guard.records_own_receipt(command, LINE, self.root), command)
        # The receipt file is written only by record-review, never by an edit tool or a shell write.
        receipt = ".agent-runtime/review.json"
        history = ".agent-runtime/review-history.jsonl"  # Earlier receipts count too, so they are guarded alike.
        for provider, name, tool_input in (("claude", "Write", {"file_path": f"{self.root}/{history}"}),
                                           ("codex", "Bash", {"command": f"echo '{{}}' >> {history}"}),
                                           ("claude", "Write", {"file_path": f"{self.root}/{receipt}"}),
                                           ("claude", "Edit", {"file_path": receipt}),
                                           ("codex", "apply_patch", {"command": f"*** Update File: {receipt}"}),
                                           ("codex", "Bash", {"command": f"cp fake.json {receipt}"}),
                                           ("codex", "Bash", {"command": f"echo '{{}}' > {receipt}"})):
            with self.subTest(name=name, tool_input=tool_input):
                result = self.hook(provider, "PreToolUse", {"session_id": session, "tool_name": name,
                                                            "tool_input": tool_input, "agent_id": "a1"})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("review receipt", result.stderr)
                self.assertIn("lean evidence " + "record-review", result.stderr)
        self.assertEqual(self.tool("codex", "Bash", session, command=f"cat {receipt}").returncode, 0)
        # Review round 1: copy-and-run in one command, extension-less copies, reads with redirects
        # and an unrelated pipeline.
        for command in (f"cp .lean/lean/evidence.py g && python3 g record-review --contract '{LINE}'",
                        f"ln -s .lean/lean/evidence.py /tmp/g.py; python3 /tmp/g.py record-review --contract '{LINE}'"):
            self.assertTrue(contract_guard.records_own_receipt(command, LINE, self.root), command)
        shutil.copy2(copy, self.root / "tools/ge")
        self.assertTrue(contract_guard.records_own_receipt(
            f"python3 tools/ge record-review --contract '{LINE}'", LINE, self.root))
        self.assertFalse(contract_guard.records_own_receipt(
            "grep record-review notes.txt | python3 .lean/bin/lean evidence state", LINE, self.root))
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
        guard = self.root / ".lean/lean/guard.py"
        guard.write_text(guard.read_text().replace("    session = session_of(payload)\n    name =",
                                                   "    session = session_of(payload)\n    undefined_name\n    name =", 1))
        for provider in ("claude", "codex"):
            with self.subTest(provider=provider):
                blocked = self.tool(provider, "Bash", command="ls")
                self.assertEqual(blocked.returncode, 2, blocked.stderr)
                self.assertIn("contract guard crashed", blocked.stderr)
                for name, tool_input in (("Read", {"file_path": "x.py"}),
                                         ("Edit", {"file_path": str(guard)}),
                                         ("Bash", {"command": "git checkout -- .lean/lean/guard.py"}),
                                         ("apply_patch", {"command": "*** Update File: .lean/lean/guard.py"})):
                    result = self.tool(provider, name, **tool_input)
                    self.assertEqual(result.returncode, 0, (name, result.stderr))
                self.assertEqual(self.tool(provider, "Edit", file_path="app.py").returncode, 2)
                # Review round 1: repair mode takes the guard path itself, not a word that ends with it.
                expanded = "git checkout -- $(touch pwned).lean/lean/guard.py"
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
                        "python3 .lean/bin/lean mode show", "x=$(git rev-parse HEAD); echo $x"):
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
        record = (f"python3 .lean/bin/lean evidence record-review --contract '{LINE}' --reviewer r "
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
        from support import configured
        command = configured(self.root, "claude", "PreToolUse")
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
        current = lean(self.root, "contract", "current", "--session", "s9")
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
        self.assertEqual(subprocess.run(["sh", "-c", "python3 .lean/bin/lean hook claude pre-tool || exit 2"],
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
        ok = lean(self.root, "contract", "declare", input=BLOCK)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout.splitlines()[0], LINE)
        bad = lean(self.root, "contract", "declare", "--contract", "Contract:")
        self.assertEqual(bad.returncode, 2)
        self.assertFalse((self.root / ".agent-runtime/contract-sessions.json").exists())


    def test_declare_cli_fails_in_claude_when_the_hook_did_not_bind_it(self):
        # Found in use: `C='...'; lean contract declare --contract "$C"` is not a pure declare, so the guard
        # skips it; the command used to print the contract as if it were bound.
        other = LINE.replace("acceptance=", "acceptance=another ")
        claude = dict(os.environ, CLAUDECODE="1")
        self.assertEqual(self.tool("claude", "Bash", "s-bound", command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        unbound = lean(self.root, "contract", "declare", "--contract", other, env=claude)
        self.assertEqual(unbound.returncode, 2, unbound.stdout)
        self.assertIn("NOT bound", unbound.stderr)
        self.assertEqual(lean(self.root, "contract", "current", "--session", "s-bound").stdout.strip(), LINE)
        # Bound whenever a session holds it, however long the person took to approve the command.
        self.assertEqual(lean(self.root, "contract", "declare", "--contract", LINE, env=claude).returncode, 0)
        # Runtimes whose hooks may not run (agy, Codex without trust) only validate.
        self.assertEqual(lean(self.root, "contract", "declare", "--contract", other).returncode, 0)
        # A pure declare is bound by the hook before it runs, so the same command then succeeds in Claude.
        self.assertEqual(self.tool("claude", "Bash", "s-bound", command=f"{DECLARE} --contract '{other}'").returncode, 0)
        self.assertEqual(lean(self.root, "contract", "declare", "--contract", other, env=claude).returncode, 0)
        # A malformed store is "not bound", never a traceback.
        state = self.root / ".agent-runtime/contract-sessions.json"
        for broken in ('{"schema": 1, "sessions": {"x": {"contract": 1, "at": [1]}}}', "[]", "{not json"):
            with self.subTest(store=broken):
                state.write_text(broken)
                result = lean(self.root, "contract", "declare", "--contract", other, env=claude)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_record_review_help_runs_without_contract_and_for_author_session(self):
        word = "record-" "review"
        for flag in ("-h", "--help"):
            help_cmd = f"python3 .lean/bin/lean evidence {word} {flag}"
            self.assertFalse(contract_guard.records_own_receipt(help_cmd, LINE, self.root), help_cmd)
            self.assertEqual(self.tool("claude", "Bash", "no-contract-help", command=help_cmd).returncode, 0, help_cmd)
        self.assertEqual(self.tool("claude", "Bash", "author-help",
                                   command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        for flag in ("-h", "--help"):
            help_cmd = f"python3 .lean/bin/lean evidence {word} {flag}"
            self.assertEqual(self.tool("claude", "Bash", "author-help", command=help_cmd).returncode, 0, help_cmd)
        # Chaining a write or a real receipt call after -h is still blocked.
        chained_write = f"python3 .lean/bin/lean evidence {word} -h && touch x"
        self.assertEqual(self.tool("claude", "Bash", "no-contract-help", command=chained_write).returncode, 2)
        chained_receipt = (f"python3 .lean/bin/lean evidence {word} -h && "
                           f"python3 .lean/bin/lean evidence {word} --contract '{LINE}' --verdict PASS")
        self.assertEqual(self.tool("claude", "Bash", "author-help", command=chained_receipt).returncode, 2)

    def test_external_scratch_and_user_memory_writes_allowed_without_repo_contract(self):
        for tool_name, path in (("Write", "/tmp/claude-scratch-note.md"),
                                ("Edit", "/private/tmp/claude-501/scratch.txt"),
                                ("Write", str(Path.home().resolve() / ".claude/projects/-Users-x10-repo/memory/MEMORY.md")),
                                ("MultiEdit", str(Path.home().resolve() / ".ccs/claude-profiles/work/projects/p/memory/note.md"))):
            with self.subTest(tool=tool_name, path=path):
                res = self.tool("claude", tool_name, "paused-session", file_path=path)
                self.assertEqual(res.returncode, 0, res.stderr)
        # Files inside the repository (even if named .claude/.../memory/) or relative paths still require a contract.
        for path in ("x.py", str(self.root / "x.py"), str(self.root / ".claude/projects/p/memory/MEMORY.md")):
            with self.subTest(repo_path=path):
                res = self.tool("claude", "Write", "paused-session", file_path=path)
                self.assertEqual(res.returncode, 2, path)

    def test_controller_takeover_supersedes_active_sessions_and_blocks_split_brain_writes(self):
        contract_guard.start_session(self.root, "s-claude", "base-state-1")
        self.assertEqual(self.tool("claude", "Bash", "s-claude",
                                   command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        self.assertEqual(self.tool("claude", "Edit", "s-claude", file_path="x.py").returncode, 0)
        takeover_block = ("Contract:\ntopic: takeover-s-claude\nrisk: MEDIUM\nquality: HIGH\n"
                          "acceptance: fallback controller completes work")
        self.assertEqual(self.tool("codex", "Bash", "s-codex",
                                   command=f"{DECLARE} <<'EOF'\n{takeover_block}\nEOF").returncode, 0)
        sessions = json.loads((self.root / ".agent-runtime/contract-sessions.json").read_text())["sessions"]
        self.assertEqual(sessions["s-claude"].get("superseded_by"), "s-codex")
        self.assertEqual(sessions["s-claude"].get("baseline"), "base-state-1")
        self.assertIn("initial_head", sessions["s-claude"])
        # The superseded session cannot edit the worktree or run writing shell commands concurrently.
        denied_edit = self.tool("claude", "Edit", "s-claude", file_path="x.py")
        self.assertEqual(denied_edit.returncode, 2)
        self.assertIn("was superseded by controller session s-codex", denied_edit.stderr)
        denied_bash = self.tool("claude", "Bash", "s-claude", command="touch x.py")
        self.assertEqual(denied_bash.returncode, 2)
        self.assertIn("was superseded by controller session s-codex", denied_bash.stderr)
        # Read-only tools and external memory/tmp notes remain allowed while superseded.
        self.assertEqual(self.tool("claude", "Read", "s-claude", file_path="x.py").returncode, 0)
        self.assertEqual(self.tool("claude", "Bash", "s-claude", command="git status --short").returncode, 0)
        self.assertEqual(self.tool("claude", "Write", "s-claude",
                                   file_path=str(Path.home().resolve() / ".claude/projects/p/memory/MEMORY.md")).returncode, 0)
        # Re-declaring a new contract explicitly takes back ownership and clears superseded_by.
        self.assertEqual(self.tool("claude", "Bash", "s-claude",
                                   command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        self.assertEqual(self.tool("claude", "Edit", "s-claude", file_path="x.py").returncode, 0)


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
        seed = lean(self.root, "hook", "claude", "session-start", input="{}")
        self.assertEqual(seed.returncode, 0, seed.stderr)
        (self.root / "app.py").write_text("x = 2\n")
        return stop_refusal(lean(self.root, "hook", "claude", "stop", input=json.dumps(
            {"session_id": session, "stop_hook_active": False, "transcript_path": str(self.transcript)})))

    def codex_event(self, event, session):
        return lean(self.root, "hook", "codex", event,
                    input=json.dumps({"session_id": session, "stop_hook_active": False}))

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

    def check_committed_high_risk_session(self, provider):
        project = self.root / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n## High-risk areas\n\n- `auth.py`: permissions.\n")
        auth = self.root / "auth.py"
        auth.write_text("deny = True\n")
        def commit():
            subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c",
                            "user.email=t@e.invalid", "commit", "-qm", "fixture"], check=True)
        commit()
        payload = {"session_id": "committed", "stop_hook_active": False}
        def event(seed=False):
            if provider == "codex":
                return stop_refusal(self.codex_event("session-start" if seed else "stop", "committed"))
            return stop_refusal(lean(self.root, "hook", "claude", "session-start" if seed else "stop",
                                     input=json.dumps(payload)))
        self.assertEqual(event(seed=True).returncode, 0)
        self.assertEqual(self.tool(provider, "Bash", "committed",
                                   command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        auth.write_text("deny = False\n")
        before = event()
        self.assertEqual(before.returncode, 2, before.stderr)
        self.assertIn("auth.py", before.stderr)
        commit()
        # Resume must retain the original HEAD, even though the working tree is now clean.
        self.assertEqual(event(seed=True).returncode, 0)
        self.assertEqual(self.prompt(provider, "continue", "committed").returncode, 0)
        self.assertEqual(self.tool(provider, "Bash", "committed",
                                   command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        after = event()
        self.assertEqual(after.returncode, 2, after.stderr)
        self.assertIn("auth.py", after.stderr)
        high = "Contract: risk=HIGH quality=HIGH acceptance=review fixture"
        evidence = [sys.executable, str(self.root / ".lean/bin/lean"), "--root", str(self.root), "evidence"]
        state = subprocess.check_output([*evidence, "state"], text=True).strip()
        recorded = subprocess.run([*evidence, "record-review", "--contract", high, "--reviewer", "independent",
                                   "--evidence", "fixture", "--verdict", "PASS", "--state", state],
                                  text=True, capture_output=True)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        for _ in range(2):  # An unchanged reviewed state reuses the receipt.
            passed = event()
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertNotIn("UNVERIFIED", passed.stdout)
        (self.root / ".agent-runtime/review.json").unlink()
        # A prior pass/mutable state baseline must not erase session commit coverage.
        missing = event()
        self.assertEqual(missing.returncode, 2, missing.stderr)
        self.assertIn("auth.py", missing.stderr)

    def test_codex_committed_high_risk_change_survives_resume_and_pass(self):
        self.check_committed_high_risk_session("codex")

    def test_claude_committed_high_risk_change_survives_resume_and_pass(self):
        self.check_committed_high_risk_session("claude")

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


class AuditHolesTests(HookFixture):
    """TCK015: holes found after 5.3.0 (help flags, memory exception, gate caches)."""

    def test_help_flag_after_double_dash_or_in_gate_scope_is_still_a_write(self):
        lean = "python3 .lean/bin/lean"
        for command in (f"{lean} gate scope -- rm -rf src -h",
                        f"{lean} gate scope -- sh -c \"echo x > f\" --help",
                        f"{lean} gate scope --only 'docs/*' -- cp a b -h",
                        f"{lean} gate scope echo hi -h",
                        f"{lean} --root . gate scope -- touch f --help",
                        f"{lean} evidence record-review -- -h",
                        "python3 -X dev .lean/bin/lean gate scope -- rm x",
                        "python3 -W ignore .lean/bin/lean gate accept-controls --reason x",
                        "python3 -X dev -W ignore .lean/bin/lean queue add --title x"):
            with self.subTest(write=command):
                self.assertTrue(contract_guard.shell_writes(command), command)
                self.assertEqual(self.tool("claude", "Bash", "no-contract", command=command).returncode, 2, command)
        for command in (f"{lean} -h", f"{lean} gate scope -h", f"{lean} gate scope --help",
                        f"{lean} evidence record-review --help", f"{lean} queue add -h",
                        "python3 -X dev .lean/bin/lean status", "python3 -c 'print(1)' .lean/bin/lean"):
            with self.subTest(read=command):
                self.assertFalse(contract_guard.shell_writes(command), command)

    def test_memory_exception_covers_only_user_memory_files(self):
        home = Path.home().resolve()
        allowed = (str(home / ".claude/projects/-Users-x-repo/memory/MEMORY.md"),
                   str(home / "Library/Application Support/orca/claude-profiles/abc/home/projects/p/memory/n.md"),
                   str(home / ".ccs/claude-profiles/work/projects/p/memory/note.md"),
                   "/tmp/scratch.txt")
        for path in allowed:
            with self.subTest(allowed=path):
                self.assertTrue(contract_guard.external_scratch_or_memory(self.root, "Write", {"file_path": path}))
        denied = ("/Users/x/work/main/.claude/hooks/memory/x.sh",
                  "/Users/x/work/main/.lean/lean/memory/.claude/x.py",
                  "/Users/x/x/memory/.claude/settings.json",
                  "/Users/x/work/repo/.claude/projects/p/memory/x.md",
                  str(home / ".claude/projects/p/memory/sub/x.md"),
                  str(home / ".claude/settings.json"),
                  "/opt/x/claude-profiles/z/projects/p/memory/x.sh")
        for path in denied:
            with self.subTest(denied=path):
                self.assertFalse(contract_guard.external_scratch_or_memory(self.root, "Write", {"file_path": path}))
                self.assertEqual(self.tool("claude", "Write", "no-contract", file_path=path).returncode, 2, path)

    def test_gate_caches_are_never_written_directly_even_with_a_contract(self):
        self.assertEqual(self.tool("claude", "Bash", "s1", command=f"{DECLARE} --contract '{LINE}'").returncode, 0)
        for cache in (".agent-runtime/gate-cache", ".agent-runtime/target-gate-cache", ".agent-runtime/gate-result.json"):
            for name, tool_input in (("Bash", {"command": f"echo forged > {cache}"}),
                                     ("Bash", {"command": f"cp /tmp/x {cache}"}),
                                     ("Bash", {"command": f"python3 -c \"open('{cache}','w').write('k')\""}),
                                     ("Write", {"file_path": str(self.root / cache), "content": "k"})):
                with self.subTest(cache=cache, tool=name, input=tool_input):
                    result = self.tool("claude", name, "s1", **tool_input)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("gate cache", result.stderr)
            name = cache.rsplit("/", 1)[1]
            spellings = [(f"Bash", {"command": f"echo k &> {cache}"}),
                         ("Bash", {"command": f"echo k &>> {cache}"}),
                         ("Bash", {"command": f"echo k > ./.agent-runtime/./{name}"}),
                         ("Bash", {"command": f"echo k > .agent-runtime//{name}"}),
                         ("Bash", {"command": f"cp x .agent-runtime/sub/../{name}"}),
                         ("Write", {"file_path": f"{self.root}/.agent-runtime/./{name}", "content": "k"}),
                         ("Write", {"file_path": f"{self.root}//.agent-runtime//{name}", "content": "k"})]
            if sys.platform == "darwin":  # Case-insensitive file system: the same file.
                spellings += [("Bash", {"command": f"echo k > .agent-runtime/{name.title()}"}),
                              ("Write", {"file_path": f"{self.root}/.agent-runtime/{name.upper()}", "content": "k"})]
            for name_, tool_input in spellings:
                with self.subTest(cache=cache, spelling=tool_input):
                    result = self.tool("claude", name_, "s1", **tool_input)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("gate cache", result.stderr)
            for command in (f"rm -f {cache}", f"cat {cache}"):
                with self.subTest(allowed=command):
                    self.assertEqual(self.tool("claude", "Bash", "s1", command=command).returncode, 0, command)


if __name__ == "__main__":
    unittest.main()

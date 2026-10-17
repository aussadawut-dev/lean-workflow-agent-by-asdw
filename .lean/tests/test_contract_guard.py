"""Task Contract declarations, the shared PreToolUse guard and both providers' Stop checks."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
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
                self.assertEqual(self.tool(provider, shell, session, command="git status").returncode, 2)
                self.assertEqual(self.tool(provider, "Read", session, file_path="x.py").returncode, 0)
                declared = self.tool(provider, shell, session, command=f"{DECLARE} <<'EOF'\n{BLOCK}\nEOF")
                self.assertEqual(declared.returncode, 0, declared.stderr)
                self.assertEqual(self.tool(provider, write[0], session, **write[1]).returncode, 0)
                self.assertEqual(self.tool(provider, shell, session, command="git status").returncode, 0)
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
        self.assertEqual(self.tool("codex", "mcp__docs__update").returncode, 2)
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

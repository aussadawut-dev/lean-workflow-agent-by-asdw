from pathlib import Path
import json
import os
import subprocess
import tarfile
import time

RUNTIME = Path(__file__).resolve().parent
ROOT = RUNTIME.parents[1]
EVIDENCE = ROOT / "docs/benchmarks/2026-10-23"
rows = []


def call(args, cwd):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


for version in ["v4.7.0", "current-dirty"]:
    tree = RUNTIME / f"{version}-overhead"
    tree.mkdir()
    with tarfile.open(EVIDENCE / f"{version}-snapshot.tar.gz") as archive:
        for member in archive.getmembers():
            member.name = member.name.partition("/")[2]
            if member.name:
                archive.extract(member, tree, filter="data")
    (tree / "benchmark-input.json").write_text('{"version":0,"value":"lean"}\n')
    (tree / "benchmark-check.py").write_text('''from pathlib import Path
import json,time
data=json.loads(Path("benchmark-input.json").read_text())
assert data["value"]=="lean" and data["version"] in [0,1]
time.sleep(0.5)
counter=Path(".agent-runtime/check-counter")
counter.parent.mkdir(exist_ok=True)
counter.write_text(str(int(counter.read_text() if counter.exists() else "0")+1))
''')
    (tree / ".lean/PROJECT.md").write_text("# Synthetic gate-control benchmark\n\nGit-visible input/check; fixed 0.5-second latency is synthetic.\n<!-- gate:start -->\n```sh\npython3 benchmark-check.py\n```\n<!-- gate:end -->\n")
    call(["git", "init", "-q", "--initial-branch=benchmark"], tree)
    call(["git", "add", "--all"], tree)
    call(["git", "-c", "user.name=Benchmark Fixture", "-c", "user.email=benchmark@localhost", "commit", "-qm", "test: pin synthetic cache fixture"], tree)
    counter = tree / ".agent-runtime/check-counter"
    for mode, repeat in [("uncached", n) for n in range(1,4)] + [("cache-prime",1)] + [("cache-repeat",n) for n in range(1,4)] + [("changed-input",1)]:
        if mode == "changed-input":
            (tree / "benchmark-input.json").write_text('{"version":1,"value":"lean"}\n')
        before = int(counter.read_text()) if counter.exists() else 0
        cmd = ["bash", str(tree/".lean/scripts/quality-gate.sh"), "--root", str(tree)]
        if mode != "uncached":
            cmd.append("--cache-tree")
        start = time.perf_counter()
        result = subprocess.run(cmd, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        delta = (int(counter.read_text()) if counter.exists() else 0) - before
        row = {"version":version,"mode":mode,"repeat":repeat,"seconds":round(time.perf_counter()-start,4),"exit_code":result.returncode,"check_invocations":delta,"load_average":os.getloadavg()}
        rows.append(row)
        (EVIDENCE / "gate-overhead-cache.json").write_text(json.dumps({"method":"Synthetic Git-visible JSON assertion plus fixed 0.5-second sleep; tests direct runner caching, not application speed. Three uncached and three repeated cached observations per version; changed tracked input must rerun checks. All runs sequential. A check invocation counter is ignored metadata, not a check input.","runs":rows},indent=2)+"\n")
        assert result.returncode == 0, result.stdout
        if mode in ["uncached","cache-prime","changed-input"]:
            assert delta == 1
        if mode == "cache-repeat":
            assert delta == (1 if version == "v4.7.0" else 0)
        print(json.dumps(row),flush=True)

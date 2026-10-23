from pathlib import Path
import hashlib
import json
import shutil
import subprocess

RUNTIME = Path(__file__).resolve().parent
ROOT = RUNTIME.parents[1]
EVIDENCE = ROOT / "docs/benchmarks/2026-10-23"
TARGET = ROOT / "targets/casetodian-next-v2"


def run(args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def main():
    tokens = json.loads((EVIDENCE / "context-tokens.json").read_text())
    assert tokens["encodings"]
    gates = json.loads((EVIDENCE / "gate-timings.json").read_text())
    for version in ["v4.7.0", "current-dirty"]:
        rows = [r for r in gates["runs"] if r["version"] == version]
        assert len(rows) == 1 and all(r["exit_code"] == 0 for r in rows)
    deploys = json.loads((EVIDENCE / "deployment-results.json").read_text())
    assert len(deploys) == 10
    assert all(r["outcome"] in ["passed", "rejected-as-expected"] for r in deploys)
    overhead = json.loads((EVIDENCE / "gate-overhead-cache.json").read_text())["runs"]
    assert len(overhead) == 16 and all(r["exit_code"] == 0 for r in overhead)
    assert not run(["git", "-C", str(TARGET), "status", "--porcelain"]), "Unexpected target changes; preserve and inspect"
    assert json.loads((ROOT / ".agent-runtime/active-target.json").read_text())["name"] == "casetodian-next-v2"
    modules = Path(run(["git", "-C", str(TARGET), "rev-parse", "--absolute-git-dir"]))
    assert modules.name == "casetodian-next-v2" and modules.parent.name == "targets" and "modules" in modules.parts
    registrations = run(["git", "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"])
    assert registrations == "submodule.targets/casetodian-next-v2.path targets/casetodian-next-v2"
    source = Path("/Users/x10/Workspace/Product/casetodian-workspace/targets/casetodian-next-v2")
    assert source.resolve() != TARGET.resolve() and source.is_dir()
    source_status_before = run(["git", "-C", str(source), "status", "--porcelain"])
    run(["python3", ".lean/scripts/submodule.py", "clear"])
    run(["git", "submodule", "deinit", "-f", "--", "targets/casetodian-next-v2"])
    run(["git", "rm", "-f", "--", "targets/casetodian-next-v2"])
    assert not (ROOT / ".gitmodules").read_text().strip()
    run(["git", "rm", "-f", "--", ".gitmodules"])
    shutil.rmtree(modules)
    records = ROOT / ".lean/targets/casetodian-next-v2"
    shutil.rmtree(records)
    if not any(records.parent.iterdir()):
        records.parent.rmdir()
    source_status_after = run(["git", "-C", str(source), "status", "--porcelain"])
    assert source_status_before == source_status_after
    context = json.loads(run(["python3", ".lean/scripts/submodule.py", "context"]))
    assert context["target"] is None and not TARGET.exists()
    containers = run(["docker", "ps", "-aq", "--filter", "label=lean.experiment=20261023"]).splitlines()
    mounts = json.loads(run(["docker", "inspect", "--format", "{{json .Mounts}}", "lean-benchmark-db-20261023"]))
    database_volumes = [m["Name"] for m in mounts if m["Type"] == "volume"]
    if containers:
        run(["docker", "rm", "-fv", *containers])
    networks = run(["docker", "network", "ls", "-q", "--filter", "label=lean.experiment=20261023"]).splitlines()
    if networks:
        run(["docker", "network", "rm", *networks])
    tags = run(["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}", "--filter", "label=lean.experiment=20261023"]).splitlines()
    tags = [t for t in tags if t.startswith("lean-benchmark-20261023-")]
    if tags:
        run(["docker", "image", "rm", *tags])
    assert not run(["docker", "ps", "-aq", "--filter", "label=lean.experiment=20261023"])
    assert not run(["docker", "network", "ls", "-q", "--filter", "label=lean.experiment=20261023"])
    remaining_volumes = run(["docker", "volume", "ls", "-q"]).splitlines()
    assert all(v not in remaining_volumes for v in database_volumes)
    retained = {}
    for name in ["timed_check.py", "measure_overhead.py", "deploy_experiment.py", "cleanup_experiment.py"]:
        data = (RUNTIME / name).read_bytes()
        (EVIDENCE / name).write_bytes(data)
        retained[name] = hashlib.sha256(data).hexdigest()
    # Runtime paths are ignored and contain private environment files; remove only
    # this task's uniquely named directory after retained results were verified.
    shutil.rmtree(RUNTIME)
    (EVIDENCE / "cleanup.json").write_text(json.dumps({"submodule_removed": True, "target_records_removed": True,
        "experiment_containers_removed": True, "experiment_network_removed": True,
        "experiment_image_tags_removed": True, "private_runtime_removed": True,
        "anonymous_database_volumes_removed": True, "shared_build_caches_preserved": True,
        "source_status_unchanged": True, "source_status": source_status_after,
        "retained_script_sha256": retained}, indent=2) + "\n")
    print("Experiment submodule, dedicated Docker resources and private runtime removed; evidence retained.")


if __name__ == "__main__":
    main()

from pathlib import Path
import base64
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import tarfile
import time
import urllib.error
import urllib.request

RUNTIME = Path(__file__).resolve().parent
ROOT = RUNTIME.parents[1]
APP = ROOT / "targets/casetodian-next-v2"
EVIDENCE = ROOT / "docs/benchmarks/2026-10-23"
NETWORK = "lean-benchmark-net-20261023"
INGRESS = "lean-benchmark-ingress-20261023"
PREFIX = "lean-benchmark-20261023"
DB = "lean-benchmark-db-20261023"
RESULTS = []


def run(args, cwd=None, log=None, env=None):
    if log:
        with (RUNTIME / log).open("a") as out:
            subprocess.run(args, cwd=cwd, env=env, check=True, stdout=out, stderr=subprocess.STDOUT)
        return ""
    return subprocess.check_output(args, cwd=cwd, env=env, text=True).strip()


def docker(*args):
    return run(["docker", *args])


def save():
    (EVIDENCE / "deployment-results.json").write_text(json.dumps(RESULTS, indent=2) + "\n")


def tree_hash(path):
    digest = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file() and not file.is_symlink():
            digest.update(str(file.relative_to(path)).encode() + b"\0" + file.read_bytes())
    return digest.hexdigest()


def http(port, path, timeout=4):
    if ":" in str(port):
        script = "fetch(process.argv[1],{signal:AbortSignal.timeout(Number(process.argv[2]))}).then(async r=>console.log(JSON.stringify({status:r.status,body:Buffer.from(await r.arrayBuffer()).toString('base64')}))).catch(()=>process.exit(2))"
        try:
            result = json.loads(docker("exec", f"{PREFIX}-api", "node", "-e", script, f"http://{port}{path}", str(timeout*1000)))
            return result["status"], base64.b64decode(result["body"])
        except subprocess.CalledProcessError as error:
            raise OSError("Internal HTTP probe unavailable") from error
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def wait_http(port, path, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            status, body = http(port, path)
            if status == 200:
                return body
        except (OSError, TimeoutError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Readiness timeout on loopback port {port} path {path}")


def remove_services():
    for service in ["web", "worker", "mcp", "api"]:
        name = f"{PREFIX}-{service}"
        found = subprocess.run(["docker", "container", "inspect", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if found.returncode == 0:
            docker("stop", "--time", "15", name)
            docker("rm", name)


def prepare_release(label, source, revision):
    context = RUNTIME / f"image-{label}"
    context.mkdir()
    tag = f"lean-benchmark-20261023-runtime:{label.lower()}"
    run(["docker", "build", "--label", "lean.experiment=20261023", "--label", f"org.opencontainers.image.revision={revision}", "-f", str(source / "deploy/docker/backend.Dockerfile"), "--target", "api", "-t", tag, str(source)], log=f"image-{label}-build.log")
    backend_image = docker("image", "inspect", "--format", "{{.Id}}", tag)
    hash_code = "const fs=require('fs'),p=require('path'),c=require('crypto');const root='/app/packages/server/dist',h=c.createHash('sha256');function walk(d){for(const f of fs.readdirSync(d).sort()){const x=p.join(d,f);if(fs.statSync(x).isDirectory())walk(x);else h.update(p.relative(root,x)).update('\\0').update(fs.readFileSync(x));}}walk(root);console.log(h.digest('hex'))"
    backend_hash = docker("run", "--rm", "--network", "none", "--entrypoint", "node", backend_image, "-e", hash_code)
    web_base = f"lean-benchmark-20261023-web-base:{label.lower()}"
    run(["docker", "build", "--label", "lean.experiment=20261023", "--label", f"org.opencontainers.image.revision={revision}", "-f", str(source / "deploy/docker/web.Dockerfile"), "--build-arg", "VITE_API_URL=", "-t", web_base, str(source)], log=f"image-{label}-build.log")
    holder = f"{PREFIX}-artifact-{label.lower()}"
    docker("create", "--name", holder, "--label", "lean.experiment=20261023", web_base)
    assets = context / "web"
    assets.mkdir()
    docker("cp", holder+":/usr/share/nginx/html/.", str(assets))
    docker("rm", holder)
    marker = json.dumps({"revision": revision, "backend_sha256": backend_hash}) + "\n"
    (assets / "release.json").write_text(marker)
    (context / "release.json").write_text(marker)
    (context / "Dockerfile").write_text(f"FROM {web_base}\nCOPY release.json /usr/share/nginx/html/release.json\n")
    (context / ".dockerignore").write_text("web/\n")
    web_tag = f"lean-benchmark-20261023-web:{label.lower()}"
    run(["docker", "build", "--label", "lean.experiment=20261023", "--label", f"org.opencontainers.image.revision={revision}", "-t", web_tag, str(context)], log=f"image-{label}-build.log")
    return {"release": label, "revision": revision, "runtime_image": backend_image,
            "web_image": docker("image", "inspect", "--format", "{{.Id}}", web_tag),
            "backend_sha256": backend_hash, "web_sha256": tree_hash(assets),
            "smoke_asset": (asset := re.search(r'src="([^"]+\.js)"', (assets / "index.html").read_text()).group(1)),
            "smoke_asset_sha256": hashlib.sha256((assets / asset.lstrip("/")).read_bytes()).hexdigest()}


def sentinel():
    return docker("exec", DB, "psql", "-U", "leanbench", "-d", "casetodian_benchmark", "-Atc", "SELECT value FROM lean_benchmark_sentinel WHERE id=1")


def deploy(version, release, action, recovery, bad=False):
    attempt = {"version": version, "action": action, "release": release,
               "recovery_image": recovery["runtime_image"], "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "outcome": "in-progress", "failure_injection": bad}
    RESULTS.append(attempt)
    save()
    start = time.perf_counter()
    remove_services()
    ports = {}
    config = RUNTIME / ("deploy-bad.env" if bad else "deploy.env")
    for service, port in [("api", 3001), ("mcp", 3002), ("worker", 3003)]:
        args = ["run", "-d", "--name", f"{PREFIX}-{service}", "--label", "lean.experiment=20261023", "--network", NETWORK,
                "--network-alias", service, "--env-file", str(config if service == "api" else RUNTIME / "deploy.env"),
                "--workdir", f"/app/apps/{service}", release["runtime_image"], "node", "--import", "tsx", "dist/server.js"]
        docker(*args)
        ports[service] = f"{service}:{port}"
    wait_http(ports["api"], "/health")
    if bad:
        status, body = http(ports["api"], "/ready", timeout=10)
        assert status == 503 and json.loads(body)["ok"] is False, "Injected bad database was not rejected"
        attempt.update(outcome="rejected-as-expected", readiness_status=status, seconds=round(time.perf_counter()-start, 3))
        save()
        return
    for service in ports:
        body = wait_http(ports[service], "/ready")
        assert json.loads(body)["ok"] is True
        actual = docker("inspect", "--format", "{{.Image}}", f"{PREFIX}-{service}")
        assert actual == release["runtime_image"]
    docker("create", "--name", f"{PREFIX}-web", "--label", "lean.experiment=20261023", "--network", NETWORK,
           "-p", "127.0.0.1::8080", release["web_image"])
    docker("network", "connect", INGRESS, f"{PREFIX}-web")
    docker("start", f"{PREFIX}-web")
    ports["web"] = docker("port", f"{PREFIX}-web", "8080/tcp").rsplit(":", 1)[1]
    assert json.loads(wait_http(ports["web"], "/health"))["ok"] is True
    assert docker("inspect", "--format", "{{.Image}}", f"{PREFIX}-web") == release["web_image"]
    marker = json.loads(wait_http(ports["web"], "/release.json"))
    assert marker == {"revision": release["revision"], "backend_sha256": release["backend_sha256"]}
    assert b"<html" in wait_http(ports["web"], "/").lower()
    assert hashlib.sha256(wait_http(ports["web"], release["smoke_asset"])).hexdigest() == release["smoke_asset_sha256"]
    assert http(ports["api"], "/api/v1/auth/me")[0] == 401
    assert http(ports["web"], "/api/v1/auth/me")[0] == 401
    assert sentinel() == "preserved-through-deploy-and-rollback"
    attempt.update(outcome="passed", seconds=round(time.perf_counter()-start, 3),
                   verified=["all-service-image-identities", "all-service-readiness", "web-health-html-release-marker", "served-javascript-content-hash", "anonymous-api-rejected", "web-proxy-anonymous-api-rejected", "database-sentinel-preserved"])
    save()
    print(version, action, attempt["seconds"], "PASS", flush=True)


def main():
    source_a = RUNTIME / "release-a-source"
    source_a.mkdir()
    revision_a = run(["git", "rev-parse", "HEAD~2"], cwd=APP)
    revision_b = run(["git", "rev-parse", "HEAD"], cwd=APP)
    archive = subprocess.check_output(["git", "archive", revision_a], cwd=APP)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(source_a, filter="data")
    print("Build release A then B using their production Dockerfiles, sequentially", flush=True)
    a = prepare_release("A", source_a, revision_a)
    b = prepare_release("B", APP, revision_b)
    assert a["backend_sha256"] != b["backend_sha256"], "Release runtime content must differ"
    (EVIDENCE / "deployment-artifacts.json").write_text(json.dumps([a, b], indent=2) + "\n")
    docker("network", "create", "--internal", "--label", "lean.experiment=20261023", NETWORK)
    docker("network", "create", "--label", "lean.experiment=20261023", INGRESS)
    docker("network", "connect", "--alias", "benchmark-db", NETWORK, DB)
    env = run(["node", "--env-file=.env", "-p", "process.env.DATABASE_URL"], cwd=APP)
    from urllib.parse import urlsplit, urlunsplit
    url = urlsplit(env)
    database = urlunsplit((url.scheme, url.netloc.split("@", 1)[0] + "@benchmark-db:5432", url.path, url.query, ""))
    synthetic = "\n".join([f"DATABASE_URL={database}", "NODE_ENV=production", "API_HOST_MCP=0", "PORT=3001", "MCP_PORT=3002", "WORKER_PORT=3003",
                             "KEYCLOAK_ISSUER=http://127.0.0.1:18081/realms/lean-benchmark", "KEYCLOAK_API_AUDIENCE=lean-benchmark-api", "KEYCLOAK_CLIENT_ID=lean-benchmark", f"KEYCLOAK_CLIENT_SECRET={secrets.token_urlsafe(24)}", "LOCAL_TEST_REALMS=0"]) + "\n"
    for name, value in [("deploy.env", synthetic), ("deploy-bad.env", synthetic.replace("@benchmark-db:5432", "@127.0.0.1:1"))]:
        (RUNTIME/name).write_text(value)
        (RUNTIME/name).chmod(0o600)
    run(["pnpm", "exec", "prisma", "migrate", "deploy"], cwd=APP, log="deploy-migrate.log")
    docker("exec", DB, "psql", "-U", "leanbench", "-d", "casetodian_benchmark", "-v", "ON_ERROR_STOP=1", "-c",
           "CREATE TABLE lean_benchmark_sentinel (id integer PRIMARY KEY, value text NOT NULL); INSERT INTO lean_benchmark_sentinel VALUES (1,'preserved-through-deploy-and-rollback');")
    for version in ["v4.7.0", "current-dirty"]:
        for release, action in [(a,"deploy-A"),(b,"deploy-B"),(a,"rollback-A")]:
            deploy(version, release, action, a)
        deploy(version, b, "inject-B-readiness-failure", a, bad=True)
        deploy(version, a, "recover-A-after-failed-B", a)
        remove_services()
    print("Sequential deployment and recovery smoke completed", flush=True)


if __name__ == "__main__":
    main()

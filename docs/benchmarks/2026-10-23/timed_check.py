from pathlib import Path
import subprocess,time,json,os,sys
app=Path(__file__).resolve().parents[2]/"targets/casetodian-next-v2"
commands={"lint":["pnpm","run","lint"],"test":["pnpm","run","test","--maxWorkers=1"],"build":["pnpm","run","build"]}
phase=sys.argv[1]; start=time.perf_counter()
log=Path(__file__).parent/f"check-{os.environ["BENCH_VERSION"]}-{os.environ["BENCH_REPEAT"]}-{phase}.log"
with log.open("w") as out:
 result=subprocess.run(commands[phase],cwd=app,stdout=out,stderr=subprocess.STDOUT)
row={"version":os.environ["BENCH_VERSION"],"repeat":int(os.environ["BENCH_REPEAT"]),"phase":phase,"seconds":round(time.perf_counter()-start,3),"exit_code":result.returncode}
with (Path(__file__).parent/"gate-components.jsonl").open("a") as out: out.write(json.dumps(row)+"\n")
print(log.read_text(),end="")
raise SystemExit(result.returncode)

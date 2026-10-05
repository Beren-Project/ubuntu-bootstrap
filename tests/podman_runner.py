"""One predictable container, observed ownership, and finally/signal cleanup."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
NAME = "ubuntu-bootstrap-integration"
LABEL = "org.beren-project.ubuntu-bootstrap"


def run(*args, capture=False, check=True):
    return subprocess.run(["podman", *args], text=True, check=check,
                          stdout=subprocess.PIPE if capture else None)


def audit():
    run("ps")
    run("ps", "-a")
    return json.loads(run("ps", "-a", "--format", "json", capture=True).stdout)


def discover_created(run_id):
    # A fixed name/project label alone cannot prove this invocation created it.
    return run("ps", "-a", "--no-trunc", "--filter", f"name=^{NAME}$", "--filter",
               f"label={LABEL}.run={run_id}", "--format", "{{.ID}}", capture=True).stdout.split()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse", action="store_true", help="Inspect and reuse a matching project container; never delete a borrowed container")
    parser.add_argument("--debug-retry", action="store_true", help="On failure, interactively retry a scenario in the SAME container; finally cleanup still applies")
    parser.add_argument("--scenario", choices=("all", "base", "engineering", "update"), default="all")
    args = parser.parse_args()
    report_dir = ROOT / "test-results"
    report_dir.mkdir(exist_ok=True)
    created = []
    run_id = uuid.uuid4().hex
    before, after = [], []
    started = time.time()
    exit_code = 1
    project_container = False

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        # No container creation, start, or image pull precedes these required checks.
        before = audit()
        matches = [c for c in before if NAME in c.get("Names", [])]
        if matches:
            inspection = json.loads(run("inspect", NAME, capture=True).stdout)[0]
            print(json.dumps(inspection, indent=2))
            if inspection["Config"].get("Labels", {}).get(LABEL) != "integration":
                raise RuntimeError("Predictable name belongs to an unrelated container; preserved")
            project_container = True
            if not args.reuse:
                raise RuntimeError("Existing project container inspected; use --reuse to debug it. No replacement created.")
            if not inspection["State"]["Running"]:
                run("start", NAME)
            print("VERIFY reused container: this run does not establish a fresh-install qualification")
        else:
            # Fixed upstream tag, no custom/uniquely tagged image builds.
            run("pull", "docker.io/library/ubuntu:26.04")
            try:
                identifier = run("run", "--detach", "--rm", "--name", NAME,
                    "--label", f"{LABEL}=integration", "--label", f"{LABEL}.release=26.04",
                    "--label", f"{LABEL}.run={run_id}",
                    "--memory", "6g", "--cpus", "4", "-e", "CI=1",
                    "-v", f"{ROOT}:/workspace:ro", "docker.io/library/ubuntu:26.04", "sleep", "infinity", capture=True).stdout.strip()
                created.append(identifier)
                project_container = True
            finally:
                # Cover an interruption after Podman creates but before stdout is consumed.
                if not created:
                    created.extend(discover_created(run_id))
            run("exec", NAME, "bash", "-eu", "-c", "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends sudo && useradd -m -s /bin/bash engineer && printf 'engineer ALL=(ALL) NOPASSWD: ALL\\n' > /etc/sudoers.d/engineer && chmod 0440 /etc/sudoers.d/engineer")
        scenario, freshness = args.scenario, "reused" if matches else "fresh"
        while True:
            result = run("exec", "-e", "HOME=/home/engineer", "-e", "PYTHONDONTWRITEBYTECODE=1",
                         "--user", "engineer", "--workdir", "/workspace", NAME,
                         "bash", "/workspace/tests/container-scenario", scenario, freshness, check=False)
            exit_code = result.returncode
            if not exit_code:
                # An all-scenario debugging retry may resume at the failed
                # stage. Finish remaining stages in this same container so
                # retrying engineering cannot silently omit update coverage.
                if args.scenario == "all" and scenario in ("base", "engineering"):
                    scenario = "engineering" if scenario == "base" else "update"
                    freshness = "reused"
                    print(f"VERIFY retry passed; continuing remaining {scenario} stage in SAME container", flush=True)
                    continue
                break
            if not args.debug_retry:
                break
            scenario = input("DEBUG failure inspected; retry SAME container (all/base/engineering/update), or Enter to clean up: ").strip()
            if scenario not in ("all", "base", "engineering", "update"):
                break
            freshness = "reused"
    except (RuntimeError, subprocess.CalledProcessError, KeyboardInterrupt) as error:
        print(f"ERROR integration: {error}", file=sys.stderr)
    finally:
        if project_container:
            for filename in ("receipts.json", "last-run.json", "bootstrap.log"):
                run("cp", f"{NAME}:/home/engineer/.local/state/ubuntu-bootstrap/{filename}",
                    str(report_dir / filename), check=False)
            run("cp", f"{NAME}:/home/engineer/inventory-size.json", str(report_dir / "inventory-size.json"), check=False)
        # Cleanup only IDs created by this invocation; never borrowed/unrelated containers.
        for identifier in created:
            run("rm", "--force", "--time", "0", identifier, check=False)
        try:
            after = audit()
            remaining = {c["Id"] for c in after}
            if any(identifier in remaining for identifier in created):
                print("ERROR project container leaked", file=sys.stderr)
                exit_code = 1
            unrelated_before = {c["Id"] for c in before} - set(created)
            if not unrelated_before.issubset(remaining):
                print("ERROR unrelated container inventory changed", file=sys.stderr)
                exit_code = 1
            run("images", "--format", "{{.Repository}}:{{.Tag}} {{.Size}}")
        except subprocess.CalledProcessError:
            exit_code = 1
        (report_dir / "podman-session.json").write_text(json.dumps({"exit_code": exit_code,
            "scenario": args.scenario, "run_id": run_id, "created": created, "before": before, "after": after,
            "seconds": round(time.time() - started, 2)}, indent=2) + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

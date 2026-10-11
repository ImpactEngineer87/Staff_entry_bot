"""Run with internet access on the same OS/CPU/Python as the offline computer."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def environment() -> dict:
    return {"system": platform.system(), "machine": platform.machine(),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "implementation": platform.python_implementation(),
            "platform_tag": sysconfig.get_platform()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, default=ROOT / "wheelhouse")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        print("Use Python 3.11 or newer; Python 3.12 is recommended.", file=sys.stderr)
        return 1
    directory = args.wheelhouse.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    requirements = ROOT / "requirements.txt"
    report = directory / "resolution_report.json"
    try:
        print("Collecting every dependency and building installation wheels…", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--wheel-dir", str(directory),
                        "--prefer-binary", "--retries", "8", "--timeout", "120",
                        "--disable-pip-version-check", "-r", str(requirements)], check=True)
        print("Checking that the packages can be resolved with internet disabled…", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed",
                        "--no-index", "--find-links", str(directory), "--report", str(report),
                        "--disable-pip-version-check", "-r", str(requirements)], check=True)
        resolved = json.loads(report.read_text(encoding="utf-8"))["install"]
        lock = directory / "requirements-offline.txt"
        lock.write_text("# All runtime dependencies resolved for this computer.\n" + "\n".join(sorted(
            f"{item['metadata']['name']}=={item['metadata']['version']}" for item in resolved)) + "\n",
                        encoding="utf-8")
        manifest = {"environment": environment(), "requirements_sha256": sha256(requirements),
                    "files": {path.name: sha256(path) for path in sorted(directory.glob("*.whl"))}}
        manifest["files"][lock.name] = sha256(lock)
        (directory / "offline_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        report.unlink(missing_ok=True)
        print(f"Offline package folder ready: {directory}\n"
              "Copy the entire project including wheelhouse to the offline computer.\n"
              "Also keep a matching Python installer. Wheels are OS/CPU/Python specific.")
        return 0
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError) as exc:
        print(f"Preparation did not finish: {exc}\n"
              "Keep downloaded files and rerun when the connection improves.\n"
              "On Ubuntu, evdev may need build-essential and python3-dev while building wheels.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

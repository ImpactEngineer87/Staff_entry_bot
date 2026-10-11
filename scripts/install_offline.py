"""Install exclusively from a previously prepared wheelhouse, without PyPI."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from prepare_offline import ROOT, environment, sha256


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, default=None)
    parser.add_argument("--include-build", action="store_true", help="Install a bundle that includes the EXE build tools.")
    parser.add_argument("--venv", type=Path, default=ROOT / ".venv")
    args = parser.parse_args()
    directory = (args.wheelhouse or ROOT / ("wheelhouse-build" if args.include_build else "wheelhouse")).resolve()
    venv = args.venv.resolve()
    try:
        manifest_path = directory / "offline_manifest.json"
        if not manifest_path.is_file():
            raise ValueError("No prepared offline bundle. Run scripts/prepare_offline.py with internet first.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if args.include_build and not manifest.get("includes_build_tools"):
            raise ValueError("This bundle has runtime packages only. Prepare it with --include-build first.")
        saved, current = manifest["environment"], environment()
        # Wheel compatibility checks below are ultimately performed by pip.
        for key in ("system", "machine", "python", "implementation"):
            if saved[key] != current[key]:
                raise ValueError(f"Offline packages were built for {key}={saved[key]}, "
                                 f"but this computer has {current[key]}. Prepare a matching bundle.")
        if sha256(ROOT / "requirements.txt") != manifest["requirements_sha256"]:
            raise ValueError("requirements.txt changed after package preparation. Prepare the bundle again.")
        if manifest.get("includes_build_tools"):
            if sha256(ROOT / "requirements-build.txt") != manifest.get("build_requirements_sha256"):
                raise ValueError("Build requirements changed after preparation. Prepare the build bundle again.")
        for name, expected in manifest["files"].items():
            if Path(name).name != name:
                raise ValueError("Invalid bundle filename.")
            path = directory / name
            if not path.is_file() or sha256(path) != expected:
                raise ValueError(f"Package file is missing or changed: {name}. Recopy the complete bundle.")
        if not (directory / "requirements-offline.txt").is_file():
            raise ValueError("The offline dependency lock is missing.")
        configuration = venv / "pyvenv.cfg"
        if configuration.is_file():
            match = re.search(r"^version\s*=\s*(\d+\.\d+)", configuration.read_text(encoding="utf-8"), re.MULTILINE)
            if match and match.group(1) != current["python"]:
                raise ValueError(f"Existing virtual environment uses Python {match.group(1)}. "
                                 "Choose a new --venv folder or recreate .venv with the matching Python.")
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--find-links", str(directory),
                        "--disable-pip-version-check", "-r", str(directory / "requirements-offline.txt")], check=True)
        subprocess.run([str(python), "-m", "pip", "check"], check=True)
        print(f'Installation complete. Start with:\n"{python}" "{ROOT / "main.py"}"')
        return 0
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Offline installation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

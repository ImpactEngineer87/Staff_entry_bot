import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import prepare_offline
import install_offline


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wheels = self.root / "wheelhouse"
        self.wheels.mkdir()
        (self.root / "requirements.txt").write_text("test-package==1.0\n", encoding="utf-8")
        self.args = ["install_offline.py", "--wheelhouse", str(self.wheels), "--venv", str(self.root / "env")]

    def bundle(self):
        (self.wheels / "test_package-1.0-py3-none-any.whl").write_bytes(b"test wheel")
        (self.wheels / "requirements-offline.txt").write_text("test-package==1.0\n", encoding="utf-8")
        data = {"environment": prepare_offline.environment(),
                "requirements_sha256": prepare_offline.sha256(self.root / "requirements.txt"),
                "files": {path.name: prepare_offline.sha256(path) for path in self.wheels.iterdir()}}
        (self.wheels / "offline_manifest.json").write_text(json.dumps(data), encoding="utf-8")
        return data

    def run_install(self):
        with patch.object(sys, "argv", self.args), patch.object(install_offline, "ROOT", self.root), \
                patch.object(install_offline.subprocess, "run") as run:
            result = install_offline.main()
        return result, run

    def test_missing_bundle_does_not_try_to_download(self):
        result, run = self.run_install()
        self.assertEqual(result, 1)
        run.assert_not_called()

    def test_changed_wheel_is_rejected_before_install(self):
        self.bundle()
        (self.wheels / "test_package-1.0-py3-none-any.whl").write_bytes(b"changed")
        result, run = self.run_install()
        self.assertEqual(result, 1)
        run.assert_not_called()

    def test_wrong_os_is_rejected_before_install(self):
        data = self.bundle()
        data["environment"]["system"] = "DifferentOS"
        (self.wheels / "offline_manifest.json").write_text(json.dumps(data), encoding="utf-8")
        result, run = self.run_install()
        self.assertEqual(result, 1)
        run.assert_not_called()

    def test_changed_requirements_need_a_new_bundle(self):
        self.bundle()
        (self.root / "requirements.txt").write_text("new-package==2.0\n", encoding="utf-8")
        result, run = self.run_install()
        self.assertEqual(result, 1)
        run.assert_not_called()

    def test_valid_bundle_install_uses_only_local_packages(self):
        self.bundle()
        result, run = self.run_install()
        self.assertEqual(result, 0)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 3)
        self.assertIn("--no-index", commands[1])
        self.assertIn("--find-links", commands[1])
        self.assertIn(str(self.wheels / "requirements-offline.txt"), commands[1])
        self.assertEqual(commands[2][-2:], ["pip", "check"])

    def build_bundle(self):
        data = self.bundle()
        requirements = self.root / "requirements-build.txt"
        requirements.write_text("-r requirements.txt\npyinstaller==6.22.3\n", encoding="utf-8")
        data["includes_build_tools"] = True
        data["build_requirements_sha256"] = prepare_offline.sha256(requirements)
        (self.wheels / "offline_manifest.json").write_text(json.dumps(data), encoding="utf-8")

    def test_runtime_bundle_cannot_be_used_for_an_exe_build(self):
        self.bundle()
        self.args.append("--include-build")
        result, run = self.run_install()
        self.assertEqual(result, 1)
        run.assert_not_called()

    def test_build_bundle_installs_without_a_package_index(self):
        self.build_bundle()
        self.args.append("--include-build")
        result, run = self.run_install()
        self.assertEqual(result, 0)
        self.assertIn("--no-index", run.call_args_list[1].args[0])

    def test_changed_build_requirements_are_rejected(self):
        self.build_bundle()
        (self.root / "requirements-build.txt").write_text("changed==1.0\n", encoding="utf-8")
        self.args.append("--include-build")
        result, run = self.run_install()
        self.assertEqual(result, 1)
        run.assert_not_called()

    def test_existing_environment_cannot_mix_python_versions(self):
        self.bundle()
        environment = self.root / "env"
        environment.mkdir()
        (environment / "pyvenv.cfg").write_text("version = 0.0.1\n", encoding="utf-8")
        result, run = self.run_install()
        self.assertEqual(result, 1)
        run.assert_not_called()

    def test_prepare_resolves_transitive_versions_and_records_hashes(self):
        args = ["prepare_offline.py", "--wheelhouse", str(self.wheels)]

        def fake_run(command, **kwargs):
            if "wheel" in command:
                (self.wheels / "test_package-1.0-py3-none-any.whl").write_bytes(b"test")
            elif "--report" in command:
                path = Path(command[command.index("--report") + 1])
                path.write_text(json.dumps({"install": [
                    {"metadata": {"name": "test-package", "version": "1.0"}},
                    {"metadata": {"name": "dependency", "version": "2.0"}}]}), encoding="utf-8")

        with patch.object(sys, "argv", args), patch.object(prepare_offline, "ROOT", self.root), \
                patch.object(prepare_offline.subprocess, "run", side_effect=fake_run) as run:
            self.assertEqual(prepare_offline.main(), 0)
        lock = (self.wheels / "requirements-offline.txt").read_text(encoding="utf-8")
        self.assertIn("test-package==1.0", lock)
        self.assertIn("dependency==2.0", lock)
        self.assertIn("--no-index", run.call_args_list[1].args[0])
        manifest = json.loads((self.wheels / "offline_manifest.json").read_text(encoding="utf-8"))
        self.assertIn("requirements-offline.txt", manifest["files"])
        self.assertFalse((self.wheels / "resolution_report.json").exists())

    def test_build_preparation_locks_build_tools_and_runtime_dependencies(self):
        self.build_bundle()
        args = ["prepare_offline.py", "--include-build", "--wheelhouse", str(self.wheels)]

        def fake_run(command, **kwargs):
            if "--report" in command:
                path = Path(command[command.index("--report") + 1])
                path.write_text(json.dumps({"install": [
                    {"metadata": {"name": "test-package", "version": "1.0"}},
                    {"metadata": {"name": "pyinstaller", "version": "6.22.3"}},
                    {"metadata": {"name": "build-dependency", "version": "2.0"}}]}), encoding="utf-8")

        with patch.object(sys, "argv", args), patch.object(prepare_offline, "ROOT", self.root), \
                patch.object(prepare_offline.subprocess, "run", side_effect=fake_run) as run:
            self.assertEqual(prepare_offline.main(), 0)
        self.assertIn(str(self.root / "requirements-build.txt"), run.call_args_list[0].args[0])
        lock = (self.wheels / "requirements-offline.txt").read_text(encoding="utf-8")
        self.assertIn("pyinstaller==6.22.3", lock)
        self.assertIn("build-dependency==2.0", lock)
        manifest = json.loads((self.wheels / "offline_manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["includes_build_tools"])
        self.assertEqual(manifest["build_requirements_sha256"],
                         prepare_offline.sha256(self.root / "requirements-build.txt"))


if __name__ == "__main__":
    unittest.main()

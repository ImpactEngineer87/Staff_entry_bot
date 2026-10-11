import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from staffbot import runtime

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_windows.py"
specification = importlib.util.spec_from_file_location("staffbot_windows_builder", SCRIPT)
builder = importlib.util.module_from_spec(specification)
specification.loader.exec_module(builder)


class RuntimePackagingTests(unittest.TestCase):
    def test_source_logs_keep_existing_location(self):
        with patch.object(runtime.sys, "frozen", False, create=True):
            root = Path("source")
            self.assertEqual(runtime.logs_directory(root), root / "logs")

    def test_frozen_resources_and_persistent_logs_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(runtime.sys, "frozen", True, create=True), \
                 patch.object(runtime.sys, "_MEIPASS", str(root / "extraction"), create=True), \
                 patch.object(runtime.sys, "platform", "win32"), \
                 patch.dict(runtime.os.environ, {"LOCALAPPDATA": str(root / "user")}):
                self.assertEqual(runtime.resource_root(), root / "extraction")
                self.assertEqual(runtime.logs_directory(), root / "user" / "StaffEntryBot" / "logs")
                self.assertNotIn(root / "extraction", runtime.logs_directory().parents)

    def test_frozen_practice_is_a_new_instance_not_a_python_script(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = str(Path(directory) / "StaffEntryBot.exe")
            with patch.object(runtime.sys, "frozen", True, create=True), \
                 patch.object(runtime.sys, "executable", executable):
                command, working, environment = runtime.practice_launch(Path("temporary-extraction"))
            self.assertEqual(command, [executable, "--practice"])
            self.assertEqual(working, Path(directory).resolve())
            self.assertEqual(environment["PYINSTALLER_RESET_ENVIRONMENT"], "1")
            self.assertNotIn("demo_form.py", " ".join(command))

    def test_source_practice_still_uses_python(self):
        with patch.object(runtime.sys, "frozen", False, create=True):
            root = Path("source")
            command, working, environment = runtime.practice_launch(root)
            self.assertEqual(command, [sys.executable, str(root / "demo_form.py")])
            self.assertEqual(working, root)


class BuildPackagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "BUILD_EXE.md").write_text("Build guide", encoding="utf-8")

    def test_non_windows_build_is_rejected(self):
        with patch.object(sys, "platform", "linux"), patch.object(sys, "argv", ["build_windows.py"]), \
             patch.object(builder.subprocess, "run") as run:
            self.assertEqual(builder.main(), 1)
        run.assert_not_called()

    def run_builder(self, smoke_ok):
        output = self.root / "dist"
        args = ["build_windows.py", "--output", str(output), "--work", str(self.root / "build")]

        def execute(command, **kwargs):
            if "PyInstaller" in command:
                (output / "StaffEntryBot.exe").write_bytes(b"simulated Windows binary")
            elif "--self-test" in command:
                Path(command[-1]).write_text(json.dumps({"ok": smoke_ok, "frozen": True}), encoding="utf-8")

        with patch.object(sys, "platform", "win32"), patch.object(sys, "argv", args), \
             patch.object(builder, "ROOT", self.root), \
             patch.object(builder.importlib.metadata, "version", return_value="6.22.3"), \
             patch.object(builder.subprocess, "run", side_effect=execute) as run:
            result = builder.main()
        return result, run, output

    def test_build_runs_executable_check_and_writes_checksum(self):
        result, run, output = self.run_builder(True)
        self.assertEqual(result, 0)
        self.assertEqual(len(run.call_args_list), 2)
        self.assertIn("StaffEntryBot.spec", run.call_args_list[0].args[0][-1])
        self.assertIn("--self-test", run.call_args_list[1].args[0])
        self.assertTrue((output / "StaffEntryBot.exe.sha256").is_file())
        self.assertEqual((output / "BUILD_EXE.md").read_text(encoding="utf-8"), "Build guide")

    def test_failed_executable_check_is_not_reported_as_ready(self):
        result, run, output = self.run_builder(False)
        self.assertEqual(result, 1)
        self.assertFalse((output / "StaffEntryBot.exe.sha256").exists())


if __name__ == "__main__":
    unittest.main()

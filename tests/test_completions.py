"""Real generators/filesystem/Zsh with controlled application fixtures, no network."""
from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch
import unittest

from bootstrap_lib import cli, completions
from bootstrap_lib.platform import BootstrapError
from bootstrap_lib.runtime import digest
from test_logic import context
import tempfile


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.ctx = context(self.home)
        self.ctx.env["HOME"] = str(self.home)
        self.binary = self.home / "fixture"
        self.destination = self.home / ".zfunc/_fixture"
        self.spec = {"command": "fixture", "profile": "cargo", "owner": "fnm",
                     "executable": "fixture", "arguments": ["completions", "zsh"]}
        self.application()
        self.stdout = redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def application(self, version=1, mode="valid"):
        self.binary.write_text(f'''#!/usr/bin/python3
import os, pathlib, sys
VERSION={version!r}
MODE={mode!r}
if "--version" in sys.argv:
    print("fixture", VERSION)
else:
    with pathlib.Path(__file__).with_name("calls").open("a") as stream:
        stream.write(str(os.geteuid()) + "\\n")
    if MODE == "empty":
        sys.exit(0)
    if MODE == "header":
        print("#compdef unrelated-command")
        sys.exit(0)
    print("#compdef fixture")
    print("#uid:", os.geteuid())
    if MODE == "comments":
        sys.exit(0)
    if MODE == "failure":
        print("partial output")
        sys.exit(7)
    elif MODE == "syntax":
        print("if then")
    else:
        print("_fixture() {{ compadd -- version" + str(VERSION) + "; }}")
''')
        self.binary.chmod(0o755)
        self.ctx.record("fnm", [self.binary], manager="fixture")

    def provision(self):
        completions.provision_one(self.ctx, self.spec, [])

    def test_creates_normal_user_directory_and_valid_autoload_file(self):
        self.provision()
        self.assertEqual(self.destination.parent.stat().st_uid, os.getuid())
        self.assertEqual(self.destination.stat().st_uid, os.getuid())
        self.assertTrue(self.destination.stat().st_size)
        self.assertEqual((self.home / "calls").read_text().strip(), str(os.getuid()))
        subprocess.run(["zsh", "-fc", 'fpath=("$1" $fpath); autoload -Uz compinit; compinit -i -D; [[ $_comps[fixture] == _fixture ]]',
                        "test", str(self.destination.parent)], check=True, env=self.ctx.env)

    def test_rerun_and_current_update_preserve_file_without_regeneration(self):
        self.provision()
        before = self.destination.stat().st_mtime_ns
        self.provision()
        self.ctx.args.update = True
        self.provision()
        self.assertEqual(self.destination.stat().st_mtime_ns, before)
        self.assertEqual(len((self.home / "calls").read_text().splitlines()), 1)
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_updated_application_regenerates_its_completion(self):
        self.provision()
        before = self.destination.read_bytes()
        self.application(version=2)
        self.ctx.args.update = True
        self.provision()
        self.assertNotEqual(self.destination.read_bytes(), before)
        self.assertIn("version2", self.destination.read_text())
        self.assertEqual(len((self.home / "calls").read_text().splitlines()), 2)

    def test_cargo_style_proxy_detects_toolchain_version_change(self):
        version = self.home / "toolchain-version"
        version.write_text("1")
        proxy = self.home / "cargo-proxy"
        proxy.write_text('#!/usr/bin/python3\nfrom pathlib import Path\nprint("cargo", Path(__file__).with_name("toolchain-version").read_text())\n')
        proxy.chmod(0o755)
        self.ctx.record("fnm", [self.binary, proxy], manager="fixture")
        self.spec["version_executable"] = "cargo-proxy"
        self.provision()
        binary_hash = digest(self.binary)
        version.write_text("2")
        self.provision()
        self.assertEqual(digest(self.binary), binary_hash)
        self.assertEqual(self.ctx.receipts["completion:fixture"]["source"]["version"], "cargo 2")
        self.assertEqual(len((self.home / "calls").read_text().splitlines()), 2)

    def test_generation_failure_keeps_prior_file_and_receipt(self):
        self.provision()
        before = self.destination.read_bytes(), self.destination.stat().st_mtime_ns
        receipt = self.ctx.receipts["completion:fixture"]
        self.application(version=2, mode="failure")
        with self.assertRaisesRegex(BootstrapError, "generation failed.*exit 7"):
            self.provision()
        self.assertEqual((self.destination.read_bytes(), self.destination.stat().st_mtime_ns), before)
        self.assertEqual(self.ctx.receipts["completion:fixture"], receipt)
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_empty_or_invalid_syntax_never_replaces_working_file(self):
        self.provision()
        before = digest(self.destination)
        for mode in ("empty", "syntax", "header", "comments"):
            with self.subTest(mode=mode):
                self.application(version=2, mode=mode)
                with self.assertRaises(BootstrapError):
                    self.provision()
                self.assertEqual(digest(self.destination), before)
                self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_first_generation_failure_leaves_no_partial_completion(self):
        self.application(mode="failure")
        with self.assertRaises(BootstrapError):
            self.provision()
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.destination.parent.iterdir()), [])
        self.assertNotIn("completion:fixture", self.ctx.receipts)

    def test_root_rejected_before_any_generator_or_directory_creation(self):
        with patch("os.geteuid", return_value=0), patch("subprocess.run", side_effect=AssertionError("generator ran")):
            with self.assertRaisesRegex(BootstrapError, "never root"):
                self.provision()
        self.assertFalse(self.destination.parent.exists())

    def test_source_tool_must_be_owned_before_generator_runs(self):
        self.binary.write_text("unmanaged replacement")
        with self.assertRaisesRegex(BootstrapError, "changed outside bootstrap"):
            self.provision()
        self.assertFalse((self.home / "calls").exists())

    def test_unmanaged_and_changed_completions_are_preserved(self):
        self.destination.parent.mkdir()
        self.destination.write_text("personal completion")
        with self.assertRaisesRegex(BootstrapError, "completion preserved"):
            self.provision()
        self.assertEqual(self.destination.read_text(), "personal completion")
        self.destination.unlink()
        self.provision()
        self.destination.write_text("externally changed completion")
        with self.assertRaisesRegex(BootstrapError, "completion preserved"):
            self.provision()
        self.assertEqual(self.destination.read_text(), "externally changed completion")

    def test_symlink_directory_and_file_are_refused(self):
        real = self.home / "other"
        real.mkdir()
        self.destination.parent.symlink_to(real)
        with self.assertRaisesRegex(BootstrapError, "symlink"):
            self.provision()
        self.assertEqual(list(real.iterdir()), [])
        self.destination.parent.unlink()
        self.destination.parent.mkdir()
        target = real / "personal"
        target.write_text("personal")
        self.destination.symlink_to(target)
        with self.assertRaisesRegex(BootstrapError, "regular completion"):
            self.provision()
        self.assertEqual(target.read_text(), "personal")

    def test_insecure_directory_is_refused_even_on_current_rerun(self):
        self.provision()
        self.destination.parent.chmod(0o777)
        with self.assertRaisesRegex(BootstrapError, "writable by group/others"):
            self.provision()

    def test_new_directory_is_secure_with_permissive_umask(self):
        previous = os.umask(0o002)
        try:
            self.provision()
        finally:
            os.umask(previous)
        self.assertEqual(self.destination.parent.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o644)

    def test_discoverable_system_completion_needs_no_user_copy_or_generator(self):
        with patch("bootstrap_lib.completions.system_completion", return_value=self.binary):
            self.provision()
        self.assertFalse(self.destination.parent.exists())
        self.assertFalse((self.home / "calls").exists())
        self.assertEqual(self.ctx.receipts["completion:fixture"]["provider"], "system")

    def test_skipped_unqualified_tool_does_not_run_a_generator(self):
        self.ctx.receipts.pop("fnm")
        self.provision()
        self.assertFalse((self.home / "calls").exists())
        self.assertFalse(self.destination.parent.exists())

    def test_optional_completion_failure_reports_failure_after_app_success(self):
        def provision(ctx, profile):
            if profile == "nvim":
                raise BootstrapError("optional generator failure")
        with ExitStack() as stack:
            for path in ("apt.base", "rust.rust", "rust.cargo", "python.managed_python", "node.node", "dotfiles.dotfiles", "editors.nvim"):
                stack.enter_context(patch("bootstrap_lib.cli." + path))
            stack.enter_context(patch("bootstrap_lib.cli.Context", return_value=self.ctx))
            stack.enter_context(patch.object(self.ctx, "run"))
            stack.enter_context(patch("bootstrap_lib.cli.shell.choose", return_value=None))
            stack.enter_context(patch("bootstrap_lib.cli.completions.provision", side_effect=provision))
            result = cli.main(["--non-interactive", "--no-change-shell", "--nvim"])
        self.assertEqual(result, 1)
        final = json.loads((self.ctx.state / "last-run.json").read_text())
        self.assertEqual(final["failed"], ["nvim completions"])

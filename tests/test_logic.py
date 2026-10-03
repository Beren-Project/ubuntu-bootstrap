"""Logic/ownership regressions, using temporary homes and real filesystem checks."""
import argparse
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import pwd
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bootstrap_lib.config import ROOT, load_manifest, resolve, restore_args
from bootstrap_lib import cli, dotfiles, openmodelica, rust, shell, system_assets
from bootstrap_lib.platform import BootstrapError, detect, invoking_user
from bootstrap_lib.runtime import Context, digest, extract, release


def context(home, **overrides):
    args = SimpleNamespace(non_interactive=True, update=False, adopt=[], attempt_unqualified=[],
                           yes=False, change_shell=False)
    for name, value in overrides.items():
        setattr(args, name, value)
    with patch.dict(os.environ, {"XDG_DATA_HOME": str(home / "data"), "XDG_CACHE_HOME": str(home / "cache"),
                                "XDG_STATE_HOME": str(home / "state")}, clear=False):
        return Context(load_manifest(), args, pwd.getpwuid(os.getuid()), home, "amd64")


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.config = load_manifest()

    def test_default_and_prohibited_package_sets(self):
        self.assertTrue({"gh", "zsh", "wl-clipboard", "python3"}.issubset(self.config["apt"]["base"]))
        self.assertFalse(set(self.config["apt"]["build"]) & set(self.config["apt"]["base"]))
        self.assertEqual(len(self.config["cargo_tools"]), 11)
        self.assertFalse({"zellij", "tokei", "watchexec-cli", "mdbook", "cargo-outdated", "cargo-xwin",
                          "skim", "xplr", "yazi-fm"} & {t["crate"] for t in self.config["cargo_tools"]})

    def test_ngspice_implies_build_openmodelica_does_not(self):
        self.assertEqual(resolve(self.config, ["ngspice"]), ["apt", "build", "ngspice"])
        self.assertEqual(resolve(self.config, ["openmodelica"]), ["apt", "openmodelica"])
        self.assertEqual(self.config["apt"]["openmodelica"], ["gnupg"])

    def test_dependency_cycle_unknown_and_duplicates(self):
        c = deepcopy(self.config)
        c["profiles"]["apt"]["depends"] = ["cargo"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            resolve(c, ["cargo"])
        with self.assertRaisesRegex(ValueError, "Unknown"):
            resolve(self.config, ["unknown"])
        result = resolve(self.config, ["ngspice", "build", "ngspice"])
        self.assertEqual(len(result), len(set(result)))

    def test_exact_pinned_five_file_selection(self):
        self.assertEqual(self.config["dotfiles"]["revision"], "c44e4b8c8299f2b05ee225678daead77bf5bfbd1")
        expected = [".zshrc", ".zshenv", ".gitconfig", ".tmux.conf", ".config/starship.toml"]
        self.assertEqual(self.config["dotfiles"]["files"], expected)
        preview = restore_args(self.config)
        self.assertEqual(preview[:3], ["/usr/bin/python3", "-B", "scripts/restore.py"])
        self.assertEqual(preview[3:], [arg for name in expected for arg in ("--file", name)])
        self.assertEqual(restore_args(self.config, True), [*preview, "--apply"])
        self.assertNotIn("--profile", preview)

    def test_arm_metadata_and_neovim_archives(self):
        for spec in [*self.config["profiles"].values(), *self.config["cargo_tools"]]:
            self.assertIn(spec["arm64"], ("supported", "unqualified"))
        self.assertIn("arm64", self.config["nvim"]["archives"]["arm64"])
        self.assertNotIn("x86_64", self.config["nvim"]["archives"]["arm64"])
        fnm = next(t for t in self.config["cargo_tools"] if t["crate"] == "fnm")
        self.assertIn("fnm-arm64.zip", fnm["binstall_urls"]["arm64"])

    def test_no_ordinary_versions_pinned(self):
        for tool in self.config["cargo_tools"]:
            self.assertNotIn("version", tool)
        self.assertEqual(self.config["python"]["channel"], "cpython")
        self.assertEqual(self.config["node"]["channel"], "lts")


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.config = load_manifest()

    def test_supported_architectures_and_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "os-release"
            path.write_text('ID=ubuntu\nVERSION_ID="26.04"\nVERSION_CODENAME=resolute\n')
            self.assertEqual(detect(self.config, path, "x86_64"), "amd64")
            self.assertEqual(detect(self.config, path, "aarch64"), "arm64")
            with self.assertRaisesRegex(BootstrapError, "architecture"):
                detect(self.config, path, "riscv64")
            for text in ('ID=debian\nVERSION_ID=26.04\nVERSION_CODENAME=resolute',
                         'ID=ubuntu\nVERSION_ID=24.04\nVERSION_CODENAME=noble',
                         'ID=ubuntu\nVERSION_ID=26.04\nVERSION_CODENAME=noble'):
                path.write_text(text)
                with self.assertRaisesRegex(BootstrapError, "Only Ubuntu"):
                    detect(self.config, path, "x86_64")

    def test_root_rejected(self):
        with patch("os.geteuid", return_value=0):
            with self.assertRaisesRegex(BootstrapError, "normal user"):
                invoking_user()

    def test_automation_requires_shell_choice(self):
        with patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.arguments(["--non-interactive"])
        args = cli.arguments(["--non-interactive", "--no-change-shell"])
        self.assertFalse(args.change_shell)


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.ctx = context(self.home)
        self.binary = self.home / "tool"

    def test_missing_owned_component_is_installable(self):
        self.assertFalse(self.ctx.owned("tool", [self.binary]))

    def test_unmanaged_name_is_not_adopted(self):
        self.binary.write_text("unrelated installation")
        with self.assertRaisesRegex(BootstrapError, "Unmanaged"):
            self.ctx.owned("tool", [self.binary])
        self.assertEqual(self.binary.read_text(), "unrelated installation")
        self.assertNotIn("tool", self.ctx.receipts)

    def test_explicit_adoption_and_metadata_recovery(self):
        self.binary.write_text("reviewed")
        self.ctx.args.adopt = ["tool"]
        self.assertTrue(self.ctx.owned("tool", [self.binary]))
        self.ctx.record("tool", [self.binary], manager="fixture")
        self.ctx.args.adopt = []
        self.assertTrue(self.ctx.owned("tool", [self.binary]))
        self.ctx.receipts_path.unlink()
        rebuilt = context(self.home, adopt=["tool"])
        self.assertTrue(rebuilt.owned("tool", [self.binary]))

    def test_external_replacement_is_preserved_and_refused(self):
        self.binary.write_text("managed")
        self.ctx.record("tool", [self.binary])
        self.binary.write_text("externally changed")
        with self.assertRaisesRegex(BootstrapError, "changed outside"):
            self.ctx.owned("tool", [self.binary])
        self.assertEqual(self.binary.read_text(), "externally changed")

    def test_receipt_cannot_add_desired_components(self):
        self.ctx.record("unrelated-user-tool", [])
        self.assertNotIn("unrelated-user-tool", resolve(self.ctx.config, self.ctx.config["defaults"]))

    def test_diagnostic_state_rejects_symlink_and_is_replaced(self):
        self.ctx.write_state("last-run.json", {"failed": []})
        self.ctx.write_state("last-run.json", {"failed": ["example"]})
        destination = self.ctx.state / "last-run.json"
        self.assertEqual(json.loads(destination.read_text()), {"failed": ["example"]})
        destination.unlink()
        self.binary.write_text("user state")
        destination.symlink_to(self.binary)
        with self.assertRaisesRegex(BootstrapError, "unsafe diagnostic"):
            self.ctx.write_state("last-run.json", {})
        self.assertEqual(self.binary.read_text(), "user state")

    def test_cargo_update_ownership_boundary(self):
        owned = {t["crate"] for t in self.ctx.config["cargo_tools"]}
        commands = [rust.update_argv(self.ctx, name, "1.2.3") for name in owned]
        self.assertEqual({command[-1] for command in commands}, owned)
        for command in commands:
            self.assertNotIn("-a", command)
            self.assertNotIn("--all", command)
            self.assertNotIn("unrelated-user-tool", command)

    def test_binstall_legacy_registry_is_authoritative(self):
        cargo = self.home / ".cargo"
        cargo.mkdir()
        (cargo / ".crates2.json").write_text('{"installs": {}}')
        (cargo / ".crates.toml").write_text('[v1]\n"starship 1.26.0 (registry+https://github.com/rust-lang/crates.io-index)" = ["starship"]\n')
        self.assertEqual(rust.crate_state(self.ctx, {"crate": "starship", "bins": ["starship"]}), "1.26.0")

    def test_multiline_executable_version(self):
        self.assertEqual(rust.executable_version("eza - replacement for ls\nv0.23.5\nhttps://github.com/eza-community/eza"), "0.23.5")
        self.assertEqual(rust.executable_version("cargo 22.1.1"), "22.1.1")
        self.assertIsNone(rust.executable_version("not a version"))

    def test_arm_default_no_and_explicit_opt_in(self):
        self.ctx.arch = "arm64"
        self.assertTrue(self.ctx.arm_allowed("rust", "supported"))
        with patch("sys.stdout", new=io.StringIO()):
            self.assertFalse(self.ctx.arm_allowed("dotfiles", "unqualified"))
            self.ctx.args.attempt_unqualified = ["dotfiles"]
            self.assertTrue(self.ctx.arm_allowed("dotfiles", "unqualified"))

    def test_yes_accepts_arm_default_no_without_prompt(self):
        self.ctx.arch = "arm64"
        self.ctx.args.non_interactive = False
        self.ctx.args.yes = True
        with patch("builtins.input", side_effect=AssertionError("unnecessary prompt")), patch("sys.stdout", new=io.StringIO()):
            self.assertFalse(self.ctx.arm_allowed("ngspice", "unqualified"))

    def test_root_only_commands_are_explicit(self):
        completed = SimpleNamespace(returncode=0)
        with patch("subprocess.run", return_value=completed) as call:
            self.ctx.run(["cargo", "install", "fixture"])
            self.assertEqual(call.call_args.args[0][0], "cargo")
            self.ctx.run(["apt-get", "install", "gh"], sudo=True)
            self.assertEqual(call.call_args.args[0][:2], ["/usr/bin/sudo", "-n"])

    def test_symlinked_managed_directory_rejected(self):
        from bootstrap_lib.runtime import safe_directory
        real = self.home / "real"
        real.mkdir()
        link = self.home / "link"
        link.symlink_to(real)
        with self.assertRaisesRegex(BootstrapError, "symlink"):
            safe_directory(link / "nested")


class IntegrityTests(unittest.TestCase):
    def test_archive_traversal_and_link_rejected(self):
        for name, kind in (("../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                archive = Path(directory) / "bad.tar"
                with tarfile.open(archive, "w") as tree:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "../../escape"
                    tree.addfile(member)
                with self.assertRaisesRegex(BootstrapError, "Unsafe"):
                    extract(archive, Path(directory) / "extracted")

    def test_checksum_mismatch_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = context(Path(directory))
            with patch("bootstrap_lib.runtime.get_bytes", return_value=b"bad download"):
                with self.assertRaisesRegex(BootstrapError, "SHA-256 mismatch"):
                    ctx.download("https://example.invalid/archive", "0" * 64, "archive")
            self.assertFalse((ctx.cache / "archive").exists())

    def test_valid_cached_artifact_requires_no_network(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = context(Path(directory))
            artifact = ctx.cache / "artifact"
            artifact.write_bytes(b"verified")
            with patch("bootstrap_lib.runtime.get_bytes", side_effect=AssertionError("network used")):
                self.assertEqual(ctx.download("https://example.invalid", digest(artifact), "artifact"), artifact)

    def test_release_requires_sha256_and_correct_asset(self):
        payload = {"tag_name": "v1", "assets": [{"name": "arm64.tgz", "digest": None}]}
        with patch("bootstrap_lib.runtime.get_bytes", return_value=json.dumps(payload).encode()):
            with self.assertRaisesRegex(BootstrapError, "no SHA-256"):
                release("owner/repo", "arm64.tgz")
            with self.assertRaisesRegex(BootstrapError, "architecture"):
                release("owner/repo", "x86_64.tgz")

    def test_checkout_checks_sha_origin_dirty_and_index_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            config = load_manifest()["dotfiles"]
            base = [config["url"], config["revision"], "", "H scripts/restore.py"]
            for position, replacement in ((0, "wrong origin"), (1, "0" * 40), (2, " M scripts/restore.py"),
                                           (3, "h scripts/restore.py"), (3, "S scripts/restore.py")):
                values = list(base)
                values[position] = replacement
                with patch("bootstrap_lib.dotfiles.git", side_effect=values):
                    with self.assertRaises(BootstrapError):
                        dotfiles.verify_checkout(None, root, config["url"], config["revision"])
            with patch("bootstrap_lib.dotfiles.git", side_effect=base):
                dotfiles.verify_checkout(None, root, config["url"], config["revision"])


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.destination = self.root / "installed"
        self.destination.mkdir()
        (self.destination / "binary").write_text("working first version")
        self.staged = self.root / "staged"
        self.staged.mkdir()
        (self.staged / "binary").write_text("second version")
        # Exercise the real copy/rename commands in a temporary directory; no sudo needed.
        self.ctx = SimpleNamespace(run=self.run_command, status=lambda *args: None)

    def run_command(self, argv, *, sudo=False):
        self.assertTrue(sudo)
        subprocess.run(list(map(str, argv)), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_successive_replacements_retain_each_working_predecessor(self):
        system_assets.publish(self.ctx, self.staged, self.destination)
        (self.staged / "binary").write_text("third version")
        system_assets.publish(self.ctx, self.staged, self.destination)
        self.assertEqual((self.destination / "binary").read_text(), "third version")
        backups = sorted(p.read_text() for p in self.root.glob("installed.ubuntu-bootstrap-previous-*/binary"))
        self.assertEqual(backups, ["second version", "working first version"])
        self.assertFalse((self.root / "installed.ubuntu-bootstrap-new").exists())

    def test_failed_rename_restores_the_working_tree(self):
        def failing_run(argv, *, sudo=False):
            if str(argv[0]) == "/usr/bin/mv" and str(argv[1]).endswith(".ubuntu-bootstrap-new"):
                raise BootstrapError("publication failure")
            self.run_command(argv, sudo=sudo)
        self.ctx.run = failing_run
        with self.assertRaisesRegex(BootstrapError, "publication failure"):
            system_assets.publish(self.ctx, self.staged, self.destination)
        self.assertEqual((self.destination / "binary").read_text(), "working first version")
        self.assertTrue((self.root / "installed.ubuntu-bootstrap-new").is_dir())

    def test_interrupted_staging_is_preserved_for_inspection(self):
        interrupted = self.root / "installed.ubuntu-bootstrap-new"
        interrupted.mkdir()
        with self.assertRaisesRegex(BootstrapError, "Interrupted publication"):
            system_assets.publish(self.ctx, self.staged, self.destination)
        self.assertEqual((self.destination / "binary").read_text(), "working first version")
        self.assertTrue(interrupted.is_dir())


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.allowed = patch("bootstrap_lib.shell.Path.read_text", return_value="/bin/bash\n/usr/bin/zsh\n")
        self.which = patch("bootstrap_lib.shell.shutil.which", return_value="/usr/bin/zsh")
        self.allowed.start()
        self.which.start()
        self.addCleanup(self.allowed.stop)
        self.addCleanup(self.which.stop)

    def make(self, directory, consent):
        ctx = context(Path(directory), change_shell=consent)
        if ctx.user.pw_uid == 0:
            ctx.user = SimpleNamespace(pw_uid=1000, pw_name="unit-test-user")
        return ctx

    def test_no_never_escalates(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make(directory, False)
            with patch.object(ctx, "run", side_effect=AssertionError("unexpected mutation")):
                self.assertIsNone(shell.choose(ctx))

    def test_yes_targets_original_user_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make(directory, True)
            before = SimpleNamespace(pw_uid=ctx.user.pw_uid, pw_shell="/bin/bash")
            after = SimpleNamespace(pw_uid=ctx.user.pw_uid, pw_shell="/usr/bin/zsh")
            with patch("bootstrap_lib.shell.pwd.getpwnam", side_effect=[before, after]), patch.object(ctx, "run") as run:
                self.assertEqual(shell.choose(ctx), "/usr/bin/zsh")
                run.assert_called_once_with(["/usr/bin/chsh", "-s", "/usr/bin/zsh", ctx.user.pw_name], sudo=True)

    def test_already_zsh_does_not_change(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make(directory, True)
            entry = SimpleNamespace(pw_uid=ctx.user.pw_uid, pw_shell="/usr/bin/zsh")
            with patch("bootstrap_lib.shell.pwd.getpwnam", return_value=entry), patch.object(ctx, "run") as run:
                shell.choose(ctx)
                run.assert_not_called()

    def test_root_target_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make(directory, True)
            with patch("bootstrap_lib.shell.pwd.getpwnam", return_value=SimpleNamespace(pw_uid=0, pw_shell="/bin/bash")):
                with self.assertRaisesRegex(BootstrapError, "Original"):
                    shell.choose(ctx)

    def test_never_execs_in_ci_or_automation(self):
        with patch.dict(os.environ, {"CI": "1"}), patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True):
            self.assertFalse(shell.should_enter(SimpleNamespace(non_interactive=False)))
        self.assertFalse(shell.should_enter(SimpleNamespace(non_interactive=True)))

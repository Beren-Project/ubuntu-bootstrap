"""Trust, migration and durable crash-state regressions in isolated homes."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_logic import context
from bootstrap_lib import durability, inventories, julia, migration, rust
from bootstrap_lib.config import ROOT, resolve
from bootstrap_lib.platform import BootstrapError
from bootstrap_lib.runtime import digest, safe_directory


class Environment(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.ctx = context(self.home)

    def file(self, path, data=b"fixture", mode=0o755):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)
        return path

    def cargo_metadata(self, tool, version="1.2.3"):
        cargo = self.home / ".cargo"
        cargo.mkdir(exist_ok=True)
        key = f"{tool['crate']} {version} (registry+https://github.com/rust-lang/crates.io-index)"
        (cargo / ".crates.toml").write_text("[v1]\n" + json.dumps(key) + " = " + json.dumps(tool["bins"]) + "\n")


class TrustTests(Environment):
    def test_symlinked_manager_roots_cannot_redirect_owned_updates(self):
        for name in (".cargo", ".rustup"):
            with self.subTest(root=name):
                real = self.home / (name[1:] + "-personal")
                real.mkdir()
                root = self.home / name
                root.symlink_to(real)
                self.ctx.args.update = True
                with patch.object(self.ctx, "owned", return_value=True), \
                        patch.object(self.ctx, "output", return_value="stable-x86_64-unknown-linux-gnu (default)"), \
                        patch.object(self.ctx, "run") as run:
                    with self.assertRaisesRegex(BootstrapError, "symlink"):
                        rust.rust(self.ctx)
                    run.assert_not_called()
                root.unlink()

    def test_custom_julia_depot_is_refused_before_install_or_update(self):
        self.ctx.args.update = True
        for value in (str(self.home / "personal-depot"), "relative-depot", ""):
            self.ctx.env["JULIAUP_DEPOT_PATH"] = value
            with patch.object(julia, "install_application") as install, patch.object(self.ctx, "run") as run:
                with self.assertRaisesRegex(BootstrapError, "Custom JULIAUP_DEPOT_PATH"):
                    julia.julia(self.ctx)
                install.assert_not_called()
                run.assert_not_called()
        self.ctx.env["JULIAUP_DEPOT_PATH"] = str(self.home / ".julia")
        julia.validate_depot(self.ctx)

    def test_rust_integrity_gate_and_target_mapping(self):
        data = b"\x7fELFverified-fixture"
        checksum = hashlib.sha256(data).hexdigest()
        for arch, prefix in (("amd64", "x86_64"), ("arm64", "aarch64")):
            self.ctx.arch = arch
            with patch.object(rust, "get_bytes", return_value=(checksum + " *./rustup-init\n").encode()) as metadata, \
                    patch("bootstrap_lib.runtime.get_bytes", return_value=data):
                binary = rust.rustup_init(self.ctx)
            self.assertEqual(digest(binary), checksum)
            self.assertIn(prefix + "-unknown-linux-gnu/rustup-init.sha256", metadata.call_args.args[0])
            self.assertEqual(binary.stat().st_mode & 0o777, 0o700)
        for raw in (b"", b"not a checksum", (checksum + " *wrong\n").encode(), b"\xff"):
            with patch.object(rust, "get_bytes", return_value=raw), patch.object(self.ctx, "download") as download:
                with self.assertRaises(BootstrapError):
                    rust.rustup_init(self.ctx)
                download.assert_not_called()
        with patch.object(rust, "get_bytes", return_value=("0" * 64 + " *./rustup-init\n").encode()), \
                patch("bootstrap_lib.runtime.get_bytes", return_value=data):
            with self.assertRaisesRegex(BootstrapError, "SHA-256 mismatch"):
                rust.rustup_init(self.ctx)

    def test_rust_fresh_order_rerun_and_update(self):
        init = self.file(self.ctx.cache / "verified-init")
        calls = []
        def run(argv, **kwargs):
            calls.append(list(map(str, argv)))
            if Path(argv[0]) == init:
                for name in ("rustup", "cargo", "rustc"):
                    self.file(self.home / ".cargo/bin" / name)
                self.file(self.home / ".cargo/env", b"# environment\n", 0o644)
            return 0
        with patch.object(rust, "rustup_init", return_value=init), patch.object(self.ctx, "run", side_effect=run), \
                patch.object(self.ctx, "output", return_value="stable-x86_64-unknown-linux-gnu (default)"):
            rust.rust(self.ctx)
            self.assertEqual(calls[0][1:], ["-y", "--no-modify-path", "--default-toolchain", "none"])
            self.assertEqual(calls[1][1:], ["self", "update"])
            self.assertEqual(calls[2][1:6], ["toolchain", "install", "stable", "--profile", "minimal"])
            self.assertIn("--default", calls[2])
            calls.clear()
            rust.rust(self.ctx)
            self.assertTrue(all(c[-1] == "--version" for c in calls))
            calls.clear()
            self.ctx.args.update = True
            rust.rust(self.ctx)
            self.assertEqual(calls[0][1:], ["self", "update"])
            self.assertEqual(calls[1][1:3], ["toolchain", "install"])

    def test_cargo_first_fallback_and_julia_version_probe(self):
        for profile in ("python", "julia"):
            tool = self.ctx.config[profile]["cargo"]
            calls = []
            def run(argv, **kwargs):
                calls.append(list(map(str, argv)))
                if "cargo-binstall" in str(argv[0]):
                    return 7
                for binary in tool["bins"]:
                    self.file(self.home / ".cargo/bin" / binary)
                self.cargo_metadata(tool)
                return 0
            with patch.object(rust, "binstall"), patch.object(self.ctx, "run", side_effect=run), \
                    patch.object(rust.apt, "ensure"), patch.object(rust, "get_bytes", return_value=b'{"crate":{"max_stable_version":"1.2.3"}}'), \
                    patch.object(self.ctx, "output", return_value=tool["crate"] + " 1.2.3") as output:
                receipt = rust.install_tool(self.ctx, tool)
            self.assertIn("cargo-binstall", calls[0][0])
            self.assertEqual(calls[1][1:3], ["install", "--locked"])
            self.assertNotIn("--all", calls[0])
            self.assertEqual(receipt["manager"], "cargo")
            if profile == "julia":
                self.assertEqual(output.call_count, 1)
                self.assertEqual(Path(output.call_args.args[0][0]).name, "juliaup")

    def test_independent_dependencies_and_binstall_once(self):
        self.assertEqual(resolve(self.ctx.config, ["python"]), ["apt", "rust", "python"])
        self.assertEqual(resolve(self.ctx.config, ["julia"]), ["apt", "rust", "julia"])
        binary = self.file(self.home / ".cargo/bin/cargo-binstall")
        self.ctx.record("cargo-binstall", [binary])
        with patch.object(self.ctx, "run") as run:
            rust.binstall(self.ctx)
            rust.binstall(self.ctx)
        self.assertEqual(run.call_count, 1)

    def test_no_remote_shell_installer_infrastructure(self):
        forbidden = ("sh.rustup.rs", "astral.sh/uv/install.sh", "install.julialang.org")
        for path in [*ROOT.joinpath("bootstrap_lib").glob("*.py"), ROOT / "config/bootstrap.toml", ROOT / "bootstrap"]:
            text = path.read_text()
            for url in forbidden:
                self.assertNotIn(url, text, path)
            self.assertNotRegex(text, r"(?:curl|wget)[^\n]*\|\s*(?:/bin/)?(?:ba)?sh")
            if path.suffix == ".py":
                # No runtime helper may provide a renamed download-then-shell
                # escape hatch. Completion validation uses Zsh explicitly.
                self.assertNotRegex(text, r'[\'"](?:/bin/)?(?:sh|bash|dash)[\'"]')
        self.assertFalse(hasattr(self.ctx, "installer"))
        for name in ("rust", "python", "julia"):
            self.assertNotIn("installer", self.ctx.config[name])
            text = (ROOT / "bootstrap_lib" / (name + ".py")).read_text()
            self.assertNotRegex(text, r'[\'"](?:/bin/)?(?:ba)?sh[\'"]')


class InventoryTests(Environment):
    def test_deduplicates_migrates_and_retains_ownership(self):
        inv = {"pkg": ["/b", "/a", "/a"]}
        old = {"completion:a": {"paths": {"/owned": "proof"}, "inventory": inv},
               "completion:b": {"paths": {}, "inventory": {"pkg": ["/a", "/b"]}}}
        result = inventories.normalize(old)
        snapshots = result[inventories.SECTION]["snapshots"]
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(result["completion:a"]["inventory_ref"], result["completion:b"]["inventory_ref"])
        self.assertEqual(result["completion:a"]["paths"], old["completion:a"]["paths"])
        self.assertIn("inventory", old["completion:a"])
        self.ctx.write_state("receipts.json", old)
        self.ctx.initialize_state()
        self.assertEqual(self.ctx.receipts, result)
        before = self.ctx.receipts_path.stat().st_mtime_ns
        self.ctx.initialize_state()
        self.assertEqual(self.ctx.receipts_path.stat().st_mtime_ns, before)
        self.ctx.record("completion:a", inventory={"pkg": ["/changed"]})
        self.assertEqual(len(self.ctx.receipts[inventories.SECTION]["snapshots"]), 2)
        self.assertNotEqual(self.ctx.receipts["completion:a"]["inventory_ref"], self.ctx.receipts["completion:b"]["inventory_ref"])

    def test_bad_reference_digest_and_conflict_fail_closed(self):
        valid = inventories.normalize({"completion:a": {"inventory": {"pkg": ["/a"]}}})
        for case in ("dangling", "digest", "conflict"):
            state = deepcopy(valid)
            if case == "dangling":
                state["completion:a"]["inventory_ref"] = "missing"
            elif case == "digest":
                next(iter(state[inventories.SECTION]["snapshots"].values()))["pkg"].append("/changed")
            else:
                state["completion:a"]["inventory"] = {"pkg": ["/other"]}
            with self.assertRaises(BootstrapError):
                inventories.normalize(state)

    def test_representative_all_profile_size_is_materially_lower(self):
        inventory = {"pkg": [f"/usr/share/fixture/{i}" for i in range(500)]}
        old = {"completion:" + str(i): {"paths": {}, "inventory": inventory} for i in range(40)}
        before = len(durability.json_bytes(old))
        after = len(durability.json_bytes(inventories.normalize(old)))
        self.assertLess(after, before * 0.5)


class RecoveryTests(Environment):
    def test_new_state_ancestry_is_durable_before_publication(self):
        destination = self.home / "new/state/bootstrap"
        flushed = []
        def flush(path):
            self.assertTrue(Path(path).is_dir())
            flushed.append(Path(path))
        with patch("bootstrap_lib.runtime.fsync_directory", side_effect=flush):
            safe_directory(destination)
        for directory in (destination, destination.parent, destination.parent.parent):
            self.assertIn(directory, flushed)
            self.assertIn(directory.parent, flushed)
        with patch("bootstrap_lib.runtime.fsync_directory") as flush:
            safe_directory(destination)
            flush.assert_not_called()

    def fixture(self, *, old=True):
        target = self.home / ".julia/juliaup/completions/zsh.zsh"
        target.parent.mkdir(parents=True, exist_ok=True)
        if old:
            self.file(target, b"old completion", 0o644)
            os.utime(target, ns=(1_700_000_000_000_000_000,) * 2)
            self.ctx.record("completion:juliaup", [target], provider="upstream-managed")
        else:
            self.ctx.record("rust", manager="rustup")
        prior = self.ctx.receipts_path.read_bytes()
        stage = self.file(self.ctx.cache / "stage", b"new completion", 0o644)
        proposed = {**self.ctx.receipts, **{"completion:" + name: {"paths": {str(target): digest(stage)}, "provider": "upstream-managed"}
                    for name in ("juliaup", "julia")}}
        tx = durability.Transaction(self.ctx)
        value = tx.start("completion", target=str(target))
        value["old_artifact"] = digest(target) if old else None
        value["new_artifact"] = digest(stage)
        if old:
            durability.durable_copy(target, tx.root / "old-artifact")
        durability.durable_copy(stage, tx.root / "new-artifact")
        tx.receipt_backup(value, proposed)
        value["phase"] = "PREPARED"
        tx.save(value)
        return tx, value, target, stage, proposed, prior

    def test_persisted_publication_boundaries_recover_old_pair(self):
        for phase in ("PREPARED", "ARTIFACT_PUBLISHED", "STATE_PUBLISHED"):
            for artifact_new, state_new in ((False, False), (True, False), (True, True), (False, True)):
                with self.subTest(phase=phase, artifact_new=artifact_new, state_new=state_new):
                    tx, value, target, stage, proposed, prior = self.fixture()
                    before = target.stat().st_mtime_ns
                    if artifact_new:
                        durability.atomic_bytes(target, stage.read_bytes(), mode=0o644)
                    if state_new:
                        self.ctx.write_state("receipts.json", proposed)
                    value["phase"] = phase
                    tx.save(value)
                    self.ctx.initialize_state()
                    self.assertEqual(target.read_bytes(), b"old completion")
                    self.assertEqual(target.stat().st_mtime_ns, before)
                    self.assertEqual(self.ctx.receipts_path.read_bytes(), prior)
                    self.assertFalse(tx.root.exists())

    def test_committed_pair_retained_and_cleanup_restartable(self):
        tx, value, target, stage, proposed, prior = self.fixture()
        durability.atomic_bytes(target, stage.read_bytes(), mode=0o644)
        self.ctx.write_state("receipts.json", proposed)
        value["phase"] = "COMMITTED"
        tx.save(value)
        (tx.root / "old-artifact").unlink()  # cleanup already started
        self.ctx.initialize_state()
        self.assertEqual(target.read_bytes(), b"new completion")
        self.assertEqual(self.ctx.receipts, proposed)
        self.assertFalse(tx.root.exists())
        self.ctx.initialize_state()

    def test_first_install_rollback_and_failed_recovery_preserves_material(self):
        tx, value, target, stage, proposed, prior = self.fixture(old=False)
        durability.atomic_bytes(target, stage.read_bytes(), mode=0o644)
        self.ctx.initialize_state()
        self.assertFalse(target.exists())
        self.assertEqual(self.ctx.receipts_path.read_bytes(), prior)
        tx, value, target, stage, proposed, prior = self.fixture()
        durability.atomic_bytes(target, b"personal change", mode=0o644)
        with self.assertRaisesRegex(durability.RecoveryError, "material preserved at"):
            self.ctx.initialize_state()
        self.assertEqual(target.read_bytes(), b"personal change")
        self.assertEqual((tx.root / "old-artifact").read_bytes(), b"old completion")
        self.assertTrue(tx.journal.exists())

    def test_terminal_mismatch_and_symlink_backup_refused(self):
        tx, value, target, stage, proposed, prior = self.fixture()
        value["phase"] = "COMMITTED"
        tx.save(value)
        with self.assertRaisesRegex(durability.RecoveryError, "mismatched"):
            tx.recover()
        value["phase"] = "PREPARED"
        tx.save(value)
        backup = tx.root / "old-artifact"
        backup.unlink()
        backup.symlink_to(stage)
        with self.assertRaises(durability.RecoveryError):
            tx.recover()
        self.assertTrue(tx.journal.exists())
        self.assertTrue(stage.exists())

    def test_uncaught_subprocess_exit_then_startup_recovery(self):
        tx, value, target, stage, proposed, prior = self.fixture()
        code = "import os,sys; from pathlib import Path; from bootstrap_lib.durability import atomic_bytes; atomic_bytes(Path(sys.argv[1]),b'new completion',mode=0o644); os._exit(77)"
        result = subprocess.run([sys.executable, "-B", "-c", code, str(target)], cwd=ROOT)
        self.assertEqual(result.returncode, 77)
        self.ctx.initialize_state()
        self.assertEqual(target.read_bytes(), b"old completion")
        self.assertEqual(self.ctx.receipts_path.read_bytes(), prior)

    def test_file_and_directory_fsync_order(self):
        path = self.ctx.state / "probe.json"
        events = []
        real_replace = Path.replace
        def replace(source, target):
            events.append("replace")
            return real_replace(source, target)
        with patch.object(durability.os, "fsync", side_effect=lambda fd: events.append("fsync")), patch.object(Path, "replace", replace):
            durability.atomic_bytes(path, b"{}\n")
        self.assertEqual(events, ["fsync", "replace", "fsync"])

    def test_partial_publication_stages_are_recovered_and_unknown_files_kept(self):
        tx, value, target, stage, proposed, prior = self.fixture()
        artifact_stage = target.parent / tx.stage_name(target)
        state_stage = self.ctx.state / tx.stage_name(self.ctx.receipts_path)
        self.file(artifact_stage, b"partial artifact", 0o600)
        self.file(state_stage, b"partial state", 0o600)
        self.file(tx.root / ".bootstrap-stage-interrupted-journal", b"partial journal", 0o600)
        self.ctx.initialize_state()
        self.assertEqual(target.read_bytes(), b"old completion")
        self.assertFalse(artifact_stage.exists() or state_stage.exists() or tx.root.exists())
        tx, value, target, stage, proposed, prior = self.fixture()
        self.file(tx.root / "unknown-material", b"preserve this", 0o600)
        with self.assertRaisesRegex(durability.RecoveryError, "Unknown recovery material"):
            self.ctx.initialize_state()
        self.assertTrue((tx.root / "unknown-material").exists())

    def test_receipt_semantics_must_match_committed_artifact(self):
        tx, value, target, stage, proposed, prior = self.fixture()
        durability.atomic_bytes(target, stage.read_bytes(), mode=0o644)
        proposed["completion:julia"]["paths"] = {str(target): "0" * 64}
        self.ctx.write_state("receipts.json", proposed)
        value["phase"] = "COMMITTED"
        value["new_state"] = digest(self.ctx.receipts_path)
        tx.save(value)
        with self.assertRaisesRegex(durability.RecoveryError, "pair disagrees"):
            self.ctx.initialize_state()
        self.assertTrue(tx.journal.exists())


class MigrationTests(Environment):
    def test_failed_retirement_recovery_is_fatal_and_names_material(self):
        paths = self.legacy("python")
        flush = migration.fsync_directory
        def fail_retirement(directory):
            if directory == paths[0].parent:
                raise OSError("retirement flush failed")
            flush(directory)
        with patch.object(rust, "binstall"), patch.object(rust, "install_tool", side_effect=self.replacement), \
                patch.object(migration, "validate_runtime"), \
                patch.object(migration, "fsync_directory", side_effect=fail_retirement):
            with self.assertRaisesRegex(durability.RecoveryError, str(self.ctx.state / "transaction")):
                migration.install_application(self.ctx, "python")
        tx = durability.Transaction(self.ctx)
        self.assertTrue(tx.journal.exists())
        self.assertTrue((tx.root / "old-state").exists())
        self.assertTrue((tx.root / "new-state").exists())
        self.ctx.initialize_state()
        self.assertFalse(tx.root.exists())
        self.assertFalse(any(p.exists() for p in paths))

    def test_replacement_persistence_precedes_legacy_retirement(self):
        old = self.legacy("python")
        with patch.object(rust, "binstall"), patch.object(rust, "install_tool", side_effect=self.replacement), \
                patch.object(migration, "validate_runtime"), \
                patch.object(migration, "flush_replacement", side_effect=OSError("flush failed")):
            with self.assertRaisesRegex(durability.RecoveryError, "before ownership evidence"):
                migration.install_application(self.ctx, "python")
        self.assertTrue(all(p.exists() for p in old))
        self.assertEqual(self.ctx.receipts["uv"]["manager"], "uv")
        self.assertEqual(durability.Transaction(self.ctx).load()["phase"], "INSTALLING")

    def legacy(self, profile):
        owner, manager, paths = migration.legacy_spec(self.ctx, profile)
        for path in paths:
            self.file(path, ("legacy " + path.name).encode())
        if profile == "julia":
            paths[1].unlink()
            launcher = self.file(paths[1].with_name("julialauncher"), b"legacy launcher")
            paths[1].symlink_to(launcher)
        self.ctx.record(owner, paths, manager=manager, channel="release")
        return paths

    def replacement(self, ctx, tool, **kwargs):
        paths = [self.file(self.home / ".cargo/bin" / n, ("cargo " + n).encode()) for n in tool["bins"]]
        self.cargo_metadata(tool)
        return {"paths": {str(p): digest(p) for p in paths}, "manager": "cargo", "crate": tool["crate"], "version": "1.2.3"}

    def test_both_legacy_migrations_preserve_data_and_rerun(self):
        for profile in ("python", "julia"):
            paths = self.legacy(profile)
            personal = self.file(paths[0].parent / "personal", b"unrelated")
            data = self.file(self.home / "runtime-data", b"runtime preserved", 0o644)
            with patch.object(rust, "binstall"), patch.object(rust, "install_tool", side_effect=self.replacement), \
                    patch.object(migration, "validate_runtime"):
                replacement = migration.install_application(self.ctx, profile)
            self.assertFalse(any(p.exists() or p.is_symlink() for p in paths))
            self.assertEqual(personal.read_bytes(), b"unrelated")
            self.assertEqual(data.read_bytes(), b"runtime preserved")
            self.assertEqual(self.ctx.receipts[replacement["crate"]], replacement)
            self.assertFalse((self.ctx.state / "transaction").exists())
            with patch.object(rust, "install_tool", return_value=replacement) as install:
                migration.install_application(self.ctx, profile)
            install.assert_called_once()

    def test_changed_unmanaged_and_symlink_launchers_are_never_removed(self):
        paths = self.legacy("python")
        paths[0].write_bytes(b"personal modification")
        self.ctx.args.adopt = ["uv"]
        with patch.object(rust, "install_tool") as install:
            with self.assertRaisesRegex(BootstrapError, "changed outside"):
                migration.install_application(self.ctx, "python")
            install.assert_not_called()
        self.assertEqual(paths[0].read_bytes(), b"personal modification")
        self.ctx.receipts.pop("uv")
        with self.assertRaisesRegex(BootstrapError, "Unproven legacy"):
            migration.install_application(self.ctx, "python")
        paths[0].unlink()
        paths[0].symlink_to(paths[1])
        with self.assertRaisesRegex(BootstrapError, "symlink"):
            migration.install_application(self.ctx, "python")

    def test_install_failure_preserves_legacy_receipt_and_launchers(self):
        paths = self.legacy("python")
        prior = self.ctx.receipts_path.read_bytes()
        with patch.object(rust, "binstall"), patch.object(rust, "install_tool", side_effect=BootstrapError("installer failed")):
            with self.assertRaisesRegex(BootstrapError, "installer failed"):
                migration.install_application(self.ctx, "python")
        self.assertTrue(all(p.exists() for p in paths))
        self.assertEqual(self.ctx.receipts_path.read_bytes(), prior)
        self.assertFalse((self.ctx.state / "transaction").exists())

    def test_ambiguous_install_and_partial_retirement_fail_closed_or_resume(self):
        paths = self.legacy("python")
        def partial(ctx, tool, **kwargs):
            self.file(self.home / ".cargo/bin/uv", b"unproven partial output")
            raise BootstrapError("interrupted installer")
        with patch.object(rust, "binstall"), patch.object(rust, "install_tool", side_effect=partial):
            with self.assertRaisesRegex(durability.RecoveryError, "before ownership evidence"):
                migration.install_application(self.ctx, "python")
        self.assertTrue(all(p.exists() for p in paths))
        tx = durability.Transaction(self.ctx)
        with self.assertRaisesRegex(durability.RecoveryError, "no automatic adoption"):
            self.ctx.initialize_state()
        self.assertTrue(tx.journal.exists())
        # Only this test's known fixture material is reset; ambiguous production
        # outputs are never deleted by recovery.
        (self.home / ".cargo/bin/uv").unlink()
        tx.cleanup()
        with patch.object(rust, "binstall"), patch.object(rust, "install_tool", side_effect=self.replacement), \
                patch.object(migration, "validate_runtime"), patch.object(migration, "recover", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                migration.install_application(self.ctx, "python")
        paths[0].unlink()  # power loss after the first exact legacy retirement
        self.ctx.initialize_state()
        self.assertFalse(any(p.exists() for p in paths))
        self.assertEqual(self.ctx.receipts["uv"]["manager"], "cargo")

    def test_persisted_retirement_phases_roll_forward(self):
        for phase in ("REPLACEMENT_VERIFIED", "LEGACY_RETIRED", "COMMITTED"):
            paths = self.legacy("python")
            # Remove only this isolated test's previous replacement fixture.
            for n in ("uv", "uvx"):
                (self.home / ".cargo/bin" / n).unlink(missing_ok=True)
            save = durability.Transaction.save
            def crash(tx, value):
                save(tx, value)
                if value["phase"] == phase:
                    raise KeyboardInterrupt("simulated death")
            with patch.object(rust, "binstall"), patch.object(rust, "install_tool", side_effect=self.replacement), \
                    patch.object(migration, "validate_runtime"), patch.object(durability.Transaction, "save", crash), \
                    patch.object(migration, "recover", side_effect=KeyboardInterrupt("no cleanup")):
                with self.assertRaises(KeyboardInterrupt):
                    migration.install_application(self.ctx, "python")
            tx = durability.Transaction(self.ctx)
            value = tx.load()
            # The no-cleanup crash hook leaves REPLACEMENT_VERIFIED; construct
            # subsequent persisted states from the same verified material.
            if phase != "REPLACEMENT_VERIFIED":
                for p in paths:
                    p.unlink()
                value["phase"] = phase
                if phase == "COMMITTED":
                    self.ctx.write_state("receipts.json", json.loads((tx.root / "new-state").read_text()))
                tx.save(value)
            self.ctx.initialize_state()
            self.assertTrue(all(not p.exists() for p in paths))
            self.assertEqual(self.ctx.receipts["uv"]["manager"], "cargo")
            self.assertFalse(tx.root.exists())


if __name__ == "__main__":
    unittest.main()

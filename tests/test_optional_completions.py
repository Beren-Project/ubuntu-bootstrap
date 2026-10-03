"""Optional provider contracts exercised with real Zsh and local applications."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bootstrap_lib import completions, optional_completions as providers
from bootstrap_lib.config import OPTIONAL, validate_optional_completions
from bootstrap_lib.platform import BootstrapError
from bootstrap_lib.runtime import digest
from test_logic import context


class ProviderEnvironment(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.ctx = context(self.home)
        self.ctx.env["HOME"] = str(self.home)
        self.ctx.env.pop("ZDOTDIR", None)
        self.directory = self.home / "providers"
        self.directory.mkdir()
        (self.home / ".zshrc").write_text(f'fpath=("{self.directory}" $fpath)\nautoload -Uz compinit\ncompinit -i -d /dev/null -D\n')
        quiet = redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)


class OptionalProviderTests(ProviderEnvironment):
    def test_manifest_classifies_every_optional_profile_and_build_command(self):
        specs = self.ctx.config["optional_zsh_completions"]
        self.assertEqual({spec["profile"] for spec in specs}, set(OPTIONAL))
        mapping = {command: spec for spec in specs for command in spec["commands"]}
        for command in ("vim", "nvim"):
            self.assertEqual(mapping[command]["function"], "_vim")
        for command in ("gcc", "g++", "cc", "c++", "make", "pkg-config", "ninja"):
            self.assertEqual(mapping[command]["provider"], "system")
        for command in ("cmake", "ctest", "cpack", "emacs", "ngspice", "omc"):
            self.assertEqual(mapping[command]["provider"], "unavailable")
        self.assertEqual(mapping["juliaup"]["provider"], "upstream-managed")

    def test_invalid_classification_and_duplicate_command_are_rejected(self):
        config = deepcopy(self.ctx.config)
        config["optional_zsh_completions"][0]["provider"] = "implicit"
        with self.assertRaisesRegex(ValueError, "Unknown optional"):
            validate_optional_completions(config)
        config = deepcopy(self.ctx.config)
        config["optional_zsh_completions"].append(config["optional_zsh_completions"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_optional_completions(config)

    def test_optional_command_cannot_replace_a_base_completion_receipt(self):
        config = deepcopy(self.ctx.config)
        config["optional_zsh_completions"][1]["commands"] = ["uv"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_optional_completions(config)

    def system_fixture(self, commands, function="_fixture"):
        path = self.directory / function
        path.write_text('#compdef ' + ' '.join(commands) + '\n' + function + '() { _files; }\n')
        return path

    def provision_system(self, spec, path):
        # A temp user directory stands in for package-owned /usr solely in this
        # registration test. Production root trust is tested independently.
        with patch.object(providers, "inventory", return_value={"fixture-package": [str(path)]}), \
                patch.object(providers, "trusted_system", return_value=True):
            providers.provision_system(self.ctx, spec)

    def test_shared_vim_provider_registers_both_editors_without_user_duplicates(self):
        path = self.system_fixture(["vim", "nvim"], "_vim")
        for command in ("vim", "nvim"):
            spec = {"commands": [command], "provider": "system", "function": "_vim"}
            self.provision_system(spec, path)
            self.provision_system(spec, path)
            self.assertEqual(self.ctx.receipts["completion:" + command]["function"], "_vim")
        self.assertFalse((self.home / ".zfunc").exists())

    def test_gcc_aliases_use_shared_function(self):
        commands = ["gcc", "g++", "cc", "c++"]
        path = self.system_fixture(commands, "_gcc")
        self.provision_system({"commands": commands, "provider": "system", "function": "_gcc"}, path)
        self.assertTrue(all(self.ctx.receipts["completion:" + cmd]["function"] == "_gcc" for cmd in commands))

    def test_already_loaded_valid_system_function_is_accepted(self):
        path = self.system_fixture(["vim"], "_vim")
        with (self.home / ".zshrc").open("a") as config:
            config.write("autoload +X _vim\n")
        self.provision_system({"commands": ["vim"], "provider": "system", "function": "_vim"}, path)
        self.assertEqual(self.ctx.receipts["completion:vim"]["provider"], "system")

    def test_personal_function_cannot_impersonate_system_autoload(self):
        path = self.system_fixture(["vim"], "_vim")
        with (self.home / ".zshrc").open("a") as config:
            config.write("_vim() { :; }\n")
        with self.assertRaisesRegex(BootstrapError, "personal/shadowed"):
            self.provision_system({"commands": ["vim"], "provider": "system", "function": "_vim"}, path)
        self.assertNotIn("completion:vim", self.ctx.receipts)

    def test_probe_does_not_repair_missing_real_shell_registration(self):
        path = self.system_fixture(["vim"], "_vim")
        with (self.home / ".zshrc").open("a") as config:
            config.write("unset _comps\n")
        with self.assertRaisesRegex(BootstrapError, "did not initialize compinit"):
            self.provision_system({"commands": ["vim"], "provider": "system", "function": "_vim"}, path)
        self.assertNotIn("completion:vim", self.ctx.receipts)

    def test_provider_drift_between_discovery_and_load_is_rejected(self):
        path = self.system_fixture(["vim"], "_vim")
        other = self.home / "personal-providers"
        other.mkdir()
        (other / "_vim").write_bytes(path.read_bytes())
        (self.home / ".zshrc").write_text(f'''integer starts=0
[[ -r "{self.home}/starts" ]] && starts=$(<"{self.home}/starts")
(( starts++ ))
print -r -- $starts > "{self.home}/starts"
if (( starts == 1 )); then
 fpath=("{self.directory}" $fpath)
else
 fpath=("{other}" $fpath)
fi
autoload -Uz compinit
compinit -i -d /dev/null -D
''')
        with self.assertRaisesRegex(BootstrapError, "provider changed before load"):
            self.provision_system({"commands": ["vim"], "provider": "system", "function": "_vim"}, path)
        self.assertNotIn("completion:vim", self.ctx.receipts)

    def test_unavailable_is_reported_without_artifacts_or_failure(self):
        spec = {"commands": ["fixture-missing"], "provider": "unavailable", "reason": "no supported provider"}
        with patch.object(providers, "inventory", return_value={"fixture-package": []}):
            providers.provision_system(self.ctx, spec)
        self.assertEqual(self.ctx.receipts["completion:fixture-missing"]["provider"], "unavailable")
        self.assertEqual(self.ctx.results[-1]["state"], "SKIP")
        self.assertFalse((self.home / ".zfunc").exists())

    def test_later_package_provider_is_discovered_in_unavailable_entry(self):
        path = self.system_fixture(["fixture"])
        self.provision_system({"commands": ["fixture"], "provider": "unavailable", "reason": "none qualified"}, path)
        self.assertEqual(self.ctx.receipts["completion:fixture"]["provider"], "system")

    def test_generic_file_completion_is_not_an_application_provider(self):
        with (self.home / ".zshrc").open("a") as config:
            config.write("compdef _files fixture-missing\n")
        spec = {"commands": ["fixture-missing"], "provider": "unavailable", "reason": "no application provider"}
        with patch.object(providers, "inventory", return_value={"fixture": []}):
            providers.provision_system(self.ctx, spec)
        self.assertEqual(self.ctx.receipts["completion:fixture-missing"]["provider"], "unavailable")

    def test_unselected_profiles_never_probe_or_generate(self):
        with patch.object(providers, "provision_system") as system, patch.object(providers, "provision_upstream") as native:
            completions.provision(self.ctx, "dotfiles")
        system.assert_not_called()
        native.assert_not_called()
        self.assertFalse((self.home / ".zfunc").exists())

    def test_selected_later_profile_and_update_only_validate_its_entry(self):
        with patch.object(providers, "provision_system") as system, patch.object(providers, "provision_upstream") as native:
            providers.provision(self.ctx, "vim")
            self.assertEqual(system.call_args.args[1]["commands"], ["vim"])
            self.ctx.args.update = True
            providers.provision(self.ctx, "vim")
        self.assertEqual(system.call_count, 2)
        native.assert_not_called()

    def test_user_shadow_and_missing_required_registration_fail_without_overwrite(self):
        path = self.system_fixture(["vim", "nvim"], "_vim")
        original = path.read_bytes()
        spec = {"commands": ["vim"], "provider": "system", "function": "_vim"}
        with patch.object(providers, "inventory", return_value={"fixture": [str(path)]}):
            with self.assertRaisesRegex(BootstrapError, "trusted package-owned"):
                providers.provision_system(self.ctx, spec)
        self.assertFalse(providers.trusted_system(path))
        self.assertEqual(path.read_bytes(), original)
        spec["function"] = "_different"
        with self.assertRaisesRegex(BootstrapError, "Expected _different"):
            self.provision_system(spec, path)

    def test_root_cannot_prepare_optional_profiles(self):
        with patch("os.geteuid", return_value=0), patch.object(providers, "inventory", side_effect=AssertionError):
            with self.assertRaisesRegex(BootstrapError, "never root"):
                providers.provision(self.ctx, "vim")


class NativeJuliaCompletionTests(ProviderEnvironment):
    def setUp(self):
        super().setUp()
        self.spec = {"profile": "julia", "commands": ["juliaup", "julia"], "functions": ["_juliaup", "_julia_channel"],
                     "provider": "upstream-managed", "owner": "juliaup", "executable": ".cargo/bin/juliaup",
                     "destination": ".native/completions/zsh.zsh", "arguments": ["completions", "zsh"]}
        self.ctx.config["optional_zsh_completions"][0] = self.spec
        self.binary = self.home / self.spec["executable"]
        self.destination = self.home / self.spec["destination"]
        self.binary.parent.mkdir(parents=True)
        (self.home / ".zshrc").write_text(f'autoload -Uz compinit\ncompinit -i -d /dev/null -D\n[[ -r "{self.destination}" ]] && source "{self.destination}"\n')
        self.application()

    def application(self, version=1, failure=False, invalid=False):
        # Native format intentionally starts with a compinit guard, unlike the
        # strict generic #compdef autoload header. Payload exists only in tests.
        output = f'''if ! (( $+functions[compdef] )); then
autoload -Uz compinit && compinit -i -d /dev/null -D
fi
# fixture version {version}
_juliaup() {{ _arguments '--help'; }}
compdef _juliaup juliaup
_julia_channel() {{
local -a channels
channels=(${{(f)"$(juliaup _list-channels)"}})
IPREFIX="${{IPREFIX}}+"
PREFIX="${{PREFIX#+}}"
compadd -a channels
}}
compdef _julia_channel julia
'''
        if invalid:
            output = "# comments only\n"
        self.binary.write_text(f'''#!/usr/bin/python3
import os, pathlib, sys
if '--version' in sys.argv:
    print('juliaup fixture {version}')
elif '_list-channels' in sys.argv:
    print('release\\nnightly')
else:
    with pathlib.Path(__file__).with_name('calls').open('a') as log:
        log.write(str(os.geteuid()) + '\\n')
    print({output!r})
    sys.exit({7 if failure else 0})
''')
        self.binary.chmod(0o755)
        self.ctx.record("juliaup", [self.binary], manager="cargo")

    def provision(self):
        providers.provision_upstream(self.ctx, self.spec)

    def test_native_source_registered_and_channel_behavior_validated(self):
        self.provision()
        self.assertEqual(self.destination.stat().st_uid, os.getuid())
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o644)
        self.assertFalse((self.home / ".zfunc/_juliaup").exists())
        self.assertEqual(self.ctx.receipts["completion:julia"]["function"], "_julia_channel")
        self.assertEqual((self.binary.parent / "calls").read_text().strip(), str(os.getuid()))

    def test_native_rerun_and_current_update_preserve_file(self):
        self.provision()
        before = self.destination.stat().st_mtime_ns
        self.provision()
        self.ctx.args.update = True
        self.provision()
        self.assertEqual(self.destination.stat().st_mtime_ns, before)
        self.assertEqual(len((self.binary.parent / "calls").read_text().splitlines()), 1)
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_native_changed_application_regenerates(self):
        self.provision()
        before = digest(self.destination)
        self.application(version=2)
        self.ctx.args.update = True
        self.provision()
        self.assertNotEqual(digest(self.destination), before)
        self.assertEqual(self.ctx.receipts["completion:juliaup"]["source"]["version"], "juliaup fixture 2")

    def test_native_generation_failure_and_invalid_output_preserve_working_script(self):
        self.provision()
        before = self.destination.read_bytes(), self.destination.stat().st_mtime_ns
        receipt = deepcopy(self.ctx.receipts["completion:juliaup"])
        for failure, invalid in ((True, False), (False, True)):
            self.application(version=2, failure=failure, invalid=invalid)
            with self.assertRaises(BootstrapError):
                self.provision()
            self.assertEqual((self.destination.read_bytes(), self.destination.stat().st_mtime_ns), before)
            self.assertEqual(self.ctx.receipts["completion:juliaup"], receipt)
            self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_native_personal_script_is_preserved_even_if_valid(self):
        self.provision()
        self.destination.write_text(self.destination.read_text() + "# personal alteration\n")
        before = self.destination.read_bytes()
        with self.assertRaisesRegex(BootstrapError, "Externally changed"):
            self.provision()
        self.assertEqual(self.destination.read_bytes(), before)
        self.ctx.receipts.pop("completion:juliaup")
        with self.assertRaisesRegex(BootstrapError, "Unmanaged Juliaup completion preserved"):
            self.provision()

    def test_restored_shell_validation_failure_rolls_back_old_file_and_receipts(self):
        self.provision()
        before = self.destination.read_bytes(), self.destination.stat().st_mtime_ns
        receipt = deepcopy(self.ctx.receipts["completion:juliaup"])
        self.application(version=2)
        with patch.object(providers, "verify_native_registration", side_effect=BootstrapError("registration failure")):
            with self.assertRaisesRegex(BootstrapError, "registration failure"):
                self.provision()
        self.assertEqual((self.destination.read_bytes(), self.destination.stat().st_mtime_ns), before)
        self.assertEqual(self.ctx.receipts["completion:juliaup"], receipt)
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_native_root_and_symlink_refused_before_generation(self):
        with patch("os.geteuid", return_value=0):
            with self.assertRaisesRegex(BootstrapError, "never root"):
                self.provision()
        self.assertFalse(self.destination.parent.exists())
        self.destination.parent.mkdir(parents=True)
        target = self.home / "personal"
        target.write_text("personal")
        self.destination.symlink_to(target)
        with self.assertRaisesRegex(BootstrapError, "regular Juliaup completion"):
            self.provision()
        self.assertEqual(target.read_text(), "personal")

    def test_custom_depot_is_refused_before_preparation(self):
        self.ctx.env["JULIAUP_DEPOT_PATH"] = str(self.home / "custom-depot")
        with self.assertRaisesRegex(BootstrapError, "Custom JULIAUP_DEPOT_PATH"):
            self.provision()
        self.assertFalse(self.destination.parent.exists())
        self.assertFalse((self.binary.parent / "calls").exists())

    def test_native_writable_script_is_preserved_and_refused_even_on_rerun(self):
        self.provision()
        self.destination.chmod(0o666)
        before = self.destination.read_bytes(), self.destination.stat().st_mtime_ns
        with self.assertRaisesRegex(BootstrapError, "Insecure Juliaup completion file"):
            self.provision()
        self.assertEqual((self.destination.read_bytes(), self.destination.stat().st_mtime_ns), before)
        self.assertEqual(len((self.binary.parent / "calls").read_text().splitlines()), 1)

    def test_new_native_parents_are_secure_with_permissive_umask(self):
        prior = os.umask(0o002)
        try:
            self.provision()
        finally:
            os.umask(prior)
        self.assertEqual(self.destination.parent.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.destination.parent.parent.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o644)

    def test_existing_insecure_parent_is_refused_before_creating_children(self):
        self.destination.parent.parent.mkdir(mode=0o777)
        self.destination.parent.parent.chmod(0o777)
        with self.assertRaisesRegex(BootstrapError, "Insecure Juliaup completion parent"):
            self.provision()
        self.assertFalse(self.destination.parent.exists())

    def test_reviewed_julia_adoption_reconciles_only_its_native_script(self):
        self.provision()
        self.destination.write_text(self.destination.read_text() + "# personal modification\n")
        self.ctx.receipts.pop("completion:juliaup")
        unrelated = self.home / ".zfunc/_personal"
        unrelated.parent.mkdir()
        unrelated.write_text("personal unrelated completion")
        self.ctx.args.adopt = ["julia"]
        self.provision()
        self.assertNotIn("personal modification", self.destination.read_text())
        self.assertEqual(unrelated.read_text(), "personal unrelated completion")
        self.assertEqual(self.ctx.receipts["completion:juliaup"]["paths"], self.ctx.receipts["completion:julia"]["paths"])

    def test_restored_native_function_shadow_is_detected(self):
        self.provision()
        before = self.destination.read_bytes()
        with (self.home / ".zshrc").open("a") as config:
            config.write("_julia_channel() { :; }\n")
        with self.assertRaisesRegex(BootstrapError, "personal/shadowed _julia_channel"):
            self.provision()
        self.assertEqual(self.destination.read_bytes(), before)

    def test_receipt_failure_rolls_back_native_script_and_both_receipts(self):
        self.provision()
        before = self.destination.read_bytes(), self.destination.stat().st_mtime_ns
        self.application(version=2)
        receipts = deepcopy(self.ctx.receipts)
        disk_receipts = self.ctx.receipts_path.read_bytes()
        with patch.object(self.ctx, "write_state", side_effect=OSError("receipt publication failure")):
            with self.assertRaisesRegex(OSError, "receipt publication failure"):
                self.provision()
        self.assertEqual((self.destination.read_bytes(), self.destination.stat().st_mtime_ns), before)
        self.assertEqual(self.ctx.receipts, receipts)
        self.assertEqual(self.ctx.receipts_path.read_bytes(), disk_receipts)
        self.assertFalse(list(self.ctx.state.glob(".bootstrap-*")))
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_interrupt_after_receipt_rename_restores_previous_state(self):
        self.provision()
        before = self.destination.read_bytes(), self.destination.stat().st_mtime_ns
        self.application(version=2)
        receipts = deepcopy(self.ctx.receipts)
        disk_receipts = self.ctx.receipts_path.read_bytes()
        write_state = self.ctx.write_state
        def interrupted(name, value):
            write_state(name, value)
            raise KeyboardInterrupt("interrupt after receipt rename")
        with patch.object(self.ctx, "write_state", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.provision()
        self.assertEqual((self.destination.read_bytes(), self.destination.stat().st_mtime_ns), before)
        self.assertEqual(self.ctx.receipts, receipts)
        self.assertEqual(self.ctx.receipts_path.read_bytes(), disk_receipts)
        self.assertFalse(list(self.ctx.state.glob(".bootstrap-*")))
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_interrupt_after_native_rename_preserves_old_script(self):
        self.provision()
        before = self.destination.read_bytes(), self.destination.stat().st_mtime_ns
        self.application(version=2)
        receipts = self.ctx.receipts_path.read_bytes()
        replace = Path.replace
        fired = False
        def interrupted(path, target):
            nonlocal fired
            result = replace(path, target)
            if path.name.startswith(".bootstrap-") and not path.name.startswith(".bootstrap-previous-") and target == self.destination and not fired:
                fired = True
                raise KeyboardInterrupt("interrupt immediately after rename")
            return result
        with patch.object(Path, "replace", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.provision()
        self.assertEqual((self.destination.read_bytes(), self.destination.stat().st_mtime_ns), before)
        self.assertEqual(self.ctx.receipts_path.read_bytes(), receipts)
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_interrupt_after_completed_receipts_keeps_file_and_receipts_consistent(self):
        from bootstrap_lib.durability import Transaction
        self.provision()
        self.application(version=2)
        cleanup = Transaction.cleanup
        fired = False
        def interrupted(tx):
            nonlocal fired
            if tx.load()["phase"] == "COMMITTED" and not fired:
                fired = True
                raise KeyboardInterrupt("after durable commit")
            cleanup(tx)
        with patch.object(Transaction, "cleanup", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.provision()
        receipt = self.ctx.receipts["completion:juliaup"]
        self.assertEqual(receipt["paths"][str(self.destination)], digest(self.destination))
        self.assertEqual(receipt["source"]["version"], "juliaup fixture 2")
        self.assertEqual(json.loads(self.ctx.receipts_path.read_text()), self.ctx.receipts)
        self.assertFalse((self.ctx.state / "transaction").exists())

    def test_receipt_backup_cleanup_failure_keeps_committed_pair_consistent(self):
        self.provision()
        self.application(version=2)
        unlink = Path.unlink
        def fail_cleanup(path, *args, **kwargs):
            if path.name == "old-state":
                raise OSError("recovery-copy cleanup unavailable")
            return unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_cleanup):
            with self.assertRaisesRegex(BootstrapError, "material preserved at"):
                self.provision()
        receipt = self.ctx.receipts["completion:juliaup"]
        self.assertEqual(receipt["paths"][str(self.destination)], digest(self.destination))
        self.assertEqual(json.loads(self.ctx.receipts_path.read_text()), self.ctx.receipts)
        backup = self.ctx.state / "transaction/old-state"
        self.assertEqual(json.loads(backup.read_text())["completion:juliaup"]["source"]["version"], "juliaup fixture 1")
        self.ctx.initialize_state()
        self.assertFalse(backup.parent.exists())

    def test_failed_rollback_keeps_recovery_backup(self):
        from bootstrap_lib.durability import Transaction
        self.provision()
        before = self.destination.read_bytes()
        self.application(version=2)
        restore = Transaction.restore
        def failed_restore(tx, target, backup, expected):
            if backup.name == "old-artifact":
                raise OSError("restore unavailable")
            return restore(tx, target, backup, expected)
        with patch.object(Transaction, "restore", failed_restore), patch.object(providers, "verify_native_registration", side_effect=BootstrapError("registration failed")):
            with self.assertRaisesRegex(BootstrapError, "material preserved at"):
                self.provision()
        backup = self.ctx.state / "transaction/old-artifact"
        self.assertEqual(backup.read_bytes(), before)
        self.ctx.initialize_state()
        self.assertEqual(self.destination.read_bytes(), before)
        self.assertFalse(backup.parent.exists())

    def test_failed_state_publication_cleans_staging_file(self):
        state = self.ctx.state / "probe.json"
        state.write_text("prior state\n")
        before = set(self.ctx.state.iterdir())
        replace = Path.replace
        def fail(path, target):
            if target == state:
                raise OSError("state publication failure")
            return replace(path, target)
        with patch.object(Path, "replace", fail):
            with self.assertRaisesRegex(OSError, "state publication failure"):
                self.ctx.write_state("probe.json", {"new": "state"})
        self.assertEqual(state.read_text(), "prior state\n")
        self.assertEqual(set(self.ctx.state.iterdir()), before)

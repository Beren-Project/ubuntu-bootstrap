"""Small Linux publication journal. No third-party installer atomicity claim.

Completion PREPARED/ARTIFACT_PUBLISHED/STATE_PUBLISHED roll back; COMMITTED
keeps the new pair. ROLLED_BACK keeps the old pair. Both terminal states finish
restartable cleanup. Verified Cargo migrations roll forward after replacement
evidence is durable. INSTALLING with ambiguous output requires operator review.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

from .platform import BootstrapError


class RecoveryError(BootstrapError):
    """State-dependent work must stop; recovery material must be preserved."""


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def regular(path, *, missing=False):
    path = Path(path)
    if not path.exists() and not path.is_symlink() and missing:
        return False
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise RecoveryError(f"Unsafe recovery/publication file: {path}")
    return True


def parents(path):
    for parent in Path(path).absolute().parents:
        if parent.is_symlink() or not parent.is_dir():
            raise RecoveryError(f"Unsafe publication parent: {parent}")
        # /tmp may be sticky and root-owned; never manage artifacts through a
        # user-writable non-sticky parent belonging to a different principal.
        mode = parent.stat().st_mode
        if mode & 0o022 and not mode & stat.S_ISVTX:
            raise RecoveryError(f"Writable publication parent: {parent}")


def atomic_bytes(destination, data, *, mode=0o600, metadata=None, stage_name=None):
    destination = Path(destination)
    parents(destination)
    regular(destination, missing=True)
    staged = None
    try:
        stream = (open(destination.parent / stage_name, "xb") if stage_name else
                  tempfile.NamedTemporaryFile(prefix=".bootstrap-stage-", dir=destination.parent, delete=False))
        with stream:
            staged = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            if metadata:
                os.utime(staged, ns=metadata)
            os.fsync(stream.fileno())
        staged.replace(destination)
        fsync_directory(destination.parent)
    finally:
        if staged and staged.exists():
            staged.unlink()


def durable_copy(source, destination):
    regular(source)
    regular(destination, missing=True)
    shutil.copy2(source, destination)
    regular(destination)
    with Path(destination).open("rb") as stream:
        os.fsync(stream.fileno())
    fsync_directory(Path(destination).parent)


class Transaction:
    def __init__(self, ctx):
        self.ctx = ctx
        self.root = ctx.state / "transaction"
        self.journal = self.root / "journal.json"

    def save(self, value):
        atomic_bytes(self.journal, json_bytes(value))

    def start(self, kind, **details):
        if self.root.exists() or self.root.is_symlink():
            raise RecoveryError(f"Pending transaction preserved at {self.root}")
        self.root.mkdir(mode=0o700)
        fsync_directory(self.ctx.state)
        value = {"schema": 1, "kind": kind, "phase": "STAGING", **details}
        self.save(value)
        return value

    def load(self):
        if self.root.is_symlink() or not self.root.is_dir() or self.root.stat().st_uid != os.getuid() or self.root.stat().st_mode & 0o077:
            raise RecoveryError(f"Unsafe transaction directory: {self.root}")
        regular(self.journal)
        value = json.loads(self.journal.read_text())
        if value.get("schema") != 1 or value.get("kind") not in ("completion", "migration"):
            raise RecoveryError(f"Malformed transaction journal: {self.journal}")
        return value

    def cleanup(self):
        # Only fixed, explicitly owned recovery names. Unknown files are kept.
        allowed = {"journal.json", "old-artifact", "new-artifact", "old-state", "new-state"}
        files = list(self.root.iterdir())
        if any(p.name not in allowed and not p.name.startswith(".bootstrap-stage-") for p in files):
            raise RecoveryError(f"Unknown recovery material preserved at {self.root}")
        for path in files:
            regular(path)
        for path in files:
            if path != self.journal:
                path.unlink()
        fsync_directory(self.root)
        self.journal.unlink()
        fsync_directory(self.root)
        self.root.rmdir()
        fsync_directory(self.ctx.state)

    def receipt_backup(self, value, proposed):
        path = self.ctx.receipts_path
        value["old_state"] = sha(path) if regular(path, missing=True) else None
        if value["old_state"]:
            durable_copy(path, self.root / "old-state")
        atomic_bytes(self.root / "new-state", json_bytes(proposed))
        value["new_state"] = sha(self.root / "new-state")

    def check_state(self, value):
        current = sha(self.ctx.receipts_path) if regular(self.ctx.receipts_path, missing=True) else None
        if current not in (value["old_state"], value["new_state"]):
            raise RecoveryError(f"Receipt state changed; recovery material at {self.root}")

    def restore(self, destination, backup, expected):
        if expected is None:
            destination.unlink(missing_ok=True)
            fsync_directory(destination.parent)
        else:
            regular(backup)
            if sha(backup) != expected:
                raise RecoveryError(f"Invalid recovery copy preserved: {backup}")
            info = backup.stat()
            atomic_bytes(destination, backup.read_bytes(), mode=stat.S_IMODE(info.st_mode),
                         metadata=(info.st_atime_ns, info.st_mtime_ns), stage_name=self.stage_name(destination))

    def stage_name(self, destination):
        return ".bootstrap-" + Path(destination).name + "-transaction"

    def clear_stage(self, destination):
        stage = Path(destination).parent / self.stage_name(destination)
        if regular(stage, missing=True):
            stage.unlink()
            fsync_directory(stage.parent)

    def completion_target(self, value):
        target = Path(value["target"])
        allowed = {self.ctx.home / s["destination"] for s in self.ctx.config["optional_zsh_completions"]
                   if s["provider"] == "upstream-managed"}
        allowed.update(self.ctx.home / ".zfunc" / ("_" + s["command"]) for s in self.ctx.config["zsh_completions"])
        if target not in allowed:
            raise RecoveryError(f"Unrecognized completion target in {self.journal}")
        parents(target)
        return target

    def validate_new_pair(self, target, receipts, checksum):
        native = next((s for s in self.ctx.config["optional_zsh_completions"]
                       if s["provider"] == "upstream-managed" and self.ctx.home / s["destination"] == target), None)
        commands = native["commands"] if native else [target.name.removeprefix("_")]
        if checksum is None:
            if any(str(target) in entry.get("paths", {}) for name, entry in receipts.items()
                   if name.startswith("completion:")):
                raise RecoveryError("Removed completion still has an ownership receipt")
            return
        for command in commands:
            entry = receipts.get("completion:" + command, {})
            if (entry.get("paths") != {str(target): checksum} or
                    entry.get("provider") != ("upstream-managed" if native else "generated")):
                raise RecoveryError(f"Completion artifact/receipt pair disagrees: {target}: {command}")

    def recover_completion(self, value):
        target = self.completion_target(value)
        phase = value["phase"]
        if phase == "STAGING":
            self.cleanup()  # no target/state publication can precede PREPARED
            return
        if phase not in ("PREPARED", "ARTIFACT_PUBLISHED", "STATE_PUBLISHED", "COMMITTED", "ROLLED_BACK"):
            raise RecoveryError(f"Unknown completion phase at {self.journal}")
        current = sha(target) if regular(target, missing=True) else None
        if current not in (value["old_artifact"], value["new_artifact"]):
            raise RecoveryError(f"Artifact changed; recovery material at {self.root}")
        self.check_state(value)
        if phase in ("COMMITTED", "ROLLED_BACK"):
            prefix = "new" if phase == "COMMITTED" else "old"
            state = sha(self.ctx.receipts_path) if self.ctx.receipts_path.exists() else None
            if current != value[prefix + "_artifact"] or state != value[prefix + "_state"]:
                raise RecoveryError(f"Terminal transaction pair mismatched at {self.root}")
            if phase == "COMMITTED":
                self.validate_new_pair(target, json.loads(self.ctx.receipts_path.read_text()), current)
        else:
            for name, checksum in (("old-artifact", value["old_artifact"]), ("old-state", value["old_state"])):
                if checksum is not None:
                    regular(self.root / name)
                    if sha(self.root / name) != checksum:
                        raise RecoveryError(f"Invalid recovery copy: {self.root / name}")
            self.clear_stage(target)
            self.clear_stage(self.ctx.receipts_path)
            self.restore(target, self.root / "old-artifact", value["old_artifact"])
            self.restore(self.ctx.receipts_path, self.root / "old-state", value["old_state"])
            value["phase"] = "ROLLED_BACK"
            self.save(value)
        self.clear_stage(target)
        self.clear_stage(self.ctx.receipts_path)
        self.cleanup()

    def publish_completion(self, target, staged, proposed, validate):
        self.completion_target({"target": str(target)})
        self.validate_new_pair(target, proposed, sha(staged) if staged is not None else None)
        for destination in (target, self.ctx.receipts_path):
            leftover = destination.parent / self.stage_name(destination)
            if leftover.exists() or leftover.is_symlink():
                raise RecoveryError(f"Unjournaled publication stage preserved: {leftover}")
        value = self.start("completion", target=str(target))
        try:
            value["old_artifact"] = sha(target) if regular(target, missing=True) else None
            if value["old_artifact"]:
                durable_copy(target, self.root / "old-artifact")
            if staged is not None:
                durable_copy(staged, self.root / "new-artifact")
            value["new_artifact"] = sha(staged) if staged is not None else None
            self.receipt_backup(value, proposed)
            value["phase"] = "PREPARED"
            self.save(value)
            self.restore(target, self.root / "new-artifact", value["new_artifact"])
            value["phase"] = "ARTIFACT_PUBLISHED"
            self.save(value)
            validate()
            self.ctx.write_state("receipts.json", proposed)
            value["phase"] = "STATE_PUBLISHED"
            self.save(value)
            value["phase"] = "COMMITTED"
            self.save(value)
            self.ctx.receipts = proposed
            self.cleanup()
        except BaseException:
            if self.journal.exists():
                try:
                    self.recover_completion(self.load())
                    self.ctx.receipts = json.loads(self.ctx.receipts_path.read_text()) if self.ctx.receipts_path.exists() else {}
                except (OSError, ValueError, KeyError, BootstrapError) as error:
                    raise RecoveryError(f"Publication recovery failed; material preserved at {self.root}: {error}") from error
            raise

    def recover(self):
        if not self.root.exists() and not self.root.is_symlink():
            return
        try:
            if self.root.is_dir() and not self.root.is_symlink() and not list(self.root.iterdir()):
                if self.root.stat().st_uid != os.getuid() or self.root.stat().st_mode & 0o077:
                    raise RecoveryError(f"Unsafe empty transaction directory: {self.root}")
                self.root.rmdir()
                fsync_directory(self.ctx.state)
                return
            value = self.load()
            if value["kind"] == "completion":
                self.recover_completion(value)
            else:
                from .migration import recover
                recover(self.ctx, self, value)
        except (OSError, ValueError, KeyError, TypeError, BootstrapError) as error:
            raise RecoveryError(f"Recovery failed; material preserved at {self.root}: {error}") from error

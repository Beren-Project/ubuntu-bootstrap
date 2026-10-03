"""Exact baseline-owned launcher migration, with durable retirement recovery."""
import json
import os
from pathlib import Path

from .durability import RecoveryError, Transaction, durable_copy, fsync_directory, parents, regular, sha
from .inventories import normalize
from .platform import BootstrapError
from . import rust


def legacy_spec(ctx, profile):
    if profile == "python":
        return "uv", "uv", [ctx.home / ".local/bin" / n for n in ("uv", "uvx")]
    if profile == "julia":
        return "julia", "juliaup", [ctx.home / ".juliaup/bin" / n for n in ("juliaup", "julia")]
    raise RecoveryError("Unknown Cargo migration profile")


def legacy_evidence(ctx, path):
    if not path.exists() and not path.is_symlink():
        if any(p.is_symlink() for p in path.parents):
            raise BootstrapError(f"Symlinked legacy launcher parent preserved: {path}")
        return None
    parents(path)
    for parent in path.parents:
        if parent == ctx.home.parent:
            break
        if parent.stat().st_uid != ctx.user.pw_uid:
            raise BootstrapError(f"Legacy launcher parent has wrong ownership: {parent}")
    link = None
    if path.is_symlink():
        expected = ctx.home / ".juliaup/bin/julialauncher"
        if path != ctx.home / ".juliaup/bin/julia" or path.lstat().st_uid != ctx.user.pw_uid or os.readlink(path) != str(expected):
            raise BootstrapError(f"Unsupported legacy launcher symlink preserved: {path}")
        regular(expected)
        link = str(expected)
    else:
        regular(path)
    if not path.stat().st_mode & 0o111:
        raise BootstrapError(f"Non-executable legacy launcher preserved: {path}")
    return {"sha256": sha(path), "link": link}


def validate_runtime(ctx, profile):
    if profile == "python" and "python" in ctx.receipts:
        paths = [ctx.home / ".local/bin" / n for n in ("python", "python3")]
        if not ctx.owned("python", paths):
            raise BootstrapError("Legacy managed Python launchers are incomplete; preserved")
        actual = Path(ctx.output([ctx.home / ".cargo/bin/uv", "python", "find", "--managed-python", "--no-python-downloads"], cwd=ctx.cache))
        if actual.resolve() != paths[0].resolve():
            raise BootstrapError("Replacement uv does not select the existing managed Python; preserved")
        ctx.run([paths[0], "--version"])
    elif profile == "julia":
        from .julia import verify_release
        verify_release(ctx)


def flush_replacement(ctx, receipt):
    """Persist verified Cargo outputs/registration before retiring old copies."""
    cargo = ctx.home / ".cargo"
    files = [Path(p) for p in receipt["paths"]]
    files.append(cargo / ".crates.toml")
    if (cargo / ".crates2.json").exists():
        files.append(cargo / ".crates2.json")
    for path in files:
        parents(path)
        regular(path)
        with path.open("rb") as stream:
            os.fsync(stream.fileno())
    for directory in (cargo / "bin", cargo, ctx.home):
        fsync_directory(directory)


def install_application(ctx, profile):
    tool = ctx.config[profile]["cargo"]
    owner, manager, old_paths = legacy_spec(ctx, profile)
    receipt = ctx.receipts.get(owner, {})
    legacy = receipt.get("manager") == manager and set(receipt.get("paths", {})) == set(map(str, old_paths))
    observed = {str(p): legacy_evidence(ctx, p) for p in old_paths}
    if not legacy:
        if any(observed.values()):
            raise BootstrapError(f"Unproven legacy {tool['crate']} launchers preserved; inspect exact old paths before retrying")
        return rust.install_tool(ctx, tool)
    for path, evidence in observed.items():
        if evidence and evidence["sha256"] != receipt["paths"][path]:
            raise BootstrapError(f"Legacy {tool['crate']} changed outside bootstrap: {path}; preserved, migration refused")
    new_paths = [ctx.home / ".cargo/bin" / n for n in tool["bins"]]
    if any(p.exists() or p.is_symlink() for p in new_paths):
        raise BootstrapError(f"Unmanaged replacement {tool['crate']} files preserved; migration refused")
    rust.binstall(ctx)  # manager receipt must precede the migration snapshot
    tx = Transaction(ctx)
    state_stage = ctx.receipts_path.parent / tx.stage_name(ctx.receipts_path)
    if state_stage.exists() or state_stage.is_symlink():
        raise RecoveryError(f"Unjournaled publication stage preserved: {state_stage}")
    value = tx.start("migration", profile=profile, legacy=observed)
    if regular(ctx.receipts_path, missing=True):
        durable_copy(ctx.receipts_path, tx.root / "old-state")
    value["old_state"] = sha(ctx.receipts_path) if ctx.receipts_path.exists() else None
    value["phase"] = "INSTALLING"
    tx.save(value)
    try:
        replacement = rust.install_tool(ctx, tool, publish=False, migrating=True)
        if replacement is None:
            raise BootstrapError("Cargo migration was declined")
        validate_runtime(ctx, profile)
        if sha(ctx.receipts_path) != value["old_state"]:
            raise RecoveryError(f"Receipt state changed during Cargo installation; preserved at {tx.root}")
        flush_replacement(ctx, replacement)
        proposed = {**ctx.receipts, tool["crate"]: replacement}
        if profile == "julia":
            proposed["julia"] = {"paths": {}, "manager": "juliaup", "channel": ctx.config["julia"]["channel"]}
        proposed = normalize(proposed)
        tx.receipt_backup(value, proposed)
        value["replacement"] = replacement
        value["phase"] = "REPLACEMENT_VERIFIED"
        tx.save(value)
        recover(ctx, tx, value)
        ctx.receipts = proposed
        ctx.status("VERIFY", tool["crate"] + " migration", "Cargo owns launchers; exact legacy launchers retired")
        return replacement
    except BaseException as error:
        if tx.journal.exists():
            try:
                persisted = tx.load()
                if persisted["phase"] != "INSTALLING":
                    recover(ctx, tx, persisted)
                    ctx.receipts = json.loads(ctx.receipts_path.read_text())
                elif not any(p.exists() or p.is_symlink() for p in new_paths):
                    tx.cleanup()
                else:
                    raise RecoveryError(f"Cargo migration interrupted before ownership evidence was durable; preserve and inspect {tx.root}: {error}") from error
            except (OSError, ValueError, KeyError, TypeError, BootstrapError) as recovery_error:
                raise RecoveryError(f"Migration recovery failed; material preserved at {tx.root}: {recovery_error}") from recovery_error
        raise


def recover(ctx, tx, value):
    profile = value["profile"]
    owner, manager, old_paths = legacy_spec(ctx, profile)
    if set(value["legacy"]) != set(map(str, old_paths)):
        raise RecoveryError(f"Invalid legacy paths at {tx.journal}")
    if value["phase"] == "STAGING":
        tx.cleanup()
        return
    if value["phase"] == "INSTALLING":
        raise RecoveryError(f"Incomplete Cargo installer; no automatic adoption of outputs. Inspect {tx.root}")
    if value["phase"] not in ("REPLACEMENT_VERIFIED", "LEGACY_RETIRED", "COMMITTED"):
        raise RecoveryError(f"Unknown migration phase at {tx.journal}")
    tool = ctx.config[profile]["cargo"]
    replacement = value["replacement"]
    expected_paths = {str(ctx.home / ".cargo/bin" / n) for n in tool["bins"]}
    if (set(replacement["paths"]) != expected_paths or replacement.get("manager") != "cargo"
            or replacement.get("crate") != tool["crate"]):
        raise RecoveryError(f"Invalid replacement receipt at {tx.journal}")
    for name, checksum in replacement["paths"].items():
        path = Path(name)
        parents(path)
        regular(path)
        if sha(path) != checksum:
            raise RecoveryError(f"Replacement changed; preserved: {path}; recovery at {tx.root}")
    if rust.crate_state(ctx, tool) != replacement["version"]:
        raise RecoveryError(f"Replacement Cargo registration changed; recovery at {tx.root}")
    tx.check_state(value)
    for path in old_paths:
        current = legacy_evidence(ctx, path)
        expected = value["legacy"][str(path)]
        if current is not None and current != expected:
            raise RecoveryError(f"Legacy launcher changed during migration; preserved: {path}; recovery at {tx.root}")
    if value["phase"] == "COMMITTED":
        if any(p.exists() or p.is_symlink() for p in old_paths) or sha(ctx.receipts_path) != value["new_state"]:
            raise RecoveryError(f"Committed migration no longer matches; recovery at {tx.root}")
    else:
        # The retained new-state copy is verified before retiring any launcher.
        regular(tx.root / "new-state")
        if sha(tx.root / "new-state") != value["new_state"]:
            raise RecoveryError(f"Invalid migration state backup: {tx.root}")
        regular(tx.root / "old-state")
        if sha(tx.root / "old-state") != value["old_state"]:
            raise RecoveryError(f"Invalid legacy receipt backup: {tx.root}")
        prior = json.loads((tx.root / "old-state").read_text()).get(owner, {})
        if prior.get("manager") != manager or set(prior.get("paths", {})) != set(map(str, old_paths)):
            raise RecoveryError(f"Invalid baseline ownership evidence: {tx.root}")
        for name, evidence in value["legacy"].items():
            if evidence and evidence["sha256"] != prior["paths"][name]:
                raise RecoveryError(f"Legacy journal/receipt evidence disagrees: {tx.root}")
        proposed = json.loads((tx.root / "new-state").read_text())
        if proposed.get(tool["crate"]) != replacement:
            raise RecoveryError(f"Migration receipt mismatch: {tx.root}")
        tx.clear_stage(ctx.receipts_path)
        for path in old_paths:
            path.unlink(missing_ok=True)
            if path.parent.exists():
                fsync_directory(path.parent)
        value["phase"] = "LEGACY_RETIRED"
        tx.save(value)
        ctx.write_state("receipts.json", proposed)
        value["phase"] = "COMMITTED"
        tx.save(value)
        ctx.receipts = proposed
    tx.cleanup()

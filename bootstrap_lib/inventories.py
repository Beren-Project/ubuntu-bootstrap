"""Content-addressed diagnostic inventories; the manifest remains authority."""
from copy import deepcopy
import hashlib
import json

from .platform import BootstrapError

SECTION = "_completion_inventories"


def canonical(inventory):
    if not isinstance(inventory, dict) or any(
        not isinstance(k, str) or not isinstance(v, list) or
        any(not isinstance(p, str) for p in v) for k, v in inventory.items()
    ):
        raise BootstrapError("Malformed completion inventory")
    return {k: sorted(set(v)) for k, v in sorted(inventory.items())}


def identity(inventory):
    data = json.dumps(canonical(inventory), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def normalize(receipts):
    if not isinstance(receipts, dict):
        raise BootstrapError("Malformed receipts document")
    result = deepcopy(receipts)
    section = result.pop(SECTION, {"schema": 1, "snapshots": {}})
    if not isinstance(section, dict) or section.get("schema") != 1 or not isinstance(section.get("snapshots"), dict):
        raise BootstrapError("Malformed shared completion inventories")
    snapshots = section["snapshots"]
    for ref, contents in snapshots.items():
        if ref != identity(contents):
            raise BootstrapError(f"Completion inventory digest mismatch: {ref}")
    used = {}
    for name, entry in result.items():
        if not isinstance(entry, dict):
            raise BootstrapError(f"Malformed receipt: {name}")
        if not name.startswith("completion:"):
            continue
        if "inventory" in entry:
            contents = canonical(entry.pop("inventory"))
            ref = identity(contents)
            if "inventory_ref" in entry and entry["inventory_ref"] != ref:
                raise BootstrapError(f"Conflicting completion inventory: {name}")
            snapshots[ref] = contents
            entry["inventory_ref"] = ref
        if "inventory_ref" in entry:
            ref = entry["inventory_ref"]
            if not isinstance(ref, str) or ref not in snapshots:
                raise BootstrapError(f"Missing completion inventory: {name}: {ref}")
            used[ref] = canonical(snapshots[ref])
    if used:
        result[SECTION] = {"schema": 1, "snapshots": used}
    return result


def resolve(receipts, entry):
    return receipts[SECTION]["snapshots"][entry["inventory_ref"]]

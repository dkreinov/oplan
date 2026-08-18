#!/usr/bin/env python3
"""Capture and compare Git worktree state around one isolated executor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


SNAPSHOT_SCHEMA = "oplan-worktree-snapshot/v2"
LEGACY_SNAPSHOT_SCHEMA = "oplan-worktree-snapshot/v1"
ACCEPTED_SCHEMA = "oplan-accepted-state/v1"


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def nul_paths(output: bytes) -> set[str]:
    return {
        value.decode("utf-8", errors="surrogateescape")
        for value in output.split(b"\0")
        if value
    }


def case_insensitive_filesystem(root: Path) -> bool:
    return os.path.exists(root / ".git") and os.path.exists(root / ".GIT")


def fold_parts(value: str, insensitive: bool) -> tuple[str, ...]:
    parts = Path(value).parts
    if insensitive:
        return tuple(part.lower() for part in parts)
    return parts


def is_linklike(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        attributes = 0
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(attributes & reparse_point)


def safe_relative(value: str) -> bool:
    path = Path(value)
    return bool(value) and value != "." and not path.is_absolute() and ".." not in path.parts


def safe_worktree_target(root: Path, relative: str, *, allow_final_link: bool = False) -> Path:
    if not safe_relative(relative):
        raise RuntimeError(f"invalid repo-relative path: {relative}")
    resolved_root = root.resolve()
    target = root / relative
    check_target = target.parent if allow_final_link else target
    try:
        check_target.resolve().relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"path resolves outside the Git worktree: {relative}") from exc
    parts = Path(relative).parts
    last_index = len(parts)
    for index in range(1, last_index + 1):
        if allow_final_link and index == last_index:
            continue
        prefix = root.joinpath(*parts[:index])
        if not os.path.lexists(prefix):
            continue
        if is_linklike(prefix):
            raise RuntimeError(f"path traverses a symlink or junction: {relative}")
    return target


def reject_linklike_descendants(path: Path, relative: str) -> None:
    if not path.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
        base = Path(dirpath)
        for name in dirnames:
            if is_linklike(base / name):
                raise RuntimeError(f"write_set directory contains a symlink or junction: {relative}")
        for name in filenames:
            if is_linklike(base / name):
                raise RuntimeError(f"write_set directory contains a symlink or junction: {relative}")


def within(path: str, root: str, insensitive: bool) -> bool:
    path_parts = fold_parts(path, insensitive)
    root_parts = fold_parts(root, insensitive)
    return path_parts[: len(root_parts)] == root_parts


def strictly_within(path: str, root: str, insensitive: bool) -> bool:
    return within(path, root, insensitive) and len(fold_parts(path, insensitive)) > len(
        fold_parts(root, insensitive)
    )


def overlaps(first: str, second: str, insensitive: bool) -> bool:
    a, b = fold_parts(first, insensitive), fold_parts(second, insensitive)
    return a == b[: len(a)] or b == a[: len(b)]


def worktree_state(repo: Path, relative: str) -> str:
    path = repo / relative
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "missing"
    mode = f"{info.st_mode & 0o7777:o}"
    if path.is_symlink():
        payload = os.readlink(path).encode("utf-8", errors="surrogateescape")
        return f"symlink:{mode}:{hashlib.sha256(payload).hexdigest()}"
    if path.is_file():
        return f"file:{mode}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    if path.is_dir():
        return f"directory:{mode}"
    return f"other:{info.st_mode}"


def path_state(repo: Path, relative: str) -> dict[str, str]:
    worktree = worktree_state(repo, relative)
    index = git(repo, "ls-files", "--stage", "-z", "--", relative)
    return {"worktree": worktree, "index": hashlib.sha256(index).hexdigest()}


def tool_cache(relative: str) -> bool:
    """Tool caches are side effects of running validation, not executor writes.

    Running any Python validation regenerates them, so treating them as
    undeclared writes would deadlock every retry of a Python leaf.
    """
    parts = Path(relative).parts
    return (
        "__pycache__" in parts
        or ".pytest_cache" in parts
        or relative.endswith((".pyc", ".pyo"))
    )


def collected(relative: str, excluded: set[str], insensitive: bool) -> bool:
    """The single membership rule for the undeclared-write comparison.

    Both sides of the comparison must pass through this predicate, because a
    snapshot written by an older guard can name paths this guard never
    collects, and comparing them would report an undeclared write for a file
    nothing wrote.
    """
    return (
        bool(relative)
        and not relative.startswith(".git/")
        and not tool_cache(relative)
        and not any(overlaps(relative, item, insensitive) for item in excluded)
    )


def collect(repo: Path, excluded: set[str], insensitive: bool) -> dict[str, dict[str, str]]:
    paths = nul_paths(git(repo, "diff", "HEAD", "--name-only", "-z"))
    paths |= nul_paths(git(repo, "ls-files", "--others", "--exclude-standard", "-z"))
    paths |= nul_paths(git(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"))
    return {
        relative: path_state(repo, relative)
        for relative in sorted(paths)
        if collected(relative, excluded, insensitive)
    }


def snapshot_schema(before: dict) -> str:
    value = before.get("schema", LEGACY_SNAPSHOT_SCHEMA)
    if value not in (SNAPSHOT_SCHEMA, LEGACY_SNAPSHOT_SCHEMA):
        raise RuntimeError(
            f"unsupported snapshot state grammar: {value!r}; re-capture the snapshot with this guard"
        )
    return value


def legacy_state(value: str) -> str:
    parts = value.split(":")
    if parts[0] in ("file", "symlink") and len(parts) == 3:
        return f"{parts[0]}:{parts[2]}"
    if parts[0] == "directory":
        return "directory"
    return value


def legacy_path_state(state: dict[str, str]) -> dict[str, str]:
    return {"worktree": legacy_state(state["worktree"]), "index": state["index"]}


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def read_write_set(control_path: Path) -> list[str]:
    control = json.loads(control_path.read_text(encoding="utf-8"))
    allowed = control.get("write_set")
    if not isinstance(allowed, list) or not all(isinstance(path, str) and safe_relative(path) for path in allowed):
        raise RuntimeError("control has an invalid write_set")
    return allowed


def sidecar_dir(snapshot: Path) -> Path:
    return snapshot.with_name(snapshot.name + ".files")


def snapshot_write_set(repo: Path, sidecar: Path, write_set: list[str]) -> dict[str, str]:
    """Record each write-set path's pre-attempt state and copy its bytes into the sidecar."""
    states: dict[str, str] = {}
    for relative in write_set:
        safe_worktree_target(repo, relative)
        state = worktree_state(repo, relative)
        states[relative] = state
        if state == "missing" or state.startswith("symlink:"):
            continue
        source = repo / relative
        destination = sidecar / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if state.startswith("directory:"):
            reject_linklike_descendants(source, relative)
            shutil.copytree(source, destination, dirs_exist_ok=True)
        elif state.startswith("file:"):
            shutil.copy2(source, destination)
        else:
            raise RuntimeError(f"cannot snapshot write_set path with unsupported state: {relative}")
    return states


def capture(repo: Path, snapshot: Path, control: Path, additional_excluded: list[str]) -> int:
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    insensitive = case_insensitive_filesystem(root)
    snapshot = snapshot.resolve()
    sidecar = sidecar_dir(snapshot)
    excluded: set[str] = set()
    for candidate in (snapshot, sidecar):
        try:
            excluded.add(candidate.relative_to(root).as_posix())
        except ValueError:
            pass
    for relative in additional_excluded:
        if not safe_relative(relative):
            raise RuntimeError(f"invalid excluded path: {relative}")
        excluded.add(relative)
    write_set = read_write_set(control)
    if sidecar.exists():
        shutil.rmtree(sidecar)
    write_set_states = snapshot_write_set(root, sidecar, write_set)
    value = {
        "repo": str(root),
        "excluded": sorted(excluded),
        "states": collect(root, excluded, insensitive),
        "write_set_states": write_set_states,
        "schema": SNAPSHOT_SCHEMA,
    }
    atomic_json(snapshot, value)
    print(f"oplan worktree guard: CAPTURED ({len(value['states'])} changed paths)")
    return 0


def delete_if_present(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)


def restore(repo: Path, snapshot: Path, control_path: Path) -> int:
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    before = json.loads(snapshot.read_text(encoding="utf-8"))
    grammar = snapshot_schema(before)
    if grammar == LEGACY_SNAPSHOT_SCHEMA:
        print(
            "oplan worktree guard: NOTE — snapshot predates the mode-tagged state grammar; "
            "comparing in the pre-mode grammar (file mode changes are not detected)"
        )
    if before.get("repo") != str(root):
        raise RuntimeError("snapshot belongs to another Git worktree")
    recorded_states = before.get("write_set_states")
    if not isinstance(recorded_states, dict):
        raise RuntimeError("snapshot has no write_set_states to restore")
    write_set = read_write_set(control_path)
    if sorted(write_set) != sorted(recorded_states):
        raise RuntimeError("control write_set does not match the snapshot's recorded write_set")
    sidecar = sidecar_dir(snapshot)
    for relative in write_set:
        target = safe_worktree_target(root, relative, allow_final_link=True)
        recorded = recorded_states[relative]
        if recorded.startswith("symlink:"):
            raise RuntimeError(f"cannot restore symlink write_set path (unsupported): {relative}")
        if is_linklike(target):
            raise RuntimeError(
                f"write_set path is a symlink or junction; remove it and rerun restore: {relative}"
            )
        if recorded == "missing":
            delete_if_present(target)
            continue
        source = sidecar / relative
        if not source.exists():
            raise RuntimeError(f"missing sidecar copy for write_set path: {relative}")
        delete_if_present(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        kind = recorded.split(":", 1)[0]
        if kind == "directory":
            shutil.copytree(source, target)
        elif kind == "file":
            shutil.copy2(source, target)
        else:
            raise RuntimeError(f"unsupported recorded state for {relative}: {recorded}")
    mismatches = []
    for relative in write_set:
        current = worktree_state(root, relative)
        if grammar == LEGACY_SNAPSHOT_SCHEMA:
            current = legacy_state(current)
        if current != recorded_states[relative]:
            mismatches.append(relative)
    mismatches.sort()
    if mismatches:
        print("oplan worktree guard: FAIL")
        for relative in mismatches:
            print(f"- restore mismatch: {relative}")
        return 1
    print(f"oplan worktree guard: RESTORED ({len(write_set)} paths)")
    return 0


def check(repo: Path, snapshot: Path, control_path: Path, workspace: Path) -> int:
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    insensitive = case_insensitive_filesystem(root)
    try:
        workspace_rel = workspace.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError("workspace is outside the Git worktree") from exc
    before = json.loads(snapshot.read_text(encoding="utf-8"))
    grammar = snapshot_schema(before)
    if grammar == LEGACY_SNAPSHOT_SCHEMA:
        print(
            "oplan worktree guard: NOTE — snapshot predates the mode-tagged state grammar; "
            "comparing in the pre-mode grammar (file mode changes are not detected)"
        )
    if before.get("repo") != str(root):
        raise RuntimeError("snapshot belongs to another Git worktree")
    allowed = read_write_set(control_path)
    if any(
        overlaps(path, ".git", insensitive) or overlaps(path, workspace_rel, insensitive)
        for path in allowed
    ):
        raise RuntimeError("control write_set overlaps Git metadata or the oplan workspace")
    for relative in allowed:
        safe_worktree_target(root, relative)
        reject_linklike_descendants(root / relative, relative)
    excluded = set(before.get("excluded", []))
    attempts_root = f"{workspace_rel}/attempts"
    invalid_exclusions = sorted(
        path for path in excluded if not strictly_within(path, attempts_root, insensitive)
    )
    if invalid_exclusions:
        raise RuntimeError(f"snapshot excludes paths outside workspace attempts: {invalid_exclusions}")
    previous = {
        path: state
        for path, state in before.get("states", {}).items()
        if collected(path, excluded, insensitive)
    }
    current = collect(root, excluded, insensitive)
    if grammar == LEGACY_SNAPSHOT_SCHEMA:
        current = {path: legacy_path_state(state) for path, state in current.items()}
    changed = {
        path for path in set(previous) | set(current) if previous.get(path) != current.get(path)
    }
    violations = sorted(
        path for path in changed if not any(within(path, permitted, insensitive) for permitted in allowed)
    )
    if violations:
        print("oplan worktree guard: FAIL")
        for path in violations:
            print(f"- undeclared write: {path}")
        return 1
    print(f"oplan worktree guard: PASS ({len(changed)} changed paths, all declared)")
    return 0


def accepted_worktree_state(repo: Path, relative: str) -> str:
    state = worktree_state(repo, relative)
    if not state.startswith("directory:"):
        return state
    root = repo / relative
    reject_linklike_descendants(root, relative)
    digest = hashlib.sha256()
    digest.update(state.encode("ascii"))
    digest.update(b"\0")
    descendants = sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())
    for descendant in descendants:
        name = descendant.relative_to(root).as_posix()
        digest.update(name.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        descendant_relative = descendant.relative_to(repo).as_posix()
        digest.update(worktree_state(repo, descendant_relative).encode("ascii"))
        digest.update(b"\0")
    return "tree:" + state.split(":", 1)[1] + ":" + digest.hexdigest()


def accepted_path_state(repo: Path, relative: str) -> dict[str, str]:
    worktree = accepted_worktree_state(repo, relative)
    index = git(repo, "ls-files", "--stage", "-z", "--", relative)
    return {"worktree": worktree, "index": hashlib.sha256(index).hexdigest()}


def accepted_root(repo: Path, manifest_path: Path) -> Path:
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    try:
        manifest_path.resolve().relative_to(root)
    except ValueError as exc:
        raise RuntimeError("accepted manifest must be inside the Git worktree") from exc
    return root


def accepted_schema(manifest: dict, root: Path) -> None:
    if manifest.get("schema") != ACCEPTED_SCHEMA:
        raise RuntimeError(
            "accepted manifest was written under a different state grammar; "
            "re-initialize the manifest"
        )
    if manifest.get("repo") != str(root):
        raise RuntimeError("accepted manifest belongs to another Git worktree")


def accepted_controls(root: Path, manifest: dict) -> tuple[list[dict[str, str]], set[str]]:
    controls = manifest["controls"]
    if not isinstance(controls, list):
        raise RuntimeError("accepted manifest controls must be a list")
    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    write_set: set[str] = set()
    for entry in controls:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise RuntimeError("accepted manifest has an invalid control entry")
        path = entry["path"]
        sha256 = entry["sha256"]
        if not isinstance(path, str) or not safe_relative(path) or path in seen:
            raise RuntimeError("accepted manifest has an invalid or duplicate control path")
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise RuntimeError("accepted manifest has an invalid control hash")
        target = safe_worktree_target(root, path)
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != sha256:
            raise RuntimeError(f"accepted manifest control hash mismatch: {path}")
        seen.add(path)
        normalized.append({"path": path, "sha256": sha256})
        write_set |= set(read_write_set(target))
    return normalized, write_set


def init_accepted(repo: Path, manifest_path: Path) -> int:
    root = accepted_root(repo, manifest_path)
    if manifest_path.is_file():
        return verify_accepted(root, manifest_path)
    value = {
        "schema": ACCEPTED_SCHEMA,
        "repo": str(root),
        "controls": [],
        "write_set_states": {},
    }
    atomic_json(manifest_path, value)
    print("oplan worktree guard: ACCEPTED STATE INITIALIZED")
    return 0


def record_accepted(repo: Path, control_path: Path, manifest_path: Path) -> int:
    root = accepted_root(repo, manifest_path)
    if not manifest_path.is_file():
        raise RuntimeError("accepted-state manifest was not initialized")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema",
        "repo",
        "controls",
        "write_set_states",
    }:
        raise RuntimeError("accepted manifest has an invalid schema")
    accepted_schema(manifest, root)
    recorded = manifest["write_set_states"]
    controls, previous = accepted_controls(root, manifest)
    if not isinstance(recorded, dict) or sorted(recorded) != sorted(previous):
        raise RuntimeError("accepted manifest states do not match its controls")
    try:
        control_relative = control_path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError("control is outside the Git worktree") from exc
    new_write_set = read_write_set(control_path)
    control_sha256 = hashlib.sha256(control_path.read_bytes()).hexdigest()
    existing = next((entry for entry in controls if entry["path"] == control_relative), None)
    if existing is not None and existing["sha256"] != control_sha256:
        raise RuntimeError("accepted control path was reused with different bytes")
    if existing is not None:
        reused = True
    else:
        reused = False
        controls = controls + [{"path": control_relative, "sha256": control_sha256}]
    combined: set[str] = set()
    for entry in controls:
        combined |= set(read_write_set(root / entry["path"]))
    for relative in combined:
        safe_worktree_target(root, relative)
    insensitive = case_insensitive_filesystem(root)
    if reused:
        refresh: set[str] = set()
    else:
        refresh = {p for p in combined if any(within(p, n, insensitive) for n in new_write_set)}
    drifted = sorted(
        p
        for p in recorded
        if p not in refresh and accepted_path_state(root, p) != recorded[p]
    )
    if drifted:
        print("oplan worktree guard: FAIL")
        for p in drifted:
            if reused and any(within(p, n, insensitive) for n in new_write_set):
                print(f"- accepted state drifted under an already-recorded control: {p}")
            elif any(strictly_within(n, p, insensitive) for n in new_write_set):
                print(
                    "- accepted state drifted in an undeclared parent directory; "
                    f"add it to the write set: {p}"
                )
            else:
                print(f"- accepted state drifted outside the accepted write set: {p}")
        return 1
    states = {
        p: accepted_path_state(root, p) if (p in refresh or p not in recorded) else recorded[p]
        for p in sorted(combined)
    }
    value = {
        "schema": manifest["schema"],
        "repo": manifest["repo"],
        "controls": controls,
        "write_set_states": states,
    }
    atomic_json(manifest_path, value)
    print(
        f"oplan worktree guard: ACCEPTED ({len(controls)} controls, {len(combined)} current paths)"
    )
    return 0


def verify_accepted(repo: Path, manifest_path: Path) -> int:
    root = accepted_root(repo, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema",
        "repo",
        "controls",
        "write_set_states",
    }:
        raise RuntimeError("accepted manifest has an invalid schema")
    accepted_schema(manifest, root)
    controls, write_set = accepted_controls(root, manifest)
    for relative in write_set:
        safe_worktree_target(root, relative)
    states = manifest.get("write_set_states")
    if not isinstance(states, dict) or sorted(states) != sorted(write_set):
        raise RuntimeError("accepted manifest states do not match its controls")
    mismatches = sorted(
        relative
        for relative in write_set
        if accepted_path_state(root, relative) != states[relative]
    )
    if mismatches:
        print("oplan worktree guard: FAIL")
        for relative in mismatches:
            print(f"- accepted state mismatch: {relative}")
        return 1
    print(
        "oplan worktree guard: ACCEPTED STATE VERIFIED "
        f"({len(controls)} controls, {len(write_set)} paths)"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("repo", type=Path)
    capture_parser.add_argument("snapshot", type=Path)
    capture_parser.add_argument("control", type=Path)
    capture_parser.add_argument("excluded", nargs="*", help="repo-relative harness artifacts written before check")
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("repo", type=Path)
    check_parser.add_argument("snapshot", type=Path)
    check_parser.add_argument("control", type=Path)
    check_parser.add_argument("workspace", type=Path)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("repo", type=Path)
    restore_parser.add_argument("snapshot", type=Path)
    restore_parser.add_argument("control", type=Path)
    init_accepted_parser = subparsers.add_parser("init-accepted")
    init_accepted_parser.add_argument("repo", type=Path)
    init_accepted_parser.add_argument("manifest", type=Path)
    record_accepted_parser = subparsers.add_parser("record-accepted")
    record_accepted_parser.add_argument("repo", type=Path)
    record_accepted_parser.add_argument("control", type=Path)
    record_accepted_parser.add_argument("manifest", type=Path)
    verify_accepted_parser = subparsers.add_parser("verify-accepted")
    verify_accepted_parser.add_argument("repo", type=Path)
    verify_accepted_parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            return capture(args.repo.resolve(), args.snapshot, args.control.resolve(), args.excluded)
        if args.command == "restore":
            return restore(args.repo.resolve(), args.snapshot.resolve(), args.control.resolve())
        if args.command == "init-accepted":
            return init_accepted(args.repo.resolve(), args.manifest.resolve())
        if args.command == "record-accepted":
            return record_accepted(args.repo.resolve(), args.control.resolve(), args.manifest.resolve())
        if args.command == "verify-accepted":
            return verify_accepted(args.repo.resolve(), args.manifest.resolve())
        return check(args.repo.resolve(), args.snapshot.resolve(), args.control.resolve(), args.workspace.resolve())
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"oplan worktree guard: ERROR — {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

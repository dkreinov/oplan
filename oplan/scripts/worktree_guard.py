#!/usr/bin/env python3
"""Capture and compare Git worktree state around one isolated executor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


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


def worktree_state(repo: Path, relative: str) -> str:
    path = repo / relative
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "missing"
    if path.is_symlink():
        payload = os.readlink(path).encode("utf-8", errors="surrogateescape")
        return "symlink:" + hashlib.sha256(payload).hexdigest()
    if path.is_file():
        return "file:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if path.is_dir():
        return "directory"
    return f"other:{info.st_mode}"


def path_state(repo: Path, relative: str) -> dict[str, str]:
    worktree = worktree_state(repo, relative)
    index = git(repo, "ls-files", "--stage", "-z", "--", relative)
    return {"worktree": worktree, "index": hashlib.sha256(index).hexdigest()}


def interpreter_cache(relative: str) -> bool:
    """Bytecode caches are interpreter side effects, not executor writes.

    Running any Python validation regenerates them, so treating them as
    undeclared writes would deadlock every retry of a Python leaf.
    """
    return "__pycache__" in Path(relative).parts or relative.endswith((".pyc", ".pyo"))


def collect(repo: Path, excluded: set[str]) -> dict[str, dict[str, str]]:
    paths = nul_paths(git(repo, "diff", "HEAD", "--name-only", "-z"))
    paths |= nul_paths(git(repo, "ls-files", "--others", "--exclude-standard", "-z"))
    paths |= nul_paths(git(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"))
    return {
        relative: path_state(repo, relative)
        for relative in sorted(paths)
        if relative
        and not relative.startswith(".git/")
        and not interpreter_cache(relative)
        and not any(overlaps(relative, item) for item in excluded)
    }


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


def safe_relative(value: str) -> bool:
    path = Path(value)
    return bool(value) and value != "." and not path.is_absolute() and ".." not in path.parts


def overlaps(first: str, second: str) -> bool:
    a, b = Path(first).parts, Path(second).parts
    return a == b[: len(a)] or b == a[: len(b)]


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
        state = worktree_state(repo, relative)
        states[relative] = state
        if state == "missing" or state.startswith("symlink:"):
            continue
        source = repo / relative
        destination = sidecar / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if state == "directory":
            shutil.copytree(source, destination, dirs_exist_ok=True)
        elif state.startswith("file:"):
            shutil.copy2(source, destination)
        else:
            raise RuntimeError(f"cannot snapshot write_set path with unsupported state: {relative}")
    return states


def capture(repo: Path, snapshot: Path, control: Path, additional_excluded: list[str]) -> int:
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
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
        "states": collect(root, excluded),
        "write_set_states": write_set_states,
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
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"write_set path escapes the repo root: {relative}") from exc
        recorded = recorded_states[relative]
        if recorded == "missing":
            delete_if_present(target)
            continue
        if recorded.startswith("symlink:"):
            raise RuntimeError(f"cannot restore symlink write_set path (unsupported): {relative}")
        source = sidecar / relative
        if not source.exists():
            raise RuntimeError(f"missing sidecar copy for write_set path: {relative}")
        delete_if_present(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if recorded == "directory":
            shutil.copytree(source, target)
        elif recorded.startswith("file:"):
            shutil.copy2(source, target)
        else:
            raise RuntimeError(f"unsupported recorded state for {relative}: {recorded}")
    mismatches = sorted(
        relative for relative in write_set if worktree_state(root, relative) != recorded_states[relative]
    )
    if mismatches:
        print("oplan worktree guard: FAIL")
        for relative in mismatches:
            print(f"- restore mismatch: {relative}")
        return 1
    print(f"oplan worktree guard: RESTORED ({len(write_set)} paths)")
    return 0


def check(repo: Path, snapshot: Path, control_path: Path, workspace: Path) -> int:
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    try:
        workspace_rel = workspace.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError("workspace is outside the Git worktree") from exc
    before = json.loads(snapshot.read_text(encoding="utf-8"))
    if before.get("repo") != str(root):
        raise RuntimeError("snapshot belongs to another Git worktree")
    allowed = read_write_set(control_path)
    if any(overlaps(path, ".git") or overlaps(path, workspace_rel) for path in allowed):
        raise RuntimeError("control write_set overlaps Git metadata or the oplan workspace")
    excluded = set(before.get("excluded", []))
    attempt_prefix = f"{workspace_rel}/attempts/"
    invalid_exclusions = sorted(path for path in excluded if not path.startswith(attempt_prefix))
    if invalid_exclusions:
        raise RuntimeError(f"snapshot excludes paths outside workspace attempts: {invalid_exclusions}")
    current = collect(root, excluded)
    previous = before.get("states", {})
    changed = {
        path for path in set(previous) | set(current) if previous.get(path) != current.get(path)
    }
    violations = sorted(
        path for path in changed if not any(overlaps(path, permitted) for permitted in allowed)
    )
    if violations:
        print("oplan worktree guard: FAIL")
        for path in violations:
            print(f"- undeclared write: {path}")
        return 1
    print(f"oplan worktree guard: PASS ({len(changed)} changed paths, all declared)")
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
    args = parser.parse_args()
    try:
        if args.command == "capture":
            return capture(args.repo.resolve(), args.snapshot, args.control.resolve(), args.excluded)
        if args.command == "restore":
            return restore(args.repo.resolve(), args.snapshot.resolve(), args.control.resolve())
        return check(args.repo.resolve(), args.snapshot.resolve(), args.control.resolve(), args.workspace.resolve())
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"oplan worktree guard: ERROR — {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

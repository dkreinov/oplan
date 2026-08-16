#!/usr/bin/env python3
"""Capture and compare Git worktree state around one isolated executor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def path_state(repo: Path, relative: str) -> dict[str, str]:
    path = repo / relative
    try:
        info = path.lstat()
    except FileNotFoundError:
        worktree = "missing"
    else:
        if path.is_symlink():
            payload = os.readlink(path).encode("utf-8", errors="surrogateescape")
            worktree = "symlink:" + hashlib.sha256(payload).hexdigest()
        elif path.is_file():
            worktree = "file:" + hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            worktree = "directory"
        else:
            worktree = f"other:{info.st_mode}"
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
        for relative in sorted(paths - excluded)
        if relative and not relative.startswith(".git/") and not interpreter_cache(relative)
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


def capture(repo: Path, snapshot: Path, additional_excluded: list[str]) -> int:
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    snapshot = snapshot.resolve()
    try:
        snapshot_rel = snapshot.relative_to(root).as_posix()
        excluded = {snapshot_rel}
    except ValueError:
        excluded = set()
    for relative in additional_excluded:
        if not safe_relative(relative):
            raise RuntimeError(f"invalid excluded path: {relative}")
        excluded.add(relative)
    value = {"repo": str(root), "excluded": sorted(excluded), "states": collect(root, excluded)}
    atomic_json(snapshot, value)
    print(f"oplan worktree guard: CAPTURED ({len(value['states'])} changed paths)")
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
    control = json.loads(control_path.read_text(encoding="utf-8"))
    allowed = control.get("write_set")
    if not isinstance(allowed, list) or not all(isinstance(path, str) and safe_relative(path) for path in allowed):
        raise RuntimeError("control has an invalid write_set")
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
    capture_parser.add_argument("excluded", nargs="*", help="repo-relative harness artifacts written before check")
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("repo", type=Path)
    check_parser.add_argument("snapshot", type=Path)
    check_parser.add_argument("control", type=Path)
    check_parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            return capture(args.repo.resolve(), args.snapshot, args.excluded)
        return check(args.repo.resolve(), args.snapshot.resolve(), args.control.resolve(), args.workspace.resolve())
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"oplan worktree guard: ERROR — {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

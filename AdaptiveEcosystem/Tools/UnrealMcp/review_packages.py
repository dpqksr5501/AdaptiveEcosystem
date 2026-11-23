"""Record or review the saved Unreal packages for one owned-map edit."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT.parent
CONTENT = PROJECT.relative_to(ROOT).as_posix() + "/Content"
PACKAGE_EXTENSIONS = (".umap", ".uasset")


def git(*args):
    result = subprocess.run(["git", "--no-optional-locks", *args], cwd=ROOT, capture_output=True)
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Git inspection failed. {message}")
    return result.stdout.decode("utf-8")


def package_name(path):
    if not re.fullmatch(r"/Game(?:/[\w-]+)+", path):
        raise ValueError(f"Expected a /Game package path without an extension: {path}")
    return path.removeprefix("/Game/")


def in_scope(path, level, assets):
    path = path.casefold()
    level = level.casefold()
    return (
        path == f"{CONTENT}/{level}.umap".casefold()
        or any(path == f"{CONTENT}/{asset}.uasset".casefold() for asset in assets)
        or any(path.startswith(f"{CONTENT}/{folder}/{level}/".casefold())
               for folder in ("__ExternalActors__", "__ExternalObjects__"))
    )


def is_package(path):
    return path.lower().endswith(PACKAGE_EXTENSIONS)


def dirty_packages():
    statuses = {
        row[3:]: row[:2]
        for row in git("status", "--porcelain=v1", "-z", "--no-renames", "-uall", "--", CONTENT).split("\0")
        if row and is_package(row[3:])
    }
    index_entries = {}
    for row in git("ls-files", "--stage", "-z", "--", CONTENT).split("\0"):
        if row:
            entry, path = row.split("\t", 1)
            if path in statuses:
                index_entries.setdefault(path, []).append(entry)
    packages = {}
    for path, status in statuses.items():
        file = ROOT / path
        digest = None
        if file.is_file():
            with file.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
        packages[path] = {"status": status, "index": index_entries.get(path, []), "sha256": digest}
    return packages


def revision(ref):
    return git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").strip()


def branch_packages(base, head):
    return {
        path for path in git("diff", "--name-only", "--no-renames", "-z", base, head, "--", CONTENT).split("\0")
        if is_package(path)
    }


def comparison(head, refs, pending):
    remote, conflicts = set(), set()
    for ref in refs:
        other = revision(ref)
        base = git("merge-base", head, other).strip()
        incoming = branch_packages(base, other)
        remote.update(incoming)
        conflicts.update(overlaps(branch_packages(base, head) | pending, incoming))
    return remote, conflicts


def overlaps(paths, other):
    lookup = {path.casefold() for path in other}
    return {path for path in paths if path.casefold() in lookup}


def report(title, paths):
    print(f"{title} ({len(paths)})")
    for path in sorted(paths):
        print(f"  {path}")


def snapshot(args, path, head, branch):
    level = package_name(args.map)
    assets = [package_name(asset) for asset in args.asset]
    before = dirty_packages()
    scoped = {name for name in before if in_scope(name, level, assets)}
    remote, conflicts = comparison(head, args.against, scoped)
    conflicts = {name for name in conflicts if in_scope(name, level, assets)}
    report("Existing local changes within the selected scope", scoped)
    report("Changes within the selected scope on comparison branches",
           {name for name in remote if in_scope(name, level, assets)})
    if conflicts:
        report("Overlapping packages to resolve before editing", conflicts)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump({"branch": branch, "head": head, "level": level, "assets": assets,
                   "refs": args.against, "before": before}, stream, ensure_ascii=False, indent=2)
    print(f"Snapshot recorded in {path.relative_to(ROOT)}")
    return 0


def review(path, head, branch):
    state = json.loads(path.read_text(encoding="utf-8"))
    if (state["head"], state["branch"]) != (head, branch):
        raise ValueError("Branch or HEAD changed since the snapshot. Review from the original checkout.")
    before, after = state["before"], dirty_packages()
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    scope = {"level": state["level"], "assets": state["assets"]}
    outside = {name for name in changed if not in_scope(name, **scope)}
    scoped = {name for name in after if in_scope(name, **scope)}
    remote, conflicts = comparison(head, state["refs"], changed | scoped)
    conflicts = {name for name in conflicts if in_scope(name, **scope)} | overlaps(outside, remote)
    report("Packages changed since the snapshot", changed)
    report("Packages changed outside the declared scope", outside)
    report("Overlapping packages on comparison branches", conflicts)
    return 1 if outside or conflicts else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("snapshot")
    start.add_argument("record")
    start.add_argument("--map", required=True, help="Package path of the owned map, starting with /Game/.")
    start.add_argument("--asset", action="append", default=[], help="Additional owned /Game asset. Repeat as needed.")
    start.add_argument("--against", required=True, action="append", help="Fetched integration or peer branch. Repeat as needed.")
    end = commands.add_parser("review")
    end.add_argument("record")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.record):
        parser.error("Record name may contain only letters, numbers, hyphens and underscores.")
    path = PROJECT / "Saved" / "UnrealMcp" / f"{args.record}.json"
    try:
        head = revision("HEAD")
        branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
        return snapshot(args, path, head, branch) if args.command == "snapshot" else review(path, head, branch)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

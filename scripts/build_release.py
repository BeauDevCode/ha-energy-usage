"""Build the exact deterministic Energy Usage release archive."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = "custom_components/energy_usage/"
COMMIT = re.compile(r"[0-9a-f]{40}\Z", re.ASCII)
VERSION = re.compile(r"0\.[0-9]+\.[0-9]+(?:-rc\.[1-9][0-9]*)?\Z", re.ASCII)


def _git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def _tracked_component_files(commit: str) -> tuple[str, ...]:
    raw = _git("ls-tree", "-r", "-z", commit, COMPONENT)
    paths: list[str] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, _object_id = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if kind != "blob" or mode not in {"100644", "100755"} or not path.startswith(COMPONENT):
            raise ValueError("unsupported release tree entry")
        paths.append(path)
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("invalid release tree")
    return tuple(sorted(paths))


def _write(archive: zipfile.ZipFile, path: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build(*, version: str, commit: str, output: Path) -> None:
    """Build one archive from an exact local Git commit."""
    if VERSION.fullmatch(version) is None or COMMIT.fullmatch(commit) is None:
        raise ValueError("invalid release identity")
    resolved = _git("rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    if resolved != commit:
        raise ValueError("release commit must be exact")
    files = _tracked_component_files(commit)
    manifest_path = f"{COMPONENT}manifest.json"
    if manifest_path not in files:
        raise ValueError("release manifest missing")
    manifest = json.loads(_git("show", f"{commit}:{manifest_path}"))
    if (
        manifest.get("domain") != "energy_usage"
        or manifest.get("version") != version
        or manifest.get("requirements") != []
    ):
        raise ValueError("release manifest mismatch")

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = (
        json.dumps(
            {"commit": commit, "version": version}, sort_keys=True, separators=(",", ":")
        ).encode()
        + b"\n"
    )
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, "w") as archive:
            for path in files:
                _write(archive, path, _git("show", f"{commit}:{path}"))
            _write(archive, f"{COMPONENT}release.json", metadata)
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    build(version=arguments.version, commit=arguments.commit, output=arguments.output)


if __name__ == "__main__":
    main()

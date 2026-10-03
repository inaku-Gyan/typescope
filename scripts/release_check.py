"""Validate a release tag against the package metadata and built artifacts."""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path


def _metadata_version(artifact: Path) -> str:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            metadata_name = next(
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            )
            contents = archive.read(metadata_name).decode()
    else:
        with tarfile.open(artifact, "r:gz") as archive:
            metadata_name = next(
                member
                for member in archive.getmembers()
                if member.name.endswith("/PKG-INFO")
            )
            metadata = archive.extractfile(metadata_name)
            if metadata is None:
                raise ValueError(f"could not read metadata from {artifact}")
            contents = metadata.read().decode()
    for line in contents.splitlines():
        if line.startswith("Version: "):
            return line.removeprefix("Version: ")
    raise ValueError(f"missing version metadata in {artifact}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tag", nargs="?", default="", help="release tag, for example v0.0.2"
    )
    parser.add_argument("--project", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()

    with args.project.open("rb") as project_file:
        version = tomllib.load(project_file)["project"]["version"]

    tag = args.tag
    if tag:
        expected = f"v{version}"
        if not re.fullmatch(r"v[0-9]+(?:\.[0-9]+)+(?:[-+][0-9A-Za-z.-]+)?", tag):
            raise ValueError(f"release tag is not a version tag: {tag!r}")
        if tag != expected:
            raise ValueError(
                f"release tag {tag!r} does not match metadata version {version!r}"
            )

    artifacts = sorted(
        path
        for path in args.dist.iterdir()
        if path.is_file() and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    )
    versions = {_metadata_version(path) for path in artifacts}
    if versions != {version}:
        raise ValueError(
            f"built versions {sorted(versions)!r} do not match {version!r}"
        )
    print(f"release metadata verified: typescope {version}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

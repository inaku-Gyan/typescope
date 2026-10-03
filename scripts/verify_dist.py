"""Validate and smoke-test the distributions in ``dist/``."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


def _metadata(artifact: Path) -> tuple[str, str]:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            candidates = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(candidates) != 1:
                raise ValueError(f"expected one wheel METADATA file in {artifact}")
            contents = archive.read(candidates[0]).decode()
    elif artifact.name.endswith(".tar.gz"):
        with tarfile.open(artifact, "r:gz") as archive:
            candidates = [
                member
                for member in archive.getmembers()
                if member.name.endswith("/PKG-INFO")
            ]
            if len(candidates) != 1:
                raise ValueError(f"expected one sdist PKG-INFO file in {artifact}")
            extracted = archive.extractfile(candidates[0])
            if extracted is None:
                raise ValueError(f"could not read sdist metadata from {artifact}")
            contents = extracted.read().decode()
    else:
        raise ValueError(f"unsupported distribution artifact: {artifact}")

    fields = {}
    for line in contents.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            if key in {"Name", "Version"}:
                fields[key] = value
    try:
        return fields["Name"], fields["Version"]
    except KeyError as error:
        raise ValueError(f"incomplete metadata in {artifact}") from error


def _python_in(environment: Path) -> Path:
    relative = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    return environment / relative


def _smoke_test(artifact: Path, uv: str) -> None:
    with tempfile.TemporaryDirectory(prefix="typescope-dist-") as temporary:
        environment = Path(temporary) / "venv"
        subprocess.run(
            [uv, "venv", "--python", sys.executable, str(environment)],
            check=True,
        )
        interpreter = _python_in(environment)
        subprocess.run(
            [
                uv,
                "pip",
                "install",
                "--python",
                str(interpreter),
                "--no-deps",
                str(artifact),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(interpreter),
                "-c",
                "from typescope import is_assignable; assert is_assignable(int, object)",
            ],
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    parser.add_argument(
        "--uv", default="uv", help="uv executable used for clean installs"
    )
    args = parser.parse_args()

    artifacts = sorted(
        path
        for path in args.directory.iterdir()
        if path.is_file() and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    )
    wheels = [path for path in artifacts if path.suffix == ".whl"]
    sdists = [path for path in artifacts if path.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError(
            "dist must contain exactly one wheel and one source distribution"
        )

    metadata = [_metadata(path) for path in artifacts]
    if len(set(metadata)) != 1 or metadata[0][0] != "typescope":
        raise ValueError(f"distribution metadata disagree: {metadata!r}")

    for artifact in artifacts:
        _smoke_test(artifact, args.uv)
        print(f"verified {artifact.name} ({metadata[0][0]} {metadata[0][1]})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

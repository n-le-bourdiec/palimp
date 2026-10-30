"""Build the synthetic scenario that `palimp demo` ships as package data (session 35).

The simulator is not shipped with palimp. This script runs the simulator CLI (black
box) for one Medium dev seed and packs its artifacts only (no ground truth, no
manifest) into `src/palimp/data/demo-scenario.tar.gz`, byte for byte reproducible:
sorted members, no owner, fixed times. With `--check`, it only says whether the
packaged file matches what the simulator writes today.

Usage:
    uv run python eval/demo_data.py          # rewrite the packaged file
    uv run python eval/demo_data.py --check  # exit 1 if it differs
"""

import argparse
import gzip
import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

LEVEL = "medium"
SEED = 14  # a dev seed (decision 0021), the smallest Medium scenario of seeds 0 to 19
TARGET = Path(__file__).parent.parent / "src" / "palimp" / "data" / "demo-scenario.tar.gz"


def build() -> bytes:
    with tempfile.TemporaryDirectory() as work:
        subprocess.run(
            [sys.executable, "-m", "palimp_sim.cli", "generate", "--level", LEVEL]
            + ["--seed", str(SEED), "--out", work],
            check=True,
            capture_output=True,
        )
        (scenario,) = Path(work).iterdir()
        artifacts = scenario / "artifacts"
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(p for p in artifacts.rglob("*") if p.is_file()):
                data = path.read_bytes()
                info = tarfile.TarInfo("artifacts/" + path.relative_to(artifacts).as_posix())
                info.size = len(data)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(data))
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode="wb", mtime=0, compresslevel=9) as out:
        out.write(raw.getvalue())
    return packed.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare only, write nothing")
    args = parser.parse_args()
    data = build()
    if args.check:
        same = TARGET.exists() and TARGET.read_bytes() == data
        print(f"{TARGET.name}: {'up to date' if same else 'differs from the simulator output'}")
        return 0 if same else 1
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(data)
    print(f"{TARGET} written ({len(data)} bytes, {LEVEL} seed {SEED})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Command line entry point: palimp-sim generate --level easy --seed 1 --out scenarios."""

import argparse
import sys
from pathlib import Path

from palimp_sim import __version__
from palimp_sim.generate import generate, scenario_id, write_scenario
from palimp_sim.levels import LEVELS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="palimp-sim", description=__doc__)
    parser.add_argument("--version", action="version", version=f"palimp-sim {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate", help="generate one scenario")
    gen.add_argument("--level", choices=sorted(LEVELS), required=True)
    gen.add_argument("--seed", type=int, required=True)
    gen.add_argument("--out", type=Path, default=Path("scenarios"))
    gen.add_argument("--force", action="store_true", help="overwrite an existing scenario")
    gen.add_argument(
        "--knob",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="override one knob of the level, for example log_collection=syslog-server",
    )
    args = parser.parse_args(argv)
    overrides = {}
    for item in args.knob:
        name, sep, value = item.partition("=")
        if not sep:
            parser.error(f"--knob expects NAME=VALUE, got {item!r}")
        overrides[name] = value

    directory = args.out / f"scenario-{scenario_id(args.level, args.seed)}"
    if directory.exists() and any(directory.iterdir()) and not args.force:
        print(f"{directory} already exists, use --force to overwrite", file=sys.stderr)
        return 1
    try:
        files = generate(args.level, args.seed, overrides)
    except ValueError as error:
        parser.error(str(error))
    write_scenario(files, directory)
    print(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

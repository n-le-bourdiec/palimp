"""Command line entry point: palimp-sim generate --level easy --seed 1 --out scenarios.

`--holdout INDEX` generates held-out scenario INDEX instead of a dev seed. It
reads the salt from the HOLDOUT_SALT environment variable, which exists only in
the held-out GitHub Actions workflow (decision 0007), and never prints it or
the derived seed.
"""

import argparse
import os
import sys
from pathlib import Path

from palimp_sim import __version__
from palimp_sim.generate import generate, generate_holdout, scenario_id, write_scenario
from palimp_sim.levels import LEVELS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="palimp-sim", description=__doc__)
    parser.add_argument("--version", action="version", version=f"palimp-sim {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate", help="generate one scenario")
    gen.add_argument("--level", choices=sorted(LEVELS), required=True)
    which = gen.add_mutually_exclusive_group(required=True)
    which.add_argument("--seed", type=int, help="dev scenario seed")
    which.add_argument(
        "--holdout",
        type=int,
        metavar="INDEX",
        help="held-out scenario index, needs the HOLDOUT_SALT environment variable",
    )
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

    salt = ""
    if args.holdout is not None:
        salt = os.environ.get("HOLDOUT_SALT", "")
        if not salt:
            parser.error(
                "--holdout needs the HOLDOUT_SALT environment variable. Held-out scenarios"
                " are generated only in the held-out GitHub Actions workflow (decision 0007);"
                " use --seed for dev scenarios"
            )
        name = f"holdout-{scenario_id(args.level, args.holdout)}"
    else:
        name = scenario_id(args.level, args.seed)
    directory = args.out / f"scenario-{name}"
    if directory.exists() and any(directory.iterdir()) and not args.force:
        print(f"{directory} already exists, use --force to overwrite", file=sys.stderr)
        return 1
    try:
        if args.holdout is not None:
            files = generate_holdout(args.level, salt, args.holdout, overrides)
        else:
            files = generate(args.level, args.seed, overrides)
    except ValueError as error:
        parser.error(str(error))
    write_scenario(files, directory)
    print(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

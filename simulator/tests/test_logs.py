"""RT_FLOW lines match the logging options of the policy in force at the time.

The config in force at a moment is rebuilt from the artifacts only: commit
times from commits.txt, contents from rollbacks/ (index 0 is config.set).
"""

import re
from datetime import datetime, timedelta

import pytest

from palimp_sim.generate import generate

COMMIT = re.compile(r"^(\d+)\s+(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ")
# Device lines start with `<14>1`, syslog server lines with the server prefix.
LINE = re.compile(r" ?1 (\S+) \S+ RT_FLOW - RT_FLOW_SESSION_(CREATE|CLOSE) ")


def log_options(config: str) -> dict[str, set[str]]:
    options: dict[str, set[str]] = {}
    for name, option in re.findall(r" policy (\S+) then log (session-init|session-close)", config):
        options.setdefault(name, set()).add(option)
    return options


def configs_by_time(files: dict[str, str]) -> list[tuple[datetime, dict[str, set[str]]]]:
    timeline = []
    for line in files["artifacts/commits.txt"].splitlines():
        match = COMMIT.match(line)
        if not match:
            continue
        index = int(match.group(1))
        path = (
            "artifacts/config.set"
            if index == 0
            else f"artifacts/rollbacks/rollback-{index:02d}.set"
        )
        moment = datetime.strptime(match.group(2), "%Y-%m-%d %H:%M:%S")
        timeline.append((moment, log_options(files[path])))
    return sorted(timeline, key=lambda item: item[0])


@pytest.mark.parametrize("seed", range(10))
def test_log_lines_follow_policy_log_options(seed: int) -> None:
    overrides = {"log_collection": "syslog-server"} if seed % 2 else {}
    generated = generate("easy", seed, overrides)
    files = {path: data.decode("utf-8") for path, data in generated.items()}
    timeline = configs_by_time(files)
    for line in files["artifacts/logs/rt_flow.log"].splitlines():
        stamp, kind = LINE.search(line).groups()
        moment = datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")
        if kind == "CLOSE":
            moment -= timedelta(seconds=int(re.search(r'elapsed-time="(\d+)"', line).group(1)))
        name = re.search(r'policy-name="([^"]+)"', line).group(1)
        in_force = [options for when, options in timeline if when <= moment][-1]
        expected = "session-init" if kind == "CREATE" else "session-close"
        assert expected in in_force.get(name, set()), (kind, name, stamp)


@pytest.mark.parametrize("seed", range(10))
def test_policies_without_logging_produce_no_lines(seed: int) -> None:
    files = {path: data.decode("utf-8") for path, data in generate("easy", seed).items()}
    logged = set()
    for path, text in files.items():
        if path.endswith(".set"):
            logged |= set(log_options(text))
    names = set(re.findall(r'policy-name="([^"]+)"', files["artifacts/logs/rt_flow.log"]))
    assert names <= logged

"""Ground truth text never leaks into visible artifacts.

For every rule, the visible texts tied to it (policy description, comment of
the creating commit, summary of its ticket) must not contain intent.summary,
and must not share more than 60% of their distinct tokens with it. Tokens are
lowercase alphanumeric words, minus a few stop words and the rule's own
application code, which object names already show (a terse description such
as "for BADGE SQL (1433)" names the application and the service, not the
intent).
"""

import csv
import io
import json
import re

import pytest

from palimp_sim.generate import generate
from palimp_sim.voice import code

STOP_WORDS = {"a", "an", "the", "to", "of", "for", "from", "and", "with", "its", "on", "in", "by"}
MAX_SHARED = 0.6
COMMIT = re.compile(r"^(\d+)\s+\d{4}-")


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS


def shared_ratio(visible: str, summary: str, app_id: str | None = None) -> float:
    words = tokens(visible) - ({code(app_id).lower()} if app_id else set())
    return len(words & tokens(summary)) / len(words) if words else 0.0


def visible_texts(files: dict[str, str], truth: dict, rule: dict) -> list[str]:
    name = rule["key"]["name"]
    texts = re.findall(
        rf' policy {re.escape(name)} description "([^"]*)"', files["artifacts/config.set"]
    )
    comments: dict[int, str] = {}
    current = None
    for line in files["artifacts/commits.txt"].splitlines():
        match = COMMIT.match(line)
        if match:
            current = int(match.group(1))
        elif current is not None:
            comments[current] = line.strip()
    texts.append(comments.get(rule["created"]["commit_index"], ""))
    event = next(e for e in truth["events"] if e["event_id"] == rule["created"]["event_id"])
    tickets = {
        row["ticket_id"]: row for row in csv.DictReader(io.StringIO(files["artifacts/tickets.csv"]))
    }
    if event["ticket_id"] in tickets:
        texts.append(tickets[event["ticket_id"]]["summary"])
    return [text for text in texts if text]


CASES = [("easy", s) for s in range(100)] + [("medium", s) for s in range(100)]


def _mark(level: str, seed: int):
    """Seeds 0 to 2 always; Easy and Medium up to 9 in CI; Medium 10 to 99 with --runslow."""
    if seed < 3:
        return (level, seed)
    full = level == "medium" and seed >= 10
    return pytest.param(level, seed, marks=pytest.mark.full if full else pytest.mark.slow)


@pytest.mark.parametrize(("level", "seed"), [_mark(*case) for case in CASES])
def test_no_ground_truth_text_in_visible_texts(level: str, seed: int) -> None:
    files = {path: data.decode("utf-8") for path, data in generate(level, seed).items()}
    truth = json.loads(files["ground_truth.json"])
    for rule in truth["rules"]:
        summary = rule["intent"]["summary"]
        for text in visible_texts(files, truth, rule):
            assert summary.lower() not in text.lower(), (rule["key"]["name"], text)
            ratio = shared_ratio(text, summary, rule["intent"]["app_id"])
            assert ratio <= MAX_SHARED, (rule["key"]["name"], text, summary)


def test_ratio_detects_a_paraphrase() -> None:
    summary = "Office users reach the CRM web front end"
    assert shared_ratio("CRM web front end for office users", summary) > MAX_SHARED
    assert shared_ratio("allow LAN to CRM FE (443)", summary) <= MAX_SHARED

"""Ground truth text never leaks into visible artifacts.

For every rule, the visible texts tied to it (policy description, comment of
the creating commit, summary of its ticket) must not contain intent.summary,
and must not share more than 60% of their distinct tokens with it. Tokens are
lowercase alphanumeric words, minus a few stop words.
"""

import csv
import io
import json
import re

import pytest

from palimp_sim.generate import generate

STOP_WORDS = {"a", "an", "the", "to", "of", "for", "from", "and", "with", "its", "on", "in", "by"}
MAX_SHARED = 0.6
COMMIT = re.compile(r"^(\d+)\s+\d{4}-")


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS


def shared_ratio(visible: str, summary: str) -> float:
    words = tokens(visible)
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


@pytest.mark.parametrize("seed", range(100))
def test_no_ground_truth_text_in_visible_texts(seed: int) -> None:
    files = {path: data.decode("utf-8") for path, data in generate("easy", seed).items()}
    truth = json.loads(files["ground_truth.json"])
    for rule in truth["rules"]:
        summary = rule["intent"]["summary"]
        for text in visible_texts(files, truth, rule):
            assert summary.lower() not in text.lower(), (rule["key"]["name"], text)
            assert shared_ratio(text, summary) <= MAX_SHARED, (rule["key"]["name"], text, summary)


def test_ratio_detects_a_paraphrase() -> None:
    summary = "Office users reach the CRM web front end"
    assert shared_ratio("CRM web front end for office users", summary) > MAX_SHARED
    assert shared_ratio("allow LAN to CRM FE (443)", summary) <= MAX_SHARED

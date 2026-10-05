import json

import jsonschema
import pytest

from palimp_sim.generate import generate
from palimp_sim.truth import schema, validate


def test_schema_is_valid() -> None:
    jsonschema.Draft202012Validator.check_schema(schema())


@pytest.mark.parametrize(("level", "seed"), [("easy", 0), ("easy", 1), ("easy", 2), ("medium", 0)])
def test_ground_truth_matches_schema(level: str, seed: int) -> None:
    validate(json.loads(generate(level, seed)["ground_truth.json"]))


def test_schema_rejects_unknown_verdict() -> None:
    document = json.loads(generate("easy", 1)["ground_truth.json"])
    document["rules"][0]["expected"]["verdict"] = "delete"
    with pytest.raises(jsonschema.ValidationError):
        validate(document)
